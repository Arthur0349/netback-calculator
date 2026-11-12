"""Shared UI helpers for the Streamlit app.

Everything here is commodity-agnostic: pages render whatever the selected
``CommodityProfile`` and reference data expose (routes, defaults, quality
spec keys), and fall back to manual inputs when the reference data has no
entry for the selected commodity (config-skeleton profiles).
"""

from typing import Any

import plotly.graph_objects as go
import streamlit as st

import theme
from netback.core.concentrate import value_concentrate
from netback.core.netback import compute_result
from netback.core.sensitivity import SensitivityRow
from netback.data.providers.static import StaticDataProvider
from netback.models.schemas import (DELIVERY_TERM_LEGS, CommodityProfile,
                                    CostInputs, NetbackResult, Route)
from netback.reporting.trade_sheet import waterfall_steps

# Generic seeds used when the reference data ships no defaults for a
# commodity (config skeletons). Deliberately neutral, all overridable.
_GENERIC_DEFAULTS: dict[str, Any] = {
    "quantity": 10_000.0,
    "price_basis": 100.0,
    "freight_rate_per_unit": 20.0,
    "insurance_rate_pct": 0.3,
    "financing_rate_annual_pct": 6.0,
    "payment_terms_days": 30.0,
    "load_port_fee_per_unit": 2.0,
    "discharge_port_fee_per_unit": 2.0,
    "commission_pct": 0.0,
    "delivery_term": "CIF",
}

DELIVERY_TERM_HELP = "\n\n".join([
    "**CFR**: buyer insures, buyer unloads.",
    "**CIF**: seller insures, buyer unloads.",
    "**DAP**: seller insures and carries transit risk, buyer unloads.",
    "**DPU**: seller also pays discharge handling.",
])

MODE_LABELS = {"netback": "Netback", "landed_cost": "Landed cost"}
MODE_HELP = ("**Netback**: delivered sale price → FOB value at the load port "
             "(the seller's view).\n\n**Landed cost**: FOB price → delivered "
             "cost (the buyer's view).")

# Muted categorical colours that sit on the dark surface without competing
# with the green/red cost semantics or the amber accent.
COST_LEG_PALETTE = ["#587FA8", "#4E9E94", "#7E76B4", "#9C8A5E", "#5C6B84"]
NEUTRAL_BAR = "#587FA8"

# Charts are read, not explored: no mode bar, no zoom on scroll.
PLOTLY_CONFIG = {"displayModeBar": False, "scrollZoom": False}

_PRICE_UNITS = {"pct": "USD/t", "g_per_t": "USD/oz"}
_RC_UNITS = {"pct": "USD/lb payable", "g_per_t": "USD/oz payable"}


@st.cache_resource
def get_provider() -> StaticDataProvider:
    return StaticDataProvider()


def chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


# --- selection ---------------------------------------------------------------

def ordered_commodities(provider: StaticDataProvider) -> list[str]:
    """Commodities with the most reference routes first, so every page opens
    on a fully built case; config skeletons last."""
    return sorted(provider.list_commodities(),
                  key=lambda c: (-len(provider.list_routes(c)), c))


def commodity_selectbox(provider: StaticDataProvider, container,
                        key: str = "commodity") -> str:
    """Selectbox over every commodity the provider knows, labelled by
    profile name. Returns the commodity key."""
    return container.selectbox(
        "Commodity", ordered_commodities(provider), key=key,
        format_func=lambda k: provider.get_commodity_profile(k).name,
    )


def route_label(route: Route, vessel: bool = False) -> str:
    label = f"{route.load_port} → {route.discharge_port}"
    return f"{label} ({route.vessel_type})" if vessel else label


def freight_unit(profile: CommodityProfile) -> str:
    return "wmt" if profile.freight_moisture_key else profile.unit


def spec_label(key: str) -> str:
    """Display name of a quality spec key: ``sulfur_pct`` -> ``Sulfur %``."""
    label = key.replace("_pct", " %").replace("_", " ")
    return label.capitalize() if label.islower() else label


def seed_inputs(provider: StaticDataProvider, commodity: str,
                route_id: str | None) -> dict[str, Any]:
    """Best-available default values for the input widgets: provider
    defaults when the reference data has them, generic seeds otherwise."""
    profile = provider.get_commodity_profile(commodity)
    seed = dict(_GENERIC_DEFAULTS)
    seed["actual_quality"] = dict(profile.benchmark_spec)
    try:
        seed["price_basis"] = provider.get_benchmark_price(commodity)
    except KeyError:
        pass
    if route_id is not None:
        try:
            ci = provider.get_default_cost_inputs(commodity, route_id)
        except KeyError:
            return seed
        seed.update(ci.model_dump())
    return seed


