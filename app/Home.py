import streamlit as st

import theme
from ui_helpers import get_provider

st.set_page_config(page_title="Netback Calculator", page_icon="🚢",
                   layout="wide")
theme.inject()
theme.ticker(get_provider())

st.title("Netback Calculator")
st.caption("FOB netback and landed-cost engine for bulk and tanker trades")

st.markdown(
    "From a delivered sale price (CFR/CIF/DAP/DPU), work **backward** to the FOB "
    "netback at the load port: freight, insurance, financing, port fees and "
    "quality adjustments, deducted leg by leg. Or run the same engine "
    "**forward**, FOB price to delivered cost. One engine, two directions: "
    "the Incoterm decides which legs apply, the mode decides their sign."
)

st.divider()

col1, col2 = st.columns(2)
col1.markdown(theme.panel(
    "Netback · backward",
    "Delivered sale price → deductions → <b>FOB netback</b>.<br>"
    "The trader's calculation: compare several outlets, "
    "pick the most profitable one.",
), unsafe_allow_html=True)
col2.markdown(theme.panel(
    "Landed cost · forward",
    "FOB price → additions → <b>delivered cost</b>.<br>"
    "The buyer's calculation: compare several origins "
    "on an equal delivered basis.",
), unsafe_allow_html=True)

st.divider()

st.markdown(
    "The engine is **commodity-agnostic**: each commodity is a configuration "
    "profile (unit, benchmark spec, quality-adjustment formula) injected into "
    "the engine, not hard-coded logic. Iron ore, bauxite and crude oil "
    "ship fully built; copper concentrate is valued from its assays "
    "(payables, TC/RC, penalties); spodumene is a config-only skeleton proving that a new commodity "
    "is a data edit, not a code change."
)

st.divider()

st.page_link("pages/1_Calculator.py",
             label="**Calculator** — single-voyage netback / landed cost "
                   "with waterfall breakdown")
st.page_link("pages/2_Arbitrage.py",
             label="**Arbitrage matrix** — one cargo, every outlet, ranked on "
                   "FOB netback with the cushion vs the runner-up")
st.page_link("pages/3_Scenario_comparison.py",
             label="**Scenario comparison** — routes or cargoes side by "
                   "side, cost leg by cost leg")
st.page_link("pages/4_Methodology.py",
             label="**Methodology** — formulas and assumptions behind every "
                   "cost leg")

st.divider()
st.caption("Reference prices and freight rates are static, "
           "order-of-magnitude indicative figures. Live market data is a "
           "planned extension behind the same provider interface.")
