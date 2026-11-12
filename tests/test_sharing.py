"""Shareable case links: a case survives the round trip through a URL, and
a hostile or broken link never raises."""

from urllib.parse import parse_qsl, urlencode

from netback.data.providers import StaticDataProvider
from netback.models.schemas import Route
from netback.sharing import CaseLink, decode_case, encode_case


def test_round_trip_index_commodity():
    p = StaticDataProvider()
    inputs = p.get_default_cost_inputs("iron_ore", "morebaya_qingdao").model_copy(
        update={"freight_rate_per_unit": 19.75, "delivery_term": "DPU",
                "actual_quality": {"Fe": 63.2, "SiO2": 4.1, "moisture": 9.0}})
    params = encode_case("iron_ore", "morebaya_qingdao", "netback", inputs,
                         deal_price=74.5)
    # through a real URL and back
    link = decode_case(dict(parse_qsl(urlencode(params))))
    assert (link.commodity, link.route_id, link.mode) == (
        "iron_ore", "morebaya_qingdao", "netback")
    assert link.delivery_term == "DPU"
    assert link.quality == inputs.actual_quality
    assert link.deal_price == 74.5
    for field, value in link.values.items():
        assert value == getattr(inputs, field)
    assert set(link.values) == {
        "price_basis", "quantity", "freight_rate_per_unit", "insurance_rate_pct",
        "financing_rate_annual_pct", "payment_terms_days",
        "load_port_fee_per_unit", "discharge_port_fee_per_unit", "commission_pct"}


def test_round_trip_concentrate_carries_terms_not_price():
    p = StaticDataProvider()
    c, rid = "copper_concentrate", "dar_es_salaam_fangchenggang"
    profile = p.get_commodity_profile(c, rid)
    prices = {"Cu": 14250.0, "Au": 4100.0, "Ag": 52.0}
    params = encode_case(c, rid, "netback", p.get_default_cost_inputs(c, rid),
                         with_price=False, metal_prices=prices,
                         terms=profile.concentrate_terms)
    assert "p" not in params                     # the price is an output
    link = decode_case(params)
    assert link.metal_prices == prices
    assert link.treatment_charge == -100.0       # negative TC survives
    assert link.refining_charges == {"Cu": -0.01, "Au": 5.0, "Ag": 0.4}
    assert "price_basis" not in link.values


def test_manual_route_is_carried():
    p = StaticDataProvider()
    inputs = p.get_default_cost_inputs("iron_ore", "morebaya_qingdao")
    route = Route(load_port="Port Hedland", discharge_port="Ningbo",
                  distance_nm=3200, transit_days=12, vessel_type="Capesize")
    link = decode_case(encode_case("lithium_spodumene", None, "netback", inputs,
                                   route=route))
    assert link.route_id is None
    assert link.route_text == {"load_port": "Port Hedland",
                               "discharge_port": "Ningbo",
                               "vessel_type": "Capesize"}
    assert link.route_values == {"distance_nm": 3200.0, "transit_days": 12.0}


def test_links_are_short_and_readable():
    p = StaticDataProvider()
    params = encode_case("crude_oil", "ras_tanura_ningbo", "landed_cost",
                         p.get_default_cost_inputs("crude_oil", "ras_tanura_ningbo"))
    assert params["q"] == "2000000" and params["f"] == "1.9"    # no 1.9000000001
    assert len(urlencode(params)) < 250


def test_broken_links_never_raise():
    link = decode_case({
        "c": "iron_ore", "m": "sideways", "term": "EXW", "q": "lots",
        "f": "nan", "p": "inf", "ins": "-3", "lf": "1e999", "x.Fe": "",
        "px.Cu": "-1", "tc": "abc", "deal": "-5", "nm": "0", "zzz": "1",
        "lp": "x" * 500, "x.SiO2": "4.5"})
    assert link.commodity == "iron_ore"
    assert link.mode is None and link.delivery_term is None
    assert link.values == {} and link.metal_prices == {}
    assert link.quality == {"SiO2": 4.5}
    assert link.treatment_charge is None and link.deal_price is None
    assert link.route_values == {} and len(link.route_text["load_port"]) == 60
    assert decode_case({}) == CaseLink()
