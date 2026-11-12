import plotly.graph_objects as go
import streamlit as st

import theme
from case_state import push_to_calculator
from netback.core.voyage import (VoyageInputs, bunker_delta, freight_from_hire,
                                 tce_from_freight, voyage_sensitivity)
from ui_helpers import (chart, money, ordered_commodities, route_label,
                        setup_page,
                        share_bar_figure, source_tag, terminal_layout,
                        tornado_figure)

st.set_page_config(page_title="Freight · Netback Calculator",
                   page_icon="🚢", layout="wide")
theme.inject()

provider = setup_page("freight")

SOLVE_LABELS = {"freight": "Freight rate", "tce": "TCE"}
SOLVE_HELP = ("**Freight rate**: the rate that pays a given daily hire on top "
              "of the voyage costs (the charterer's build-up).\n\n**TCE**: "
              "what a quoted rate pays the ship per day once voyage costs "
              "are out (the owner's view).")

# --- voyage (sidebar) -----------------------------------------------------------

routes = {}
for commodity in ordered_commodities(provider):
    for rid in provider.list_routes(commodity):
        routes[rid] = commodity

last = st.session_state.get("_calc_last", {})
if st.session_state["_entered"] and last.get("r") in routes:
    st.session_state["frt_route"] = last["r"]      # follow the Calculator

with st.sidebar:
    route_id = st.selectbox(
        "Route", list(routes), key="frt_route",
        format_func=lambda r: route_label(provider.get_route(r)))
    commodity = routes[route_id]
    route = provider.get_route(route_id)
    vessel = provider.get_vessel(route.vessel_type)
    ref = provider.get_voyage_inputs(route_id)
    cargo_unit = vessel["cargo_unit"]
    ref_rate = provider.get_freight_rate(route)
    # the rate on the Calculator, when it is looking at this same route
    try:
        quoted_seed = float(last["f"]) if last.get("r") == route_id else ref_rate
    except (KeyError, ValueError):
        quoted_seed = ref_rate
    k = f"frt_{route_id}_{source_tag()}_"

    solve = st.radio("Solve for", list(SOLVE_LABELS), horizontal=True,
                     format_func=SOLVE_LABELS.get, key="frt_solve",
                     help=SOLVE_HELP)

    market = st.expander("Market", expanded=True)
    if solve == "freight":
        hire = market.number_input(
            "Hire (USD/day)", min_value=0.0, step=500.0, format="%.0f",
            value=float(round(max(tce_from_freight(ref, ref_rate).tce, 0.0))),
            key=f"{k}hire",
            help="Time-charter rate of the ship. Seeded with the TCE implied "
                 "by the reference freight rate for this route.")
        quoted = None
    else:
        quoted = market.number_input(
            f"Quoted freight (USD/{cargo_unit})", min_value=0.0, format="%.2f",
            value=float(quoted_seed), key=f"{k}quoted",
            help="The voyage rate offered by the market. Seeded with the "
                 "rate on the Calculator when it is on this route.")
        hire = None
    bunker_price = market.number_input(
        "Bunker price (USD/t)", min_value=0.0, step=10.0, format="%.0f",
        value=float(ref.bunker_price), key=f"{k}bunker",
        help="VLSFO, one grade for the whole voyage.")
    commission = market.number_input(
        "Commission %", min_value=0.0, max_value=20.0, step=0.25, format="%.2f",
        value=float(ref.commission_pct), key=f"{k}comm",
        help="Address and brokerage commission on the gross freight.")

    leg = st.expander("Voyage", expanded=True)
    distance = leg.number_input(
        "Laden distance (nm)", min_value=1.0, step=100.0, format="%.0f",
        value=float(ref.distance_nm), key=f"{k}nm")
    left, right = leg.columns(2)
    ballast_pct = left.number_input(
        "Ballast %", min_value=0.0, max_value=200.0, step=10.0,
        format="%.0f", value=float(ref.ballast_pct), key=f"{k}ballast",
        help="Ballast distance charged to this voyage, as % of the laden "
             "distance. 100 = round voyage back to the load port.")
    sea_margin = right.number_input(
        "Margin %", min_value=0.0, max_value=50.0, step=1.0, format="%.0f",
        value=float(ref.sea_margin_pct), key=f"{k}margin",
        help="Sea margin: extra sea time for weather and currents.")
    left, right = leg.columns(2)
    days_load = left.number_input(
        "Load days", min_value=0.0, step=0.5, format="%.1f",
        value=float(ref.port_days_load), key=f"{k}dl")
    days_disch = right.number_input(
        "Disch. days", min_value=0.0, step=0.5, format="%.1f",
        value=float(ref.port_days_discharge), key=f"{k}dd")
    left, right = leg.columns(2)
    cost_load = left.number_input(
        "Load port $", min_value=0.0, step=10000.0, format="%.0f",
        value=float(ref.port_cost_load), key=f"{k}cl")
    cost_disch = right.number_input(
        "Disch. port $", min_value=0.0, step=10000.0, format="%.0f",
        value=float(ref.port_cost_discharge), key=f"{k}cd")
    left, right = leg.columns(2)
    canal_days = left.number_input(
        "Canal days", min_value=0.0, step=0.5, format="%.1f",
        value=float(ref.canal_days), key=f"{k}cdays")
    canal_dues = right.number_input(
        "Canal dues $", min_value=0.0, step=10000.0, format="%.0f",
        value=float(ref.canal_dues), key=f"{k}cdues")
    leg.caption("Port days include waiting for a berth. Port costs are the "
                "disbursements per call, lumpsum.")

    ship = st.expander(f"Vessel: {route.vessel_type}", expanded=False)
    intake = ship.number_input(
        f"Cargo intake ({cargo_unit})", min_value=1.0, step=1000.0,
        format="%.0f", value=float(ref.cargo_intake), key=f"{k}intake")
    left, right = ship.columns(2)
    speed_laden = left.number_input(
        "Laden kn", min_value=1.0, max_value=30.0, step=0.5, format="%.1f",
        value=float(ref.speed_laden_kn), key=f"{k}sl")
    speed_ballast = right.number_input(
        "Ballast kn", min_value=1.0, max_value=30.0, step=0.5, format="%.1f",
        value=float(ref.speed_ballast_kn), key=f"{k}sb")
    left, right = ship.columns(2)
    cons_laden = left.number_input(
        "Laden t/day", min_value=0.0, step=1.0, format="%.1f",
        value=float(ref.cons_laden_tpd), key=f"{k}fl")
    cons_ballast = right.number_input(
        "Ballast t/day", min_value=0.0, step=1.0, format="%.1f",
        value=float(ref.cons_ballast_tpd), key=f"{k}fb")
    cons_port = ship.number_input(
        "In port t/day", min_value=0.0, step=1.0, format="%.1f",
        value=float(ref.cons_port_tpd), key=f"{k}fp")

