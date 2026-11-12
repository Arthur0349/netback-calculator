import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import theme
from netback.core.arbitrage import rank_outlets
from netback.models.schemas import DELIVERY_TERM_LEGS, CostInputs
from ui_helpers import (commodity_selectbox, compute, freight_unit, get_provider,
                        metal_price_inputs, quality_inputs, route_label,
                        seed_inputs, terminal_layout)

st.set_page_config(page_title="Arbitrage — Netback Calculator",
                   page_icon="🧭", layout="wide")
theme.inject()

provider = get_provider()
theme.ticker(provider)

st.title("Arbitrage matrix")
st.caption("One cargo, every outlet: each destination's own price or smelter "
           "terms, freight and port costs, netted back to FOB and ranked. "
           "The question a trader asks before fixing a ship: where does this "
           "cargo earn the most at the load port?")

ALL = "All origins"

with st.sidebar:
    st.header("Cargo")
    commodity = commodity_selectbox(provider, st, key="arb_commodity")
    profile = provider.get_commodity_profile(commodity)
    is_concentrate = profile.concentrate_terms is not None
    route_ids = provider.list_routes(commodity)

    if not route_ids:
        st.warning("No reference routes for this commodity yet.")
        st.stop()

    by_origin: dict[str, list[str]] = {}
    for rid in route_ids:
        by_origin.setdefault(provider.get_route(rid).load_port, []).append(rid)
    origins = sorted(by_origin, key=lambda o: -len(by_origin[o]))
    origin = st.selectbox("Load port", origins + [ALL], key=f"arb_origin_{commodity}")
    shown = route_ids if origin == ALL else by_origin[origin]

    k = f"arb_{commodity}_"
    seed = seed_inputs(provider, commodity, shown[0])
    quantity = st.number_input(f"Quantity ({profile.unit})", min_value=1.0,
                               value=float(seed["quantity"]), step=1000.0,
                               key=f"{k}qty")
    insurance = st.number_input("Insurance rate (% of insured value)", min_value=0.0,
                                value=float(seed["insurance_rate_pct"]), step=0.05,
                                format="%.2f", key=f"{k}ins")
    financing = st.number_input("Financing rate (annual %)", min_value=0.0,
                                value=float(seed["financing_rate_annual_pct"]),
                                step=0.25, format="%.2f", key=f"{k}fin")
    terms_days = st.number_input("Payment terms (days)", min_value=0.0,
                                 value=float(seed["payment_terms_days"]), step=5.0,
                                 key=f"{k}terms")
    commission = st.number_input("Commission (%)", min_value=0.0,
                                 value=float(seed["commission_pct"]), step=0.05,
                                 format="%.2f", key=f"{k}comm")
    actual_quality = quality_inputs(profile, seed, st, key_prefix=k)
    metal_prices = (metal_price_inputs(profile, provider.get_metal_prices(commodity),
                                       st, key_prefix=k)
                    if is_concentrate else None)

# --- per-outlet terms, editable -----------------------------------------------

st.subheader("Outlets")
st.caption("Defaults come from the reference data; edit any cell. "
           + ("TC in USD/dmt (negative = smelter pays), RC in USD per payable "
              "lb for base metals."
              if is_concentrate else
              f"Delivered price in USD/{profile.unit} on the outlet's term."))

pct_payables = ([p for p in profile.concentrate_terms.payables if p.unit == "pct"]
                if is_concentrate else [])
rows = []
for rid in shown:
    route = provider.get_route(rid)
    defaults = provider.get_default_cost_inputs(commodity, rid)
    row = {"Outlet": route_label(route), "Term": defaults.delivery_term}
    if is_concentrate:
        terms = provider.get_commodity_profile(commodity, rid).concentrate_terms
        row["TC"] = terms.treatment_charge
        for p in terms.payables:
            if p.unit == "pct":
                row[f"RC {p.element}"] = p.refining_charge
    else:
        row["Delivered price"] = defaults.price_basis
    row[f"Freight (USD/{freight_unit(profile)})"] = defaults.freight_rate_per_unit
    row["Load fee"] = defaults.load_port_fee_per_unit
    row["Discharge fee"] = defaults.discharge_port_fee_per_unit
    rows.append(row)

edited = st.data_editor(
    pd.DataFrame(rows), hide_index=True, width="stretch",
    key=f"arb_editor_{commodity}_{origin}", disabled=["Outlet"],
    column_config={
        "Term": st.column_config.SelectboxColumn(
            options=list(DELIVERY_TERM_LEGS), required=True),
        **{c: st.column_config.NumberColumn(format="%.3f")
           for c in [f"RC {p.element}" for p in pct_payables]},
    },
)

