import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import theme
from maps import Lane, map_legend, responsive_map
from netback.core.arbitrage import rank_outlets
from netback.models.schemas import DELIVERY_TERM_LEGS, CostInputs
from ui_helpers import (NEUTRAL_BAR, chart, commodity_selectbox, compute,
                        freight_unit, metal_price_inputs, money,
                        quality_inputs, route_label, seed_inputs,
                        setup_page, source_tag, terminal_layout)

st.set_page_config(page_title="Arbitrage · Netback Calculator",
                   page_icon="🚢", layout="wide")
theme.inject()

provider = setup_page("arbitrage")

ALL = "All load ports"

# --- cargo (sidebar) -------------------------------------------------------------

with st.sidebar:
    commodity = commodity_selectbox(provider, st, key="arb_commodity")
    profile = provider.get_commodity_profile(commodity)
    is_concentrate = profile.concentrate_terms is not None
    route_ids = provider.list_routes(commodity)

if not route_ids:
    st.title("Arbitrage matrix")
    st.info(f"{profile.name} is a configuration skeleton: it has no reference "
            "outlets to rank yet. Price a single voyage with manual inputs on "
            "the Calculator page.")
    st.stop()

with st.sidebar:
    by_origin: dict[str, list[str]] = {}
    for rid in route_ids:
        by_origin.setdefault(provider.get_route(rid).load_port, []).append(rid)
    origins = sorted(by_origin, key=lambda o: (-len(by_origin[o]), o))
    choices = ([ALL] + origins) if len(origins) > 1 else origins
    origin = st.selectbox("Load port", choices, key=f"arb_origin_{commodity}")
    shown = route_ids if origin == ALL else by_origin[origin]

    k = f"arb_{commodity}_{source_tag()}_"
    seed = seed_inputs(provider, commodity, shown[0])
    cargo = st.expander("Cargo", expanded=True)
    quantity = cargo.number_input(f"Quantity ({profile.unit})", min_value=1.0,
                                  value=float(seed["quantity"]), step=1000.0,
                                  format="%.0f", key=f"{k}qty")
    actual_quality = quality_inputs(profile, seed, cargo, key_prefix=k)

    metal_prices = None
    if is_concentrate:
        metal_prices = metal_price_inputs(
            profile, provider.get_metal_prices(commodity),
            st.expander("Metal prices", expanded=True), key_prefix=k)

    costs = st.expander("Common cost assumptions", expanded=False)
    insurance = costs.number_input("Insurance (%)", min_value=0.0,
                                   value=float(seed["insurance_rate_pct"]),
                                   step=0.05, format="%.2f", key=f"{k}ins")
    financing = costs.number_input("Financing (% p.a.)", min_value=0.0,
                                   value=float(seed["financing_rate_annual_pct"]),
                                   step=0.25, format="%.2f", key=f"{k}fin")
    terms_days = costs.number_input("Payment terms (d)", min_value=0.0,
                                    value=float(seed["payment_terms_days"]),
                                    step=5.0, format="%.0f", key=f"{k}terms")
    commission = costs.number_input("Commission (%)", min_value=0.0,
                                    value=float(seed["commission_pct"]),
                                    step=0.05, format="%.2f", key=f"{k}comm")

unit = profile.unit
f_unit = freight_unit(profile)

st.title("Arbitrage matrix")
theme.subtitle(f"<b>{profile.name}</b> · {quantity:,.0f} {unit} · "
               f"{len(shown)} outlet{'s' if len(shown) > 1 else ''} · "
               "each netted back to FOB and ranked")

# --- per-outlet terms, editable ------------------------------------------------

pct_payables = ([p for p in profile.concentrate_terms.payables if p.unit == "pct"]
                if is_concentrate else [])
freight_col = f"Freight USD/{f_unit}"
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
    row[freight_col] = defaults.freight_rate_per_unit
    row["Load fee"] = defaults.load_port_fee_per_unit
    row["Discharge fee"] = defaults.discharge_port_fee_per_unit
    rows.append(row)

two_dp = st.column_config.NumberColumn(format="%.2f", min_value=0.0)
edited = st.data_editor(
    pd.DataFrame(rows), hide_index=True, width="stretch",
    key=f"arb_editor_{commodity}_{origin}_{source_tag()}", disabled=["Outlet"],
    column_config={
        "Outlet": st.column_config.TextColumn(width="medium"),
        "Term": st.column_config.SelectboxColumn(
            options=list(DELIVERY_TERM_LEGS), required=True, width="small",
            help="Incoterm of the delivered price."),
        "Delivered price": st.column_config.NumberColumn(
            format="%.2f", min_value=0.01, help=f"USD/{unit} on the outlet's term."),
        "TC": st.column_config.NumberColumn(
            format="%.2f", help=f"USD/{unit}. Negative = the smelter pays."),
        **{f"RC {p.element}": st.column_config.NumberColumn(
               format="%.3f", help="USD per payable lb.") for p in pct_payables},
        freight_col: two_dp, "Load fee": two_dp, "Discharge fee": two_dp,
    },
)
st.caption("Every cell is editable: overwrite the reference figures with "
           "your own quotes and the ranking updates.")

# --- compute and rank -----------------------------------------------------------