def route_inputs(provider: StaticDataProvider, commodity: str, container,
                 key_prefix: str = "") -> tuple[str | None, Route]:
    """Route selection. Offers the provider's routes for this commodity;
    when there are none, falls back to manual route entry."""
    route_ids = provider.list_routes(commodity)
    if route_ids:
        route_id = container.selectbox(
            "Route", route_ids, key=f"{key_prefix}route_{commodity}",
            format_func=lambda rid: route_label(provider.get_route(rid)),
        )
        return route_id, provider.get_route(route_id)

    container.caption("No reference routes for this commodity yet: "
                      "enter the voyage manually.")
    k = f"{key_prefix}{commodity}"
    route = Route(
        load_port=container.text_input("Load port", "Load port", key=f"{k}_lp"),
        discharge_port=container.text_input("Discharge port", "Discharge port",
                                            key=f"{k}_dp"),
        distance_nm=container.number_input("Distance (nm)", min_value=1.0,
                                           value=5000.0, step=100.0,
                                           format="%.0f", key=f"{k}_nm"),
        transit_days=container.number_input("Transit days", min_value=0.5,
                                            value=20.0, step=1.0, format="%.0f",
                                            key=f"{k}_td"),
        vessel_type=container.text_input("Vessel type", "Panamax", key=f"{k}_vt"),
    )
    return None, route


# --- input forms -------------------------------------------------------------

def quality_inputs(profile: CommodityProfile, seed: dict[str, Any], container,
                   key_prefix: str = "") -> dict[str, float]:
    """One widget per benchmark spec key (benchmark value in the label),
    seeded from the reference cargo."""
    seed_quality = seed.get("actual_quality", {})
    return {
        spec_key: container.number_input(
            f"{spec_label(spec_key)} (benchmark {benchmark_value:g})",
            value=float(seed_quality.get(spec_key, benchmark_value)),
            key=f"{key_prefix}quality_{spec_key}", format="%.2f",
        )
        for spec_key, benchmark_value in profile.benchmark_spec.items()
    }


def cost_inputs_form(profile: CommodityProfile, seed: dict[str, Any], container,
                     mode: str = "netback", key_prefix: str = "") -> CostInputs:
    """Every ``CostInputs`` field as a widget seeded from ``seed``, grouped in
    collapsible sections. Concentrates get no price widget: their delivered
    value is computed from the assays (see ``concentrate_inputs``). Quality
    fields come from the profile's benchmark spec, so a new commodity needs
    no UI change."""
    k = key_prefix
    is_concentrate = profile.concentrate_terms is not None

    deal = container.expander("Deal", expanded=True)
    terms = list(DELIVERY_TERM_LEGS)
    delivery_term = deal.selectbox(
        "Delivery term", terms, index=terms.index(seed.get("delivery_term", "CIF")),
        key=f"{k}term", help=DELIVERY_TERM_HELP)
    if is_concentrate:
        price_basis = float(seed["price_basis"])   # replaced by the valuation
    else:
        price_label = (f"{delivery_term} sale price" if mode == "netback"
                       else "FOB price")
        price_basis = deal.number_input(
            f"{price_label} (USD/{profile.unit})", min_value=0.01,
            value=float(seed["price_basis"]), format="%.2f", key=f"{k}price")
    quantity = deal.number_input(
        f"Quantity ({profile.unit})", min_value=1.0,
        value=float(seed["quantity"]), step=1000.0, format="%.0f",
        key=f"{k}quantity")

    costs = container.expander("Voyage costs", expanded=True)
    freight = costs.number_input(
        f"Freight (USD/{freight_unit(profile)})", min_value=0.0,
        value=float(seed["freight_rate_per_unit"]), format="%.2f",
        key=f"{k}freight",
        help=("Quoted per wet tonne; converted to the dry pricing basis with "
              "the cargo moisture." if profile.freight_moisture_key else None))
    left, right = costs.columns(2)
    load_fee = left.number_input(
        "Load fee", min_value=0.0,
        value=float(seed["load_port_fee_per_unit"]), format="%.2f",
        key=f"{k}loadfee")
    discharge_fee = right.number_input(
        "Discharge fee", min_value=0.0,
        value=float(seed["discharge_port_fee_per_unit"]), format="%.2f",
        key=f"{k}dischfee")
    left, right = costs.columns(2)
    insurance = left.number_input(
        "Insurance %", min_value=0.0,
        value=float(seed["insurance_rate_pct"]), step=0.05, format="%.2f",
        key=f"{k}insurance")
    commission = right.number_input(
        "Commission %", min_value=0.0, value=float(seed["commission_pct"]),
        step=0.05, format="%.2f", key=f"{k}commission")
    left, right = costs.columns(2)
    financing = left.number_input(
        "Financing %/yr", min_value=0.0,
        value=float(seed["financing_rate_annual_pct"]), step=0.25,
        format="%.2f", key=f"{k}financing")
    payment_days = right.number_input(
        "Credit days", min_value=0.0,
        value=float(seed["payment_terms_days"]), step=5.0, format="%.0f",
        key=f"{k}terms")
    costs.caption(f"Port fees in USD/{profile.unit}; the discharge fee is "
                  "seller-side under DPU only. Insurance on 110 % of CIF. "
                  "Credit days run on top of transit.")

    quality = container.expander(
        "Cargo assays" if is_concentrate else "Cargo quality", expanded=True)
    actual_quality = quality_inputs(profile, seed, quality, key_prefix=k)

    return CostInputs(
        quantity=quantity,
        price_basis=price_basis,
        freight_rate_per_unit=freight,
        insurance_rate_pct=insurance,
        financing_rate_annual_pct=financing,
        payment_terms_days=payment_days,
        load_port_fee_per_unit=load_fee,
        discharge_port_fee_per_unit=discharge_fee,
        actual_quality=actual_quality,
        commission_pct=commission,
        delivery_term=delivery_term,
    )


