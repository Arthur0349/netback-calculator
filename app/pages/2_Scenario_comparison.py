import plotly.graph_objects as go
import streamlit as st

import theme
from ui_helpers import (MODE_LABELS, SCENARIO_PALETTE, commodity_selectbox,
                        compute, get_provider, seed_inputs, terminal_layout)

st.set_page_config(page_title="Scenario comparison — Netback Calculator",
                   page_icon="⚖️", layout="wide")
theme.inject()

provider = get_provider()
theme.ticker(provider)

st.title("Scenario comparison")
st.caption("Compare routes or cargoes side by side on the resulting netback — "
           "the arbitrage view a trader uses to pick between outlets.")

with st.sidebar:
    st.header("Setup")
    mode = st.radio("Calculation mode", list(MODE_LABELS),
                    format_func=MODE_LABELS.get, key="cmp_mode")
    n_scenarios = st.slider("Scenarios", min_value=2, max_value=3, value=2)

scenarios = []
columns = st.columns(n_scenarios)
for i, col in enumerate(columns):
    with col:
        st.subheader(f"Scenario {chr(65 + i)}")
        commodity = commodity_selectbox(provider, st, key=f"cmp_commodity_{i}")
        profile = provider.get_commodity_profile(commodity)

        route_ids = provider.list_routes(commodity)
        if not route_ids:
            st.warning("No reference routes/defaults for this commodity yet — "
                       "use the Calculator page with manual inputs.")
            continue
        route_id = st.selectbox(
            "Route", route_ids, key=f"cmp_route_{i}_{commodity}",
            format_func=lambda rid: (
                lambda r: f"{r.load_port} → {r.discharge_port} ({r.vessel_type})"
            )(provider.get_route(rid)),
        )

        seed = seed_inputs(provider, commodity, route_id)
        k = f"cmp_{i}_{commodity}_{route_id}"
        price = st.number_input(f"Base price (USD/{profile.unit})",
                                min_value=0.01, value=float(seed["price_basis"]),
                                key=f"{k}_price")
        quantity = st.number_input(f"Quantity ({profile.unit})", min_value=1.0,
                                   value=float(seed["quantity"]), step=1000.0,
                                   key=f"{k}_qty")

        inputs = provider.get_default_cost_inputs(commodity, route_id,
                                                  price_basis=price,
                                                  quantity=quantity)
        route = provider.get_route(route_id)
        result = compute(inputs, route, profile, mode)

        result_label = result.breakdown[-1][0]
        theme.metric_cards([
            {"label": result_label, "value": f"${result.result_price:,.2f}",
             "unit": profile.unit, "accent": True,
             "delta": (f"{result.result_price - result.base_price:+,.2f} "
                       "vs base")},
        ])
        scenarios.append((f"{chr(65 + i)} — {profile.name}", profile, result))

if len(scenarios) >= 2:
    st.divider()
    st.subheader("Side-by-side breakdown (USD/unit)")

    components = ["Freight", "Insurance", "Financing", "Port fees",
                  "Commission", "Quality adj."]
    fig = go.Figure()
    # Values on hover only: printed labels overlap once 3 scenarios share
    # a component group.
    for (name, _profile, result), color in zip(scenarios, SCENARIO_PALETTE):
        fig.add_trace(go.Bar(
            name=name, x=components,
            y=[result.freight_cost, result.insurance_cost,
               result.financing_cost, result.port_fees_total,
               result.commission_cost, result.quality_adjustment],
            marker_color=color,
            hovertemplate="%{y:,.2f} USD/unit<extra>%{fullData.name}</extra>",
        ))
    terminal_layout(fig, barmode="group", bargroupgap=0.12,
                    yaxis_title="USD/unit", height=420,
                    legend=dict(orientation="h", yanchor="bottom", y=1.05,
                                font=dict(size=11)),
                    margin=dict(t=40, b=40))
    st.plotly_chart(fig, width="stretch")

    st.caption("Units differ across commodities (dmt vs bbl) — compare "
               "scenarios of the same commodity for a like-for-like read.")