voyage = VoyageInputs(
    distance_nm=distance, ballast_pct=ballast_pct, cargo_intake=intake,
    speed_laden_kn=speed_laden, speed_ballast_kn=speed_ballast,
    sea_margin_pct=sea_margin, cons_laden_tpd=cons_laden,
    cons_ballast_tpd=cons_ballast, cons_port_tpd=cons_port,
    port_days_load=days_load, port_days_discharge=days_disch,
    canal_days=canal_days, bunker_price=bunker_price,
    port_cost_load=cost_load, port_cost_discharge=cost_disch,
    canal_dues=canal_dues, commission_pct=commission)
est = (freight_from_hire(voyage, hire) if solve == "freight"
       else tce_from_freight(voyage, quoted))

# --- headline --------------------------------------------------------------------

st.title("Freight: voyage estimate")
theme.subtitle(
    f"<b>{route.load_port} → {route.discharge_port}</b> · "
    f"{provider.get_commodity_profile(commodity).name} · {vessel['name']} · "
    f"{intake:,.0f} {cargo_unit} · {distance:,.0f} nm laden · "
    f"{est.days_total:.1f} d voyage")

vs_ref = est.freight_rate - ref_rate
rate_card = {
    "label": "Freight rate", "value": money(est.freight_rate),
    "unit": cargo_unit, "accent": solve == "freight",
    "delta": (f"{money(vs_ref, signed=True)} vs reference {money(ref_rate)}"
              if abs(vs_ref) >= 0.005 else "on the reference rate"),
}
tce_card = {
    "label": "TCE", "value": f"{'-' if est.tce < 0 else ''}${abs(est.tce):,.0f}",
    "unit": "day", "accent": solve == "tce",
    "delta": ("rate does not cover the voyage costs" if est.tce < 0 else
              f"${est.hire_cost / 1e6:,.2f}M over the voyage"),
    "delta_kind": "neg" if est.tce < 0 else "",
}
theme.metric_cards([
    *([rate_card, tce_card] if solve == "freight" else [tce_card, rate_card]),
    {"label": "Voyage", "value": f"{est.days_total:.1f} days",
     "delta": f"{est.days_laden:.1f} laden · {est.days_ballast:.1f} ballast · "
              f"{est.days_port + est.days_canal:.1f} port"},
    {"label": "Bunkers", "value": f"{est.bunkers_t:,.0f} t",
     "delta": f"{est.bunker_share:.0%} of the freight"},
])

st.subheader("What the rate pays for")
chart(share_bar_figure(est.breakdown, cargo_unit))

# --- bunker sensitivity ----------------------------------------------------------

st.subheader("Bunker exposure")
per_100 = bunker_delta(voyage)
if solve == "freight":
    st.caption(
        f"At constant hire, every USD 100/t on the bunker price moves the "
        f"freight rate by {money(per_100)}/{cargo_unit}, "
        f"${per_100 * intake:,.0f} on the voyage. Under CFR, CIF or DAP "
        "that comes straight off the FOB netback.")
    run = lambda px: freight_from_hire(
        voyage.model_copy(update={"bunker_price": px}), hire).freight_rate
    y_title, y_format, current = f"Freight, USD/{cargo_unit}", ",.2f", est.freight_rate
