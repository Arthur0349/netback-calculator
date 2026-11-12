"""Calculator case state: shareable links and persistence across pages.

One mechanism serves three needs:

- **Shared link.** The Calculator keeps its URL in sync with the inputs
  (``netback.sharing``). Opening such a URL restores the case.
- **Coming back.** Streamlit drops widget state when the user leaves a page;
  the last case is kept in session state and restored on return.
- **Hand-over.** Another page (the voyage estimate) can push values into the
  Calculator through ``push_to_calculator``.

In all three, the case to restore becomes a *seed*: default values for the
widgets, under a fresh key prefix so the widgets are rebuilt from the seed.
The seed is a snapshot taken once, never updated while the user edits, so
widget defaults stay stable from run to run.
"""

from typing import Any

import streamlit as st

from netback.models.schemas import CommodityProfile, CostInputs, Route
from netback.sharing import CaseLink, decode_case, encode_case
from ui_helpers import source_tag


def adopt_case(provider) -> None:
    """Decide, before any Calculator widget is created, whether a case must
    be restored, and stage it as the seed."""
    state = st.session_state
    params = st.query_params.to_dict()
    last = state.get("_calc_last", {})
    pending = state.pop("_calc_pending", None)

    link = None
    if pending is not None:
        same_case = all(last.get(k) == pending.get(k) for k in ("c", "r"))
        link = decode_case({**(last if same_case else {}), **pending})
    elif params and params != state.get("_calc_url"):
        link = decode_case(params)                 # a link someone opened
    elif state.get("_entered") and last:
        link = decode_case(last)                   # back from another page

    if link is None or link.commodity not in provider.list_commodities():
        return
    state["_calc_seed"] = link
    state["_calc_nonce"] = state.get("_calc_nonce", 0) + 1
    state["commodity"] = link.commodity
    if link.mode:
        state["mode"] = link.mode
    if link.route_id in provider.list_routes(link.commodity):
        state[f"route_{link.commodity}"] = link.route_id


def case_seed(commodity: str, route_id: str | None) -> CaseLink | None:
    """The staged seed, if it belongs to the case on screen."""
    link = st.session_state.get("_calc_seed")
    if link is None or link.commodity != commodity:
        return None
    if route_id is not None and link.route_id != route_id:
        return None
    return link


def key_prefix(commodity: str, route_id: str | None) -> str:
    nonce = st.session_state.get("_calc_nonce", 0)
    return f"{commodity}_{route_id}_{source_tag()}_{nonce}_"


def seed_with_case(seed: dict[str, Any], link: CaseLink | None) -> dict[str, Any]:
    """Reference seed overlaid with the case values, clamped to what the
    widgets accept."""
    if link is None:
        return seed
    seed = {**seed, **link.values}
    seed["price_basis"] = max(0.01, seed["price_basis"])
    seed["quantity"] = max(1.0, seed["quantity"])
    if link.delivery_term:
        seed["delivery_term"] = link.delivery_term
    quality = seed.get("actual_quality", {})
    seed["actual_quality"] = {**quality, **{k: v for k, v in link.quality.items()
                                            if k in quality}}
    return seed


def profile_with_case(profile: CommodityProfile, metal_prices: dict[str, float],
                      link: CaseLink | None
                      ) -> tuple[CommodityProfile, dict[str, float]]:
    """Concentrates: smelter terms and metal prices overlaid with the case."""
    terms = profile.concentrate_terms
    if link is None or terms is None:
        return profile, metal_prices
    payables = [p.model_copy(update={
                    "refining_charge": link.refining_charges[p.element]})
                if p.element in link.refining_charges else p
                for p in terms.payables]
    update: dict[str, Any] = {"payables": payables}
    if link.treatment_charge is not None:
        update["treatment_charge"] = link.treatment_charge
    prices = {**metal_prices, **{k: v for k, v in link.metal_prices.items()
                                 if k in metal_prices}}
    return (profile.model_copy(update={
                "concentrate_terms": terms.model_copy(update=update)}), prices)


def sync_case(commodity: str, route_id: str | None, mode: str,
              inputs: CostInputs, route: Route, profile: CommodityProfile,
              metal_prices: dict[str, float] | None,
              deal_price: float) -> dict[str, str]:
    """Record the case on screen: in the URL (the address bar is the
    shareable link) and in session state (restored on return)."""
    state = st.session_state
    params = encode_case(
        commodity, route_id, mode, inputs,
        with_price=profile.concentrate_terms is None,
        metal_prices=metal_prices, terms=profile.concentrate_terms,
        deal_price=deal_price, route=route if route_id is None else None)
    if st.query_params.to_dict() != params:
        st.query_params.from_dict(params)
    state["_calc_url"] = params
    state["_calc_last"] = params
    return params


def push_to_calculator(commodity: str, route_id: str, **params: str) -> None:
    """Stage values for the Calculator (query-parameter names, see
    ``netback.sharing``) and go there."""
    st.session_state["_calc_pending"] = {"c": commodity, "r": route_id, **params}
    st.switch_page("pages/1_Calculator.py")