def metal_price_inputs(profile: CommodityProfile, metal_prices: dict[str, float],
                       container, key_prefix: str = "") -> dict[str, float]:
    return {
        p.price_key: container.number_input(
            f"{p.price_key} ({_PRICE_UNITS[p.unit]})", min_value=0.0,
            value=float(metal_prices.get(p.price_key, 0.0)), format="%.2f",
            key=f"{key_prefix}px_{p.price_key}")
        for p in profile.concentrate_terms.payables
    }


def concentrate_inputs(profile: CommodityProfile, metal_prices: dict[str, float],
                       container, key_prefix: str = ""
                       ) -> tuple[CommodityProfile, dict[str, float]]:
    """Metal prices and smelter terms (TC, RC per payable metal) as widgets.
    Returns the profile with the edited terms and the edited prices."""
    terms = profile.concentrate_terms
    k = key_prefix
    prices = metal_price_inputs(
        profile, metal_prices, container.expander("Metal prices", expanded=True),
        key_prefix=k)
    smelter = container.expander("Smelter terms", expanded=True)
    tc = smelter.number_input(
        f"TC (USD/{profile.unit})", value=float(terms.treatment_charge),
        step=5.0, format="%.2f", key=f"{k}tc",
        help="Negative = the smelter pays the miner. 2026 annual benchmark: "
             "USD 0/dmt; spot traded around -USD 120/dmt by mid-2026.")
    payables = []
    for p in terms.payables:
        rc = smelter.number_input(
            f"RC {p.element} ({_RC_UNITS[p.unit]})", value=float(p.refining_charge),
            step=0.01 if p.unit == "pct" else 0.1, format="%.3f",
            key=f"{k}rc_{p.element}")
        payables.append(p.model_copy(update={"refining_charge": rc}))
    edited = terms.model_copy(update={"treatment_charge": tc, "payables": payables})
    return profile.model_copy(update={"concentrate_terms": edited}), prices


# --- results -----------------------------------------------------------------

def compute(inputs: CostInputs, route: Route, profile: CommodityProfile,
            mode: str, metal_prices: dict[str, float] | None = None) -> NetbackResult:
    return compute_result(inputs, route, profile, mode, metal_prices)


def money(value: float, signed: bool = False) -> str:
    """$1,234.50, with the sign ahead of the currency: -$4.50, +$1.50."""
    sign = "-" if value < 0 else ("+" if signed and value > 0 else "")
    return f"{sign}${abs(value):,.2f}"


def voyage_costs(result: NetbackResult) -> float:
    return (result.freight_cost + result.insurance_cost + result.financing_cost
            + result.port_fees_total + result.commission_cost)


