import streamlit as st

import theme
from netback.core.arbitrage import rank_outlets
from ui_helpers import (compute, get_provider, money, ordered_commodities,
                        route_label)

st.set_page_config(page_title="Netback Calculator", page_icon="🚢",
                   layout="wide")
theme.inject()
provider = get_provider()
theme.ticker(provider)

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

# --- live snapshot from the engine: the default cargo, every outlet --------------

commodity = ordered_commodities(provider)[0]
base_profile = provider.get_commodity_profile(commodity)
prices = provider.get_metal_prices(commodity)
results, quantity = {}, 0.0
for rid in provider.list_routes(commodity):
    inputs = provider.get_default_cost_inputs(commodity, rid)
    quantity = inputs.quantity
    route = provider.get_route(rid)
    results[route_label(route)] = compute(
        inputs, route, provider.get_commodity_profile(commodity, rid),
        "netback", prices)
ranking = rank_outlets(results, quantity)
best = ranking[0]
unit = base_profile.unit

st.subheader(f"Reference cargo: {base_profile.name}, {quantity:,.0f} {unit}")
theme.metric_cards([
    {"label": "Best outlet", "value": best.outlet, "accent": True,
     "delta": f"of {len(ranking)} outlets ranked"},
    {"label": "FOB netback", "value": money(best.netback), "unit": unit,
     "delta": f"{money(best.delivered_price)} delivered"},
    {"label": "Lead over #2", "value": money(best.cushion), "unit": unit,
     "delta": f"${best.cushion * quantity:,.0f} on the cargo",
     "delta_kind": "pos"},
])

st.subheader("Tools")
col1, col2, col3 = st.columns(3)
col1.markdown(theme.panel(
    "Calculator →",
    "One voyage, end to end: waterfall from price (or payable metals) to "
    "FOB netback, sensitivities, breakeven freight and price, deal margin, "
    "one-page PDF trade sheet.",
    href="Calculator"), unsafe_allow_html=True)
col2.markdown(theme.panel(
    "Arbitrage matrix →",
    "One cargo, every outlet: each destination's own price or smelter terms, "
    "ranked on FOB netback, with the lead over the runner-up and the freight "
    "headroom before the ranking flips.",
    href="Arbitrage"), unsafe_allow_html=True)
col3.markdown(theme.panel(
    "Methodology →",
    "Every formula and convention: Incoterm legs, wet/dry freight, insured "
    "value, payables and deductions, TC/RC units, penalties. No black box.",
    href="Methodology"), unsafe_allow_html=True)

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
    f"Reference prices, freight and port fees are static, indicative figures "
    f"as of {provider.as_of}; destination differentials and non-benchmark "
    "TC/RCs are illustrative. Every input is editable. The engine is "
    "commodity-agnostic: a commodity is a configuration profile, not code. "
    "Source: github.com/Arthur0349/netback-calculator"
)