# --- compute and rank -----------------------------------------------------------

results = {}
for rid, (_, row) in zip(shown, edited.iterrows()):
    route = provider.get_route(rid)
    outlet_profile = provider.get_commodity_profile(commodity, rid)
    if is_concentrate:
        terms = outlet_profile.concentrate_terms
        payables = [p.model_copy(update={"refining_charge": float(row[f"RC {p.element}"])})
                    if p.unit == "pct" else p for p in terms.payables]
        outlet_profile = outlet_profile.model_copy(update={
            "concentrate_terms": terms.model_copy(update={
                "treatment_charge": float(row["TC"]), "payables": payables})})
        price = 1.0                         # replaced by the valuation
    else:
        price = float(row["Delivered price"])
    inputs = CostInputs(
        quantity=quantity, price_basis=max(price, 0.01),
        freight_rate_per_unit=float(row[f"Freight (USD/{freight_unit(profile)})"]),
        insurance_rate_pct=insurance, financing_rate_annual_pct=financing,
        payment_terms_days=terms_days,
        load_port_fee_per_unit=float(row["Load fee"]),
        discharge_port_fee_per_unit=float(row["Discharge fee"]),
        actual_quality=actual_quality, commission_pct=commission,
        delivery_term=row["Term"],
    )
    results[row["Outlet"]] = compute(inputs, route, outlet_profile, "netback",
                                     metal_prices)

ranking = rank_outlets(results, quantity)
best = ranking[0]
unit = profile.unit

st.divider()
cards = [
    {"label": "Best outlet", "value": best.outlet.split(" (")[0], "unit": "",
     "accent": True},
    {"label": "Best FOB netback", "value": f"${best.netback:,.2f}", "unit": unit},
]
if len(ranking) > 1:
    cards += [
        {"label": "Cushion vs #2", "value": f"${best.cushion:,.2f}", "unit": unit,
         "delta": "netback can drop this much before #2 wins"},
        {"label": "Cushion on the cargo", "value": f"${best.cushion * quantity:,.0f}",
         "unit": "", "delta": f"{quantity:,.0f} {unit}"},
    ]
theme.metric_cards(cards)

# netback ladder
names = [r.outlet.split(" (")[0] for r in ranking][::-1]
values = [r.netback for r in ranking][::-1]
colors = [theme.CHART_TOTAL if r.rank == 1 else "#587FA8" for r in ranking][::-1]
lo, hi = min(values), max(values)
pad = (hi - lo) * 0.6 or hi * 0.05
fig = go.Figure(go.Bar(
    x=values, y=names, orientation="h", marker_color=colors,
    text=[f"{v:,.2f}" + ("" if r.rank == 1 else f"  ({r.spread_vs_best:+,.2f})")
          for v, r in zip(values, ranking[::-1])],
    textposition="outside",
    textfont=dict(family=theme.MONO, color=theme.TEXT, size=11),
    hovertemplate=f"%{{y}}<br>%{{x:,.2f}} USD/{unit}<extra></extra>",
))
terminal_layout(fig, height=110 + 60 * len(ranking), showlegend=False,
                xaxis=dict(range=[lo - pad, hi + pad * 0.6],
                           title=f"FOB netback, USD/{unit}"),
                yaxis=dict(automargin=True, tickfont=dict(family=theme.SANS,
                                                          color=theme.TEXT, size=12)),
                margin=dict(t=20, b=40, l=10, r=10))
st.plotly_chart(fig, width="stretch")

theme.data_table(
    ["#", "Outlet", "Term", f"Delivered USD/{unit}", "Freight", "Other costs",
     "Quality", "FOB netback", "vs best", "Cargo vs best USD"],
    [[str(r.rank), r.outlet, r.delivery_term, f"{r.delivered_price:,.2f}",
      f"{r.freight:,.2f}", f"{r.other_costs:,.2f}", f"{r.quality_adjustment:+,.2f}",
      f"{r.netback:,.2f}", f"{r.spread_vs_best:+,.2f}",
      f"{r.cargo_spread_vs_best:+,.0f}"] for r in ranking],
)

notes = ["Freight is shown per dry unit." if profile.freight_moisture_key else ""]
if origin == ALL and len(by_origin) > 1:
    notes.append("Several load ports: each netback is FOB at its own port, so "
                 "the ranking compares origins as well as outlets.")
if is_concentrate:
    notes.append("Delivered = net invoice value under each smelter's terms. "
                 "Non-benchmark TC/RCs in the reference data are illustrative.")
else:
    notes.append("Destination differentials in the reference data are "
                 "illustrative assumptions; overwrite them with live quotes.")
st.caption(" ".join(n for n in notes if n))