def result_metric_cards(result: NetbackResult, unit: str, quantity: float) -> None:
    """Headline cards. Index commodities: price, voyage costs, quality,
    result. Concentrates: payables, smelter deductions, voyage costs, result."""
    costs = voyage_costs(result)
    result_label = result.breakdown[-1][0]
    sign = -1 if result.mode == "netback" else 1
    final = {"label": result_label, "value": money(result.result_price),
             "unit": unit, "accent": True,
             "delta": f"${result.result_price * quantity / 1e6:,.2f}M on the cargo"}
    costs_card = {"label": "Voyage costs", "value": money(sign * costs),
                  "unit": unit,
                  "delta": f"{costs / result.base_price:.1%} of "
                           + ("invoice value" if result.price_build_up else "price")}

    if result.price_build_up:
        payable = sum(v for label, v in result.price_build_up
                      if label.startswith("Payable"))
        deductions = result.base_price - payable
        theme.metric_cards([
            {"label": "Payable metals", "value": money(payable), "unit": unit},
            {"label": "TC / RC / penalties", "value": money(deductions, signed=True),
             "unit": unit,
             "delta": ("smelter pays the miner" if deductions > 0
                       else "deducted by the smelter"),
             "delta_kind": "pos" if deductions > 0 else ""},
            costs_card, final,
        ])
        return

    quality = result.quality_adjustment
    theme.metric_cards([
        {"label": f"{result.delivery_term} price" if result.mode == "netback"
                  else "FOB price",
         "value": money(result.base_price), "unit": unit},
        costs_card,
        {"label": "Quality adjustment", "value": money(quality, signed=True),
         "unit": unit,
         "delta": ("premium vs benchmark" if quality > 0 else
                   "penalty vs benchmark" if quality < 0 else "on benchmark"),
         "delta_kind": "pos" if quality > 0 else "neg" if quality < 0 else ""},
        final,
    ])


def concentrate_details_table(profile: CommodityProfile, inputs: CostInputs,
                              metal_prices: dict[str, float]) -> None:
    v = value_concentrate(inputs.actual_quality, profile.concentrate_terms,
                          metal_prices)
    theme.data_table(
        ["Line", "Payable / assay", f"USD/{profile.unit}"],
        [[line, qty, f"{val:,.2f}"] for line, qty, val in v.details]
        + [["Net invoice value", "", f"{v.net_value:,.2f}"]],
    )


# --- charts ------------------------------------------------------------------

def terminal_layout(fig: go.Figure, **overrides: Any) -> go.Figure:
    """Apply the shared dark-terminal chart chrome: transparent paper,
    hairline grid, monospace tick labels, terminal hover chips."""
    axis = dict(gridcolor=theme.BORDER, zerolinecolor=theme.BORDER,
                linecolor=theme.BORDER, fixedrange=True,
                tickfont=dict(family=theme.MONO, color=theme.MUTED, size=11))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    fig.update_layout(
        font=dict(family=theme.SANS, color=theme.TEXT, size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=theme.SURFACE, bordercolor=theme.BORDER,
                        font=dict(family=theme.MONO, color=theme.TEXT,
                                  size=12)),
        dragmode=False,
        **overrides,
    )
    return fig


def waterfall_figure(result: NetbackResult, unit: str,
                     horizontal: bool = False) -> go.Figure:
    """Bridge chart: price (or payables) → each signed leg → result. The
    value axis is cropped to the running total's envelope: pinned at zero,
    the individual cost legs would be a few pixels tall."""
    steps = waterfall_steps(result)
    labels = [label for label, _, _ in steps]
    values = [value for _, value, _ in steps]
    measures = ["absolute"] + ["total" if kind == "total" else "relative"
                               for _, _, kind in steps[1:]]

    running, cumulative = 0.0, []
    for value, measure in zip(values, measures):
        running = value if measure != "relative" else running + value
        cumulative.append(running)
    lo, hi = min(cumulative), max(cumulative)
    pad = (hi - lo) * 0.3 or hi * 0.05
    value_range = [lo - pad, hi + pad * (1.6 if horizontal else 1.0)]

    text = [f"{v:+,.2f}" if m == "relative" else f"{v:,.2f}"
            for v, m in zip(values, measures)]
    style = dict(
        measure=measures, text=text, textposition="outside",
        textfont=dict(family=theme.MONO, color=theme.TEXT, size=11),
        connector={"line": {"color": theme.BORDER, "width": 1}},
        increasing={"marker": {"color": theme.CHART_GREEN}},
        decreasing={"marker": {"color": theme.CHART_RED}},
        totals={"marker": {"color": theme.CHART_TOTAL}},
        cliponaxis=False,
    )
    hover = f"%{{{'y' if horizontal else 'x'}}}<extra></extra>"
    if horizontal:
        fig = go.Figure(go.Waterfall(orientation="h", y=labels, x=values,
                                     hovertemplate=hover, **style))
        return terminal_layout(
            fig, showlegend=False, height=70 + 34 * len(labels),
            xaxis=dict(range=value_range, showticklabels=False, showgrid=False),
            yaxis=dict(autorange="reversed", automargin=True,
                       tickfont=dict(family=theme.SANS, color=theme.TEXT, size=11)),
            margin=dict(t=8, b=8, l=4, r=4),
        )
    tick_labels = [label.replace(" ", "<br>") if len(label) > 9 else label
                   for label in labels]
    fig = go.Figure(go.Waterfall(x=tick_labels, y=values,
                                 hovertemplate=hover, **style))
    return terminal_layout(
        fig, showlegend=False, height=440,
        yaxis=dict(range=value_range, title=f"USD/{unit}",
                   title_font=dict(size=11, color=theme.MUTED)),
        xaxis=dict(tickangle=0, showgrid=False,
                   tickfont=dict(family=theme.SANS, color=theme.TEXT, size=11)),
        margin=dict(t=28, b=48, l=8, r=8),
    )


