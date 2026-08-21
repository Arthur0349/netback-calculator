import streamlit as st

st.set_page_config(page_title="Netback Calculator", page_icon="🚢", layout="wide")

st.title("🚢 Netback Calculator")
st.caption("Freight-rate netback and landed-cost engine for bulk and tanker trades")

st.markdown("""
Given a delivered sale price (CIF/DES/DAP), this tool works **backward** to the
FOB netback at the load port by deducting freight, insurance, financing cost,
port fees and quality adjustments — or **forward** from a FOB price to the
landed cost for a buyer. Both directions run through the same cost engine;
only the sign of the cost legs flips.

The engine is **commodity-agnostic**: each commodity is a configuration
profile (unit, benchmark spec, quality-adjustment formula) injected into the
engine, not hard-coded logic. Reference data ships for iron ore and crude oil,
with a spodumene (lithium) profile included as a config-only skeleton to show
that adding a commodity needs no code change.
""")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Netback (backward)")
    st.markdown("CIF sale price → deductions → **FOB netback**. "
                "The trader's calculation: compare several outlets and pick "
                "the most profitable one.")
with col2:
    st.subheader("Landed cost (forward)")
    st.markdown("FOB price → additions → **delivered cost**. "
                "The buyer's calculation: compare several origins on an "
                "equal delivered basis.")

st.divider()
st.page_link("pages/1_Calculator.py", label="**Calculator** — single-voyage "
             "netback / landed cost with waterfall breakdown", icon="🧮")
st.page_link("pages/2_Scenario_comparison.py", label="**Scenario comparison** — "
             "compare routes or cargoes side by side", icon="⚖️")
st.page_link("pages/3_Methodology.py", label="**Methodology** — formulas and "
             "assumptions behind every cost leg", icon="📖")

st.divider()
st.caption("Reference prices and freight rates are static, order-of-magnitude "
           "indicative figures. Live market data is a planned extension behind "
           "the same provider interface.")
