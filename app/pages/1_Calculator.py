from urllib.parse import urlencode

import streamlit as st

import theme
from case_state import (adopt_case, case_seed, key_prefix, profile_with_case,
                        seed_with_case, sync_case)
from netback.core.sensitivity import breakeven, tornado
from netback.reporting.trade_sheet import build_trade_sheet
from ui_helpers import (MODE_HELP, MODE_LABELS, chart, commodity_selectbox,
                        compute, concentrate_details_table, concentrate_inputs,
                        cost_inputs_form, cost_share_figure, freight_unit,
                        money, responsive_waterfall, result_metric_cards,
                        route_inputs, seed_inputs, setup_page, tornado_figure)

st.set_page_config(page_title="Calculator · Netback Calculator",
                   page_icon="🚢", layout="wide")
theme.inject()

provider = setup_page("calculator")
adopt_case(provider)        # shared link, return from another page, hand-over

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

    manual = case_seed(commodity, None)
    route_id, route = route_inputs(
        provider, commodity, st,
        seed={**manual.route_text, **manual.route_values} if manual else None)
    voyage = None
    if route_id is not None:
        # destination-specific terms (e.g. the smelter's TC/RCs)
        profile = provider.get_commodity_profile(commodity, route_id)
        try:
            voyage = provider.get_voyage_inputs(route_id)
        except KeyError:
            pass                    # no reference vessel class for this route

    case = case_seed(commodity, route_id)
    key = key_prefix(commodity, route_id)
    seed = seed_with_case(seed_inputs(provider, commodity, route_id), case)
    inputs = cost_inputs_form(profile, seed, st, mode=mode, key_prefix=key,
                              voyage=voyage, vessel_type=route.vessel_type)

    metal_prices = None
    if is_concentrate:
        profile, metal_prices = profile_with_case(
            profile, provider.get_metal_prices(commodity), case)
        profile, metal_prices = concentrate_inputs(
            profile, metal_prices, st, key_prefix=key)

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


def deal_seed(default: float) -> float:
    """Deal price from the restored case when there is one."""
    if case is not None and case.deal_price is not None:
        return float(case.deal_price)
    return float(round(max(default, 0.0), 2))


left, _ = st.columns([1, 3])
if mode == "netback":
    other = left.number_input(
        f"FOB purchase cost (USD/{unit})", min_value=0.0,
        value=deal_seed(result.result_price * 0.97), format="%.2f",
        key=f"{key}deal_cost",
        help="What the cargo costs you at the load port. The margin is the "
             "FOB netback minus this cost.")
    margin = result.result_price - other
    capital = other
    target = other                                   # netback needed to break even
else:
    other = left.number_input(
        f"Delivered sale price (USD/{unit})", min_value=0.0,
        value=deal_seed(result.result_price * 1.03), format="%.2f",
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

left, right, _ = st.columns([1.15, 1, 2.2], vertical_alignment="center")
left.download_button(
    "Download trade sheet (PDF)",
    data=build_trade_sheet(result, inputs, route, profile, metal_prices,
                           rows, as_of=provider.as_of,
                           live=provider.is_live),
    file_name=(f"trade-sheet-{commodity}-{route.load_port}-"
               f"{route.discharge_port}.pdf").lower().replace(" ", "-"),
    mime="application/pdf", type="primary", width="stretch",
    help="One page: headline figures, waterfall, assumptions, sensitivities.")

# --- shareable link ------------------------------------------------------------
# The URL always carries the case on screen, so the address bar is the link.

params = sync_case(commodity, route_id, mode, inputs, route, profile,
                   metal_prices, other)
with right.popover("Share this case", width="stretch"):
    try:
        base_url = st.context.url.split("?")[0]
    except Exception:               # no browser context (tests)
        base_url = ""
    st.markdown("**Link to this exact case**")
    st.code(f"{base_url}?{urlencode(params)}", language=None, wrap_lines=True)
    st.caption("Every input on screen is in the link: whoever opens it sees "
               "the same cargo, costs and result. The address bar carries "
               "the same link and follows your edits.")

st.caption(provider.data_note)
