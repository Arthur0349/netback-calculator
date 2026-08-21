import streamlit as st

import theme
from ui_helpers import (MODE_LABELS, commodity_selectbox, compute,
                        cost_inputs_form, cost_share_figure, get_provider,
                        result_metric_cards, route_inputs, seed_inputs,
                        waterfall_figure)

st.set_page_config(page_title="Calculator — Netback Calculator",
                   page_icon="🧮", layout="wide")
theme.inject()

provider = get_provider()
theme.ticker(provider)

with st.sidebar:
    st.header("Inputs")
    commodity = commodity_selectbox(provider, st)
    profile = provider.get_commodity_profile(commodity)

    mode = st.radio("Calculation mode", list(MODE_LABELS),
                    format_func=MODE_LABELS.get, key="mode")

    st.subheader("Voyage")
    route_id, route = route_inputs(provider, commodity, st)

    st.subheader("Costs")
    seed = seed_inputs(provider, commodity, route_id)
    inputs = cost_inputs_form(profile, seed, st,
                              key_prefix=f"{commodity}_{route_id}_")

st.title(f"{profile.name} — "
         f"{'netback' if mode == 'netback' else 'landed cost'}")
st.caption(f"{route.load_port} → {route.discharge_port} · "
           f"{route.vessel_type} · {route.transit_days:g} days transit · "
           f"{inputs.quantity:,.0f} {profile.unit}")

result = compute(inputs, route, profile, mode)

result_metric_cards(result, profile.unit)

st.plotly_chart(waterfall_figure(result, profile.unit), width="stretch")

st.subheader("Cost structure")
st.plotly_chart(cost_share_figure(result, profile.unit), width="stretch")

with st.expander("Full breakdown table"):
    theme.data_table(
        ["Component", f"USD/{profile.unit}", "Total USD"],
        [[label, f"{value:,.2f}", f"{value * inputs.quantity:,.0f}"]
         for label, value in result.breakdown],
    )
