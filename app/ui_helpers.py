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
from netback.core.netback import compute_netback
from netback.data.providers.static import StaticDataProvider
from netback.models.schemas import CommodityProfile, CostInputs, NetbackResult, Route

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
}

MODE_LABELS = {
    "netback": "Netback (CIF sale price → FOB netback)",
    "landed_cost": "Landed cost (FOB price → delivered cost)",
}

# Muted categorical colours that sit on the dark surface without competing
# with the green/red cost semantics or the amber accent.
COST_LEG_PALETTE = ["#587FA8", "#4E9E94", "#7E76B4", "#9C8A5E", "#5C6B84"]
SCENARIO_PALETTE = ["#5B8DBE", "#9C8AC5", "#4E9E94"]


@st.cache_resource
def get_provider() -> StaticDataProvider:
    return StaticDataProvider()


def commodity_selectbox(provider: StaticDataProvider, container,
                        key: str = "commodity") -> str:
    """Selectbox over every commodity the provider knows, labelled by
    profile name. Returns the commodity key."""
    keys = provider.list_commodities()
    return container.selectbox(
        "Commodity", keys, key=key,
        format_func=lambda k: provider.get_commodity_profile(k).name,
    )


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
            format_func=lambda rid: _route_label(provider.get_route(rid)),
        )
        return route_id, provider.get_route(route_id)

    container.info("No reference routes for this commodity yet — "
                   "enter the voyage manually.")
    k = f"{key_prefix}{commodity}"
    route = Route(
        load_port=container.text_input("Load port", "Load port", key=f"{k}_lp"),
        discharge_port=container.text_input("Discharge port", "Discharge port",
                                            key=f"{k}_dp"),
        distance_nm=container.number_input("Distance (nm)", min_value=1.0,
                                           value=5000.0, key=f"{k}_nm"),
        transit_days=container.number_input("Transit days", min_value=0.5,
                                            value=20.0, key=f"{k}_td"),
        vessel_type=container.text_input("Vessel type", "Panamax", key=f"{k}_vt"),
    )
    return None, route


def cost_inputs_form(profile: CommodityProfile, seed: dict[str, Any], container,
                     key_prefix: str = "") -> CostInputs:
    """Render every ``CostInputs`` field as a widget seeded from ``seed``.

    Quality fields are generated from the profile's benchmark spec keys, so
    a new commodity needs no UI change.
    """
    k = key_prefix
    quantity = container.number_input(
        f"Quantity ({profile.unit})", min_value=1.0,
        value=float(seed["quantity"]), step=1000.0, key=f"{k}quantity")
    price_basis = container.number_input(
        f"Base price (USD/{profile.unit})", min_value=0.01,
        value=float(seed["price_basis"]), key=f"{k}price")

    freight = container.number_input(
        f"Freight rate (USD/{profile.unit})", min_value=0.0,
        value=float(seed["freight_rate_per_unit"]), key=f"{k}freight")
    insurance = container.number_input(
        "Insurance rate (% of insured value)", min_value=0.0,
        value=float(seed["insurance_rate_pct"]), step=0.05, format="%.2f",
        key=f"{k}insurance")
    financing = container.number_input(
        "Financing rate (annual %)", min_value=0.0,
        value=float(seed["financing_rate_annual_pct"]), step=0.25,
        format="%.2f", key=f"{k}financing")
    payment_days = container.number_input(
        "Payment terms (days)", min_value=0.0,
        value=float(seed["payment_terms_days"]), step=5.0, key=f"{k}terms")
    load_fee = container.number_input(
        f"Load port fee (USD/{profile.unit})", min_value=0.0,
        value=float(seed["load_port_fee_per_unit"]), key=f"{k}loadfee")
    discharge_fee = container.number_input(
        f"Discharge port fee (USD/{profile.unit})", min_value=0.0,
        value=float(seed["discharge_port_fee_per_unit"]), key=f"{k}dischfee")
    commission = container.number_input(
        "Commission (%)", min_value=0.0, value=float(seed["commission_pct"]),
        step=0.05, format="%.2f", key=f"{k}commission")

    container.markdown("**Cargo quality** (benchmark in parentheses)")
    seed_quality = seed.get("actual_quality", {})
    actual_quality = {
        spec_key: container.number_input(
            f"{spec_key} ({benchmark_value:g})",
            value=float(seed_quality.get(spec_key, benchmark_value)),
            key=f"{k}quality_{spec_key}", format="%.2f",
        )
        for spec_key, benchmark_value in profile.benchmark_spec.items()
    }

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
    )