results, route_of, moisture_factor = {}, {}, 1.0
if profile.freight_moisture_key:
    moisture_factor = 1 - actual_quality[profile.freight_moisture_key] / 100
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
        freight_rate_per_unit=float(row[freight_col]),
        insurance_rate_pct=insurance, financing_rate_annual_pct=financing,
        payment_terms_days=terms_days,
        load_port_fee_per_unit=float(row["Load fee"]),
        discharge_port_fee_per_unit=float(row["Discharge fee"]),
        actual_quality=actual_quality, commission_pct=commission,
        delivery_term=row["Term"],
    )
    results[row["Outlet"]] = compute(inputs, route, outlet_profile, "netback",
                                     metal_prices)
    route_of[row["Outlet"]] = (rid, route)

ranking = rank_outlets(results, quantity)
best = ranking[0]

cards = [
    {"label": "Best outlet", "value": best.outlet, "accent": True,
     "delta": f"{best.delivery_term}, {money(best.delivered_price)}/{unit} delivered"},
    {"label": "FOB netback", "value": money(best.netback), "unit": unit,
     "delta": f"${best.netback * quantity / 1e6:,.2f}M on the cargo"},
]
if len(ranking) > 1:
    headroom = best.cushion * moisture_factor
    cards += [
        {"label": "Lead over #2", "value": money(best.cushion), "unit": unit,
         "delta": f"${best.cushion * quantity:,.0f} on the cargo",
         "delta_kind": "pos"},
        {"label": "Freight headroom", "value": money(headroom), "unit": f_unit,
         "delta": f"rise on {best.outlet.split(' → ')[1]} freight before "
                  f"{ranking[1].outlet.split(' → ')[1]} wins"},
    ]
theme.metric_cards(cards)

# netback ladder
if len(ranking) > 1:
    ordered = ranking[::-1]
    values = [r.netback for r in ordered]
    lo, hi = min(values), max(values)
    pad = (hi - lo) or hi * 0.05
    fig = go.Figure(go.Bar(
        x=values, y=[r.outlet for r in ordered], orientation="h",
        marker_color=[theme.CHART_TOTAL if r.rank == 1 else NEUTRAL_BAR
                      for r in ordered],
        text=[f"{r.netback:,.2f}" for r in ordered],
        textposition="inside", insidetextanchor="end", textangle=0,
        textfont=dict(family=theme.MONO, color="#0A0E17", size=12),
        hovertemplate=f"%{{y}}<br>%{{x:,.2f}} USD/{unit}<extra></extra>",
    ))
    terminal_layout(fig, height=96 + 52 * len(ranking), showlegend=False,
                    xaxis=dict(range=[lo - pad, hi + pad * 0.08], nticks=5,
                               title=f"FOB netback, USD/{unit}",
                               title_font=dict(size=11, color=theme.MUTED)),
                    yaxis=dict(automargin=True,
                               tickfont=dict(family=theme.SANS, color=theme.TEXT,
                                             size=12)),
                    margin=dict(t=12, b=44, l=8, r=8))
    chart(fig)

st.subheader("Ranking")
headers = ["#", "Outlet", "Term", "Delivered", "Freight", "Other costs", "Quality",
           "FOB netback", "vs best", "Cargo vs best"]
table = [[str(r.rank), r.outlet, r.delivery_term, f"{r.delivered_price:,.2f}",
          f"{-r.freight:,.2f}", f"{-r.other_costs:,.2f}",
          f"{r.quality_adjustment:+,.2f}", f"{r.netback:,.2f}",
          "best" if r.rank == 1 else f"{r.spread_vs_best:+,.2f}",
          "" if r.rank == 1 else f"{r.cargo_spread_vs_best:+,.0f}"] for r in ranking]
signed = (6, 8, 9)
if is_concentrate:          # assays are priced in the delivered value
    headers = headers[:6] + headers[7:]
    table = [row[:6] + row[7:] for row in table]
    signed = (7, 8)
theme.data_table(headers, table, numeric_from=3, highlight=0, signed_cols=signed)

st.subheader("Trade lanes")
responsive_map([
    Lane(load_port=route_of[r.outlet][1].load_port,
         discharge_port=route_of[r.outlet][1].discharge_port,
         path=provider.get_route_path(route_of[r.outlet][0]),
         rank="best" if r.rank == 1 else "focus",
         hover=(f"<b>{r.outlet}</b>  #{r.rank} of {len(ranking)}<br>"
                f"FOB netback {money(r.netback)}/{unit}<br>"
                f"{route_of[r.outlet][1].vessel_type} · "
                f"{route_of[r.outlet][1].transit_days:g} d"
                + ("" if r.rank == 1 else
                   f" · {money(r.spread_vs_best, signed=True)} vs best")))
    for r in ranking], key="arb_map", height=400)
st.markdown(map_legend("Best outlet", "Other outlets"), unsafe_allow_html=True)

notes = [f"USD/{unit}; freight per dry unit." if profile.freight_moisture_key
         else f"USD/{unit}."]
if origin == ALL:
    notes.append("Several load ports: each netback is FOB at its own port, so "
                 "the ranking compares origins as well as outlets (inland "
                 "logistics to the port not included).")
notes.append("Delivered = net invoice value under each smelter's terms; "
             "non-benchmark TC/RCs in the reference data are illustrative."
             if is_concentrate else
             "Destination price differentials in the reference data are "
             "illustrative; overwrite them with live quotes.")
st.caption(" ".join(notes))