else:
    tce_100 = (tce_from_freight(voyage.model_copy(
        update={"bunker_price": bunker_price + 100.0}), quoted).tce - est.tce)
    st.caption(
        f"At a fixed rate of {money(quoted)}/{cargo_unit}, every USD 100/t "
        f"on the bunker price moves the TCE by "
        f"{'-' if tce_100 < 0 else '+'}${abs(tce_100):,.0f}/day: on a voyage "
        "charter the bunker risk sits with the owner.")
    run = lambda px: tce_from_freight(
        voyage.model_copy(update={"bunker_price": px}), quoted).tce
    y_title, y_format, current = "TCE, USD/day", ",.0f", est.tce

span = max(300.0, bunker_price * 0.6)
xs = [max(0.0, bunker_price - span) + i * (2 * span / 40) for i in range(41)]
fig = go.Figure([
    go.Scatter(x=xs, y=[run(x) for x in xs], mode="lines",
               line=dict(color=theme.AMBER, width=2),
               hovertemplate=f"Bunkers $%{{x:,.0f}}/t<br>%{{y:{y_format}}}"
                             "<extra></extra>"),
    go.Scatter(x=[bunker_price], y=[current], mode="markers",
               marker=dict(size=9, color=theme.BG,
                           line=dict(color=theme.AMBER, width=2)),
               hovertemplate=f"Today: $%{{x:,.0f}}/t<br>%{{y:{y_format}}}"
                             "<extra></extra>"),
])
terminal_layout(
    fig, height=300, showlegend=False,
    xaxis=dict(title="Bunker price, USD/t",
               title_font=dict(size=11, color=theme.MUTED)),
    yaxis=dict(title=y_title, title_font=dict(size=11, color=theme.MUTED),
               tickformat=y_format),
    margin=dict(t=12, b=44, l=8, r=8))
chart(fig)

# --- what the result hangs on ----------------------------------------------------

st.subheader("What the result hangs on")
if solve == "freight":
    base, rows = voyage_sensitivity(voyage, hire_per_day=hire)
    st.caption("Each driver shocked one at a time; change in the freight "
               "rate at constant hire. Speed follows the cube law: one knot "
               "slower burns far less fuel but keeps the ship longer.")
    chart(tornado_figure(base, rows, cargo_unit, what="freight rate"))
else:
    base, rows = voyage_sensitivity(voyage, freight_rate=quoted)
    st.caption("Each driver shocked one at a time; change in the TCE at the "
               "quoted rate. Speed follows the cube law: when slowing down "
               "raises the TCE, the ship should slow steam.")
    chart(tornado_figure(base, rows, "day", decimals=0, what="TCE"))

# --- detail ----------------------------------------------------------------------

st.subheader("Detail")
with st.expander("Voyage account", expanded=True):
    lump = lambda v: f"{v:,.0f}"
    per = lambda v: f"{v / intake:,.2f}"
    lines = [
        ["Laden leg", f"{est.days_laden:.1f}",
         f"{est.days_laden * cons_laden:,.0f}",
         lump(est.days_laden * cons_laden * bunker_price),
         per(est.days_laden * cons_laden * bunker_price)],
        ["Ballast leg", f"{est.days_ballast:.1f}",
         f"{est.days_ballast * cons_ballast:,.0f}",
         lump(est.days_ballast * cons_ballast * bunker_price),
         per(est.days_ballast * cons_ballast * bunker_price)],
        ["In port and canal", f"{est.days_port + est.days_canal:.1f}",
         f"{est.bunkers_port_t:,.0f}", lump(est.bunkers_port_t * bunker_price),
         per(est.bunkers_port_t * bunker_price)],
        ["Port costs", "", "", lump(est.port_costs), per(est.port_costs)],
    ]
    if est.canal_dues:
        lines.append(["Canal dues", "", "", lump(est.canal_dues),
                      per(est.canal_dues)])
    lines += [
        ["Hire", f"{est.days_total:.1f}", "", lump(est.hire_cost),
         per(est.hire_cost)],
        ["Commission", "", "", lump(est.commission), per(est.commission)],
        ["Gross freight", f"{est.days_total:.1f}", f"{est.bunkers_t:,.0f}",
         lump(est.gross_freight), per(est.gross_freight)],
    ]
    theme.data_table(["Line", "Days", "Bunkers t", "USD",
                      f"USD/{cargo_unit}"], lines)

left, _ = st.columns([1.4, 3])
if left.button("Use this rate in the Calculator →", type="primary",
               width="stretch",
               help=f"Opens {route_label(route)} on the Calculator with "
                    f"freight at {money(est.freight_rate)}/{cargo_unit}."):
    push_to_calculator(commodity, route_id, f=f"{est.freight_rate:.2f}")

st.caption(
    "Vessel figures are indicative for the class (modern eco tonnage, one "
    "fuel grade); every input is editable. The hire field opens on the TCE "
    "implied by the reference freight rate, so the estimate starts "
    "reconciled with the Calculator.")