def result_metric_cards(result: NetbackResult, unit: str) -> None:
    """Headline metric cards: base price, total costs, quality adjustment,
    final result."""
    total_costs = (result.freight_cost + result.insurance_cost
                   + result.financing_cost + result.port_fees_total
                   + result.commission_cost)
    result_label = result.breakdown[-1][0]
    sign = "-" if result.mode == "netback" else "+"
    quality_premium = result.quality_adjustment >= 0

    theme.metric_cards([
        {"label": "Base price", "value": f"${result.base_price:,.2f}",
         "unit": unit},
        {"label": "Total voyage costs", "value": f"${total_costs:,.2f}",
         "unit": unit,
         "delta": f"{sign}{total_costs / result.base_price:.1%} of base"},
        {"label": "Quality adjustment",
         "value": f"${result.quality_adjustment:+,.2f}", "unit": unit,
         "delta": "premium" if quality_premium else "penalty",
         "delta_kind": "pos" if quality_premium else "neg"},
        {"label": result_label, "value": f"${result.result_price:,.2f}",
         "unit": unit, "accent": True,
         "delta": f"{result.result_price - result.base_price:+,.2f} vs base"},
    ])


def terminal_layout(fig: go.Figure, **overrides: Any) -> go.Figure:
    """Apply the shared dark-terminal chart chrome: transparent paper,
    hairline grid, monospace tick labels, terminal hover chips."""
    fig.update_layout(
        font=dict(family=theme.SANS, color=theme.TEXT, size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=theme.SURFACE, bordercolor=theme.BORDER,
                        font=dict(family=theme.MONO, color=theme.TEXT,
                                  size=12)),
        **overrides,
    )
    axis = dict(gridcolor=theme.BORDER, zerolinecolor=theme.BORDER,
                linecolor=theme.BORDER,
                tickfont=dict(family=theme.MONO, color=theme.MUTED, size=11))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def waterfall_figure(result: NetbackResult, unit: str) -> go.Figure:
    """Bridge chart: base price → each signed cost leg → result price,
    straight from ``NetbackResult.breakdown``."""
    labels = [label for label, _ in result.breakdown]
    values = [value for _, value in result.breakdown]
    measures = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]

    # Crop the y-axis to the running total's envelope: with an axis pinned
    # at zero the individual cost legs are a few pixels tall and unreadable.
    running, cumulative = 0.0, []
    for value, measure in zip(values, measures):
        running = value if measure == "total" else running + value
        cumulative.append(running)
    lo, hi = min(cumulative), max(cumulative)
    pad = (hi - lo) * 0.3 or hi * 0.05

    tick_labels = [label.replace(" ", "<br>", 1) if len(label) > 12 else label
                   for label in labels]

    fig = go.Figure(go.Waterfall(
        x=tick_labels, y=values, measure=measures,
        text=[f"{v:+,.2f}" if m == "relative" else f"{v:,.2f}"
              for v, m in zip(values, measures)],
        textposition="outside",
        textfont=dict(family=theme.MONO, color=theme.TEXT, size=11),
        connector={"line": {"color": theme.BORDER, "width": 1}},
        increasing={"marker": {"color": theme.CHART_GREEN}},
        decreasing={"marker": {"color": theme.CHART_RED}},
        totals={"marker": {"color": theme.CHART_TOTAL}},
    ))
    return terminal_layout(
        fig,
        title=dict(text=f"{labels[0]} → {labels[-1]}  ·  USD/{unit}",
                   font=dict(family=theme.SANS, color=theme.MUTED, size=12)),
        yaxis=dict(range=[lo - pad, hi + pad]),
        yaxis_title=None, showlegend=False,
        margin=dict(t=48, b=56), height=460,
    )


def cost_share_figure(result: NetbackResult, unit: str) -> go.Figure:
    """Proportional horizontal bar: each cost leg's share of total voyage
    costs (excludes the quality adjustment, which is not a cost)."""
    legs = [
        ("Freight", result.freight_cost),
        ("Insurance", result.insurance_cost),
        ("Financing", result.financing_cost),
        ("Port fees", result.port_fees_total),
        ("Commission", result.commission_cost),
    ]
    total = sum(v for _, v in legs) or 1.0
    palette = COST_LEG_PALETTE

    fig = go.Figure()
    for (label, value), color in zip(legs, palette):
        fig.add_trace(go.Bar(
            x=[value / total], y=["Cost structure"], name=label,
            orientation="h", marker_color=color,
            hovertemplate=(f"{label}: ${value:,.2f}/{unit} "
                           f"({value / total:.1%})<extra></extra>"),
        ))
    return terminal_layout(
        fig,
        barmode="stack", height=120,
        xaxis=dict(range=[0, 1], title=None, showticklabels=False,
                   showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.15,
                    traceorder="normal",
                    font=dict(size=11, color=theme.MUTED)),
        margin=dict(t=10, b=12, l=10, r=10),
    )


def compute(inputs: CostInputs, route: Route, profile: CommodityProfile,
            mode: str) -> NetbackResult:
    return compute_netback(inputs, route, profile, mode=mode)


def _route_label(route: Route) -> str:
    return (f"{route.load_port} → {route.discharge_port} "
            f"({route.vessel_type}, {route.transit_days:g} d)")
