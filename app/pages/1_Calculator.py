import streamlit as st

import theme
from netback.core.sensitivity import breakeven, tornado
from netback.reporting.trade_sheet import build_trade_sheet
from ui_helpers import (MODE_HELP, MODE_LABELS, chart, commodity_selectbox,
                        compute, concentrate_details_table, concentrate_inputs,
                        cost_inputs_form, cost_share_figure, freight_unit,
                        get_provider, money, responsive_waterfall,
                        result_metric_cards, route_inputs, seed_inputs,
                        tornado_figure)

st.set_page_config(page_title="Calculator · Netback Calculator",
                   page_icon="🚢", layout="wide")
theme.inject()

provider = get_provider()
theme.ticker(provider)

# --- inputs --------------------------------------------------------------------

with st.sidebar:
    commodity = commodity_selectbox(provider, st)
    profile = provider.get_commodity_profile(commodity)
    is_concentrate = profile.concentrate_terms is not None

    if is_concentrate:
        mode = "netback"
    else:
        mode = st.radio("Direction", list(MODE_LABELS), horizontal=True,
                        format_func=MODE_LABELS.get, key="mode", help=MODE_HELP)

    route_id, route = route_inputs(provider, commodity, st)
    if route_id is not None:
        # destination-specific terms (e.g. the smelter's TC/RCs)
        profile = provider.get_commodity_profile(commodity, route_id)

    key = f"{commodity}_{route_id}_"
    seed = seed_inputs(provider, commodity, route_id)
    inputs = cost_inputs_form(profile, seed, st, mode=mode, key_prefix=key)

    metal_prices = None
    if is_concentrate:
        profile, metal_prices = concentrate_inputs(
            profile, provider.get_metal_prices(commodity), st, key_prefix=key)

result = compute(inputs, route, profile, mode, metal_prices)
unit = profile.unit
result_label = result.breakdown[-1][0]
inline_label = result_label if result_label.startswith("FOB") else result_label.lower()

# --- headline --------------------------------------------------------------------

st.title(f"{profile.name}: {result_label}")
theme.subtitle(
    f"<b>{inputs.delivery_term} {route.discharge_port}</b> · "
    f"{route.load_port} → {route.discharge_port} · {route.vessel_type} · "
    f"{route.transit_days:g} d transit · {inputs.quantity:,.0f} {unit}"
    + (" · valued from assays" if is_concentrate else ""))

result_metric_cards(result, unit, inputs.quantity)
responsive_waterfall(result, unit)

st.subheader("Voyage cost structure")
chart(cost_share_figure(result, unit))

# --- sensitivity -----------------------------------------------------------------

st.subheader("What the result hangs on")
base, rows = tornado(inputs, route, profile, mode, metal_prices)
st.caption(f"Each driver shocked one at a time, down and up; change in the "
           f"{inline_label}. The top bar is the assumption to "
           "check first.")
chart(tornado_figure(base, rows, unit))

# --- deal check ------------------------------------------------------------------

st.subheader("Deal check")
days = route.transit_days + inputs.payment_terms_days
left, _ = st.columns([1, 3])
if mode == "netback":
    other = left.number_input(
        f"FOB purchase cost (USD/{unit})", min_value=0.0,
        value=float(round(result.result_price * 0.97, 2)), format="%.2f",
        key=f"{key}deal_cost",
        help="What the cargo costs you at the load port. The margin is the "
             "FOB netback minus this cost.")
    margin = result.result_price - other
    capital = other
    target = other                                   # netback needed to break even
else:
    other = left.number_input(
        f"Delivered sale price (USD/{unit})", min_value=0.0,
        value=float(round(result.result_price * 1.03, 2)), format="%.2f",
        key=f"{key}deal_sale",
        help="What the buyer pays delivered. The margin is this price minus "
             "the landed cost.")
    margin = other - result.result_price
    capital = result.base_price
    target = other                                   # landed cost that breaks even

annualised = (margin / capital) * 365 / days if capital and days else 0.0
be_freight = breakeven(inputs, route, profile, target, "freight", mode, metal_prices)
if is_concentrate:
    lead = profile.concentrate_terms.payables[0].price_key
    be_price = breakeven(inputs, route, profile, target, f"metal:{lead}", mode,
                         metal_prices)
    price_label, price_now, price_unit = (f"Breakeven {lead} price",
                                          metal_prices[lead], "t")
else:
    be_price = breakeven(inputs, route, profile, target, "price", mode)
    price_label = ("Breakeven sale price" if mode == "netback"
                   else "Breakeven FOB price")
    price_now, price_unit = inputs.price_basis, unit

kind = "pos" if margin > 0 else "neg"
cards = [
    {"label": "Margin", "value": money(margin, signed=True), "unit": unit,
     "accent": True,
     "delta": f"{'-' if margin < 0 else '+'}${abs(margin) * inputs.quantity:,.0f} "
              "on the cargo",
     "delta_kind": kind},
    {"label": "Return on capital", "value": f"{annualised:+.1%}", "unit": "yr",
     "delta": f"{margin / capital:+.2%} over {days:g} days" if capital else "",
     "delta_kind": kind},
]
if be_freight is not None:
    cards.append({
        "label": "Breakeven freight", "value": money(be_freight),
        "unit": freight_unit(profile),
        "delta": f"{be_freight - inputs.freight_rate_per_unit:+,.2f} vs today"})
else:
    cards.append({"label": "Breakeven freight", "value": "n/a",
                  "delta": "no positive freight breaks even"})
if be_price is not None:
    cards.append({
        "label": price_label, "value": money(be_price), "unit": price_unit,
        "delta": f"{be_price / price_now - 1:+.1%} vs today" if price_now else ""})
theme.metric_cards(cards)

# --- detail and export -----------------------------------------------------------

st.subheader("Detail")
if is_concentrate:
    with st.expander("Concentrate valuation: payables, charges, penalties",
                     expanded=True):
        concentrate_details_table(profile, inputs, metal_prices)

with st.expander("Full breakdown", expanded=not is_concentrate):
    lines = (result.price_build_up + result.breakdown[1:]
             if result.price_build_up else result.breakdown)
    theme.data_table(
        ["Component", f"USD/{unit}", "Cargo USD"],
        [[label, f"{value:,.2f}", f"{value * inputs.quantity:,.0f}"]
         for label, value in lines if value != 0 or label == "Base price"],
    )

st.download_button(
    "Download trade sheet (PDF)",
    data=build_trade_sheet(result, inputs, route, profile, metal_prices, rows,
                           as_of=provider.as_of),
    file_name=(f"trade-sheet-{commodity}-{route.load_port}-"
               f"{route.discharge_port}.pdf").lower().replace(" ", "-"),
    mime="application/pdf", type="primary",
    help="One page: headline figures, waterfall, assumptions, sensitivities.")
