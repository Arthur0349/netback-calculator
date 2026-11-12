import streamlit as st

import theme
from maps import Lane, map_legend, responsive_map
from netback.core.arbitrage import rank_outlets
from ui_helpers import (compute, freight_unit, money,
                        ordered_commodities, route_label, setup_page)

st.set_page_config(page_title="Netback Calculator", page_icon="🚢",
                   layout="wide")
theme.inject()
provider = setup_page("home")

st.title("Netback Calculator")
theme.subtitle("Where does a physical cargo earn the most, and what does "
               "that answer hang on?")

st.markdown(
    "A pricing engine for physical commodity trades. From a delivered sale "
    "price it works **backward** to the FOB netback at the load port, "
    "deducting freight, insurance, financing, port fees and quality "
    "adjustments leg by leg; or **forward** from a FOB price to the delivered "
    "cost. The Incoterm decides which legs apply. Concentrates are valued "
    "from their assays: payable metals, TC/RC, penalties."
)

# --- snapshot from the engine: every reference cargo, every outlet ---------------

cargoes = [c for c in ordered_commodities(provider) if provider.list_routes(c)]
snapshot = {}
for key in cargoes:
    prices = provider.get_metal_prices(key)
    results, by_route, quantity = {}, {}, 0.0
    for rid in provider.list_routes(key):
        inputs = provider.get_default_cost_inputs(key, rid)
        quantity = inputs.quantity
        route = provider.get_route(rid)
        results[route_label(route)] = compute(
            inputs, route, provider.get_commodity_profile(key, rid),
            "netback", prices)
        by_route[route_label(route)] = (rid, route, inputs)
    snapshot[key] = (rank_outlets(results, quantity), by_route, quantity)

st.subheader("Reference cargoes")
commodity = st.pills(
    "Reference cargo", cargoes, default=cargoes[0], key="home_cargo",
    format_func=lambda k: provider.get_commodity_profile(k).name,
    label_visibility="collapsed") or cargoes[0]

base_profile = provider.get_commodity_profile(commodity)
ranking, _, quantity = snapshot[commodity]
best = ranking[0]
unit = base_profile.unit

cards = [
    {"label": "Best outlet", "value": best.outlet, "accent": True,
     "delta": f"{base_profile.name}, {quantity:,.0f} {unit}"},
    {"label": "FOB netback", "value": money(best.netback), "unit": unit,
     "delta": f"{money(best.delivered_price)} delivered"},
]
if len(ranking) > 1:
    cards.append(
        {"label": "Lead over #2", "value": money(best.cushion), "unit": unit,
         "delta": f"${best.cushion * quantity:,.0f} on the cargo",
         "delta_kind": "pos"})
theme.metric_cards(cards)

lanes = []
for key in cargoes:
    profile = provider.get_commodity_profile(key)
    key_ranking, by_route, _ = snapshot[key]
    for r in key_ranking:
        rid, route, inputs = by_route[r.outlet]
        in_focus = key == commodity
        lanes.append(Lane(
            load_port=route.load_port, discharge_port=route.discharge_port,
            path=provider.get_route_path(rid),
            rank=("best" if r.rank == 1 else "focus") if in_focus else "dim",
            hover=(f"<b>{r.outlet}</b>  #{r.rank} of {len(key_ranking)}<br>"
                   f"FOB netback {money(r.netback)}/{profile.unit}<br>"
                   f"Freight {money(inputs.freight_rate_per_unit)}/"
                   f"{freight_unit(profile)} · {route.vessel_type} · "
                   f"{route.transit_days:g} d")))
responsive_map(lanes, key="home_map")
st.markdown(map_legend("Best outlet", "Other outlets of this cargo",
                       "Other reference cargoes"), unsafe_allow_html=True)

st.subheader("Tools")
st.markdown('<div class="nb-panels">' + "".join([
    theme.panel(
        "Calculator →",
        "One voyage, end to end: waterfall from price (or payable metals) to "
        "FOB netback, sensitivities, breakeven freight and price, deal "
        "margin, one-page PDF trade sheet, shareable link.",
        href="Calculator"),
    theme.panel(
        "Arbitrage matrix →",
        "One cargo, every outlet: each destination's own price or smelter "
        "terms, ranked on FOB netback, with the lead over the runner-up and "
        "the freight headroom before the ranking flips.",
        href="Arbitrage"),
    theme.panel(
        "Freight →",
        "Where a freight rate comes from: a voyage estimate from hire, "
        "bunkers, port and canal costs to USD per tonne, and back from a "
        "quoted rate to the TCE it pays the ship.",
        href="Freight"),
    theme.panel(
        "Methodology →",
        "Every formula and convention: Incoterm legs, wet/dry freight, "
        "insured value, payables and deductions, TC/RC units, penalties, "
        "the voyage estimate. No black box.",
        href="Methodology"),
]) + "</div>", unsafe_allow_html=True)

st.subheader("Coverage")
rows = []
for key in ordered_commodities(provider):
    profile = provider.get_commodity_profile(key)
    routes = [provider.get_route(rid) for rid in provider.list_routes(key)]
    pricing = ("Assays: payables, TC/RC, penalties" if profile.concentrate_terms
               else "Index price + quality escalators")
    rows.append([
        profile.name, pricing,
        ", ".join(dict.fromkeys(r.load_port for r in routes)) or "config skeleton",
        ", ".join(dict.fromkeys(r.discharge_port for r in routes)) or "manual inputs",
    ])
theme.data_table(["Commodity", "Pricing", "Load ports", "Outlets"], rows,
                 numeric_from=99, highlight=None)

st.caption(
    f"{provider.data_note} Destination differentials and non-benchmark "
    "TC/RCs are illustrative. Every input is editable. The engine is "
    "commodity-agnostic: a commodity is a configuration profile, not code. "
    "Source: github.com/Arthur0349/netback-calculator"
)