def responsive_waterfall(result: NetbackResult, unit: str) -> None:
    """Vertical bridge on wide screens, horizontal on phones. Both are
    rendered; the stylesheet shows one per viewport."""
    with st.container(key="nb_wide"):
        chart(waterfall_figure(result, unit))
    with st.container(key="nb_narrow"):
        chart(waterfall_figure(result, unit, horizontal=True))


def cost_share_figure(result: NetbackResult, unit: str) -> go.Figure:
    """Proportional horizontal bar: each cost leg's share of total voyage
    costs (excludes the quality adjustment, which is not a cost)."""
    legs = [(label, value) for label, value in [
        ("Freight", result.freight_cost),
        ("Financing", result.financing_cost),
        ("Port fees", result.port_fees_total),
        ("Insurance", result.insurance_cost),
        ("Commission", result.commission_cost),
    ] if value > 0]
    total = sum(v for _, v in legs) or 1.0

    fig = go.Figure()
    for (label, value), color in zip(legs, COST_LEG_PALETTE):
        share = value / total
        fig.add_trace(go.Bar(
            x=[share], y=[""], name=f"{label} {share:.0%}",
            orientation="h", marker_color=color,
            text=f"{value:,.2f}" if share > 0.12 else "",
            textposition="inside", insidetextanchor="middle", textangle=0,
            textfont=dict(family=theme.MONO, size=11, color="#0A0E17"),
            hovertemplate=(f"{label}: ${value:,.2f}/{unit} "
                           f"({share:.1%})<extra></extra>"),
        ))
    return terminal_layout(
        fig, barmode="stack", height=104,
        xaxis=dict(range=[0, 1], title=None, showticklabels=False,
                   showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, x=0,
                    traceorder="normal",
                    font=dict(size=11, color=theme.MUTED)),
        margin=dict(t=6, b=6, l=0, r=0),
    )


def tornado_figure(base: float, rows: list[SensitivityRow], unit: str) -> go.Figure:
    """Tornado chart: change in the result when each driver is shocked down
    (muted bar) and up (amber bar), largest swing on top."""
    rows = rows[::-1]
    labels = [f"{r.driver}  <span style='color:{theme.MUTED}'>{r.shock}</span>"
              for r in rows]
    span = max((r.swing for r in rows), default=1.0)
    common = dict(orientation="h", y=labels, textposition="outside",
                  textfont=dict(family=theme.MONO, size=10, color=theme.TEXT),
                  cliponaxis=False)
    fig = go.Figure([
        go.Bar(name="Driver down", x=[r.delta_low for r in rows],
               text=[f"{r.delta_low:+,.2f}" for r in rows],
               marker_color=NEUTRAL_BAR,
               hovertemplate="Driver down: %{x:+,.2f}<extra></extra>", **common),
        go.Bar(name="Driver up", x=[r.delta_high for r in rows],
               text=[f"{r.delta_high:+,.2f}" for r in rows],
               marker_color=theme.AMBER,
               hovertemplate="Driver up: %{x:+,.2f}<extra></extra>", **common),
    ])
    return terminal_layout(
        fig, barmode="overlay", height=90 + 38 * len(rows),
        xaxis=dict(range=[-span * 1.8, span * 1.8], zeroline=True,
                   zerolinecolor=theme.MUTED,
                   title=f"Change in result, USD/{unit} (base {base:,.2f})",
                   title_font=dict(size=11, color=theme.MUTED)),
        yaxis=dict(automargin=True,
                   tickfont=dict(family=theme.SANS, color=theme.TEXT, size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    font=dict(size=11, color=theme.MUTED)),
        margin=dict(t=30, b=44, l=8, r=8),
    )
