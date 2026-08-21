"""Data layer tests: the static reference data loads, validates against the
Session 1 schemas, and flows end-to-end through the core engine. The live
provider is a stub and must say so clearly.

The two end-to-end cases are checked against hand-computed figures using the
values in ``data/reference/``:

Iron ore, Morebaya -> Qingdao (Capesize), CIF 108 USD/dmt:
    freight 22.50 | insurance (108+22.5)*1.10*0.35% = 0.502425
    financing 108*6.5%/365*(34+30) = 1.230904 | ports 2.6+1.9 = 4.50
    commission 108*0.5% = 0.54 | quality 0.5*1.9 - 0 - 0.5*0.6 = 0.65
    netback = 108 - 22.5 - 0.502425 - 1.230904 - 4.5 - 0.54 + 0.65 = 79.376671

Crude oil, Ras Tanura -> Ningbo (VLCC), delivered 78 USD/bbl:
    freight 1.90 | insurance (78+1.9)*1.10*0.25% = 0.219725
    financing 78*6.0%/365*(22+30) = 0.666740 | ports 0.18+0.14 = 0.32
    commission 78*0.25% = 0.195 | quality 2.2*0.3 - (-0.6)*0.9 = 1.20
    netback = 78 - 1.9 - 0.219725 - 0.666740 - 0.32 - 0.195 + 1.20 = 75.898535
"""

import pytest

from netback.core.netback import compute_netback
from netback.core.quality_adjustment import get_adjustment_fn
from netback.data.providers import (LiveDataProvider, PriceDataProvider,
                                    StaticDataProvider)
from netback.models.schemas import CommodityProfile, CostInputs, Route


@pytest.fixture
def provider():
    return StaticDataProvider()


# --- reference data loads and validates against the schemas ------------------

def test_all_commodities_present(provider):
    assert provider.list_commodities() == ["crude_oil", "iron_ore",
                                           "lithium_spodumene"]


def test_every_profile_validates(provider):
    for commodity in provider.list_commodities():
        profile = provider.get_commodity_profile(commodity)
        assert isinstance(profile, CommodityProfile)
        assert profile.benchmark_spec
        # actual_quality defaults (where present) cover the benchmark spec keys
        spec = provider._spec(commodity)
        if "defaults" in spec:
            assert set(spec["defaults"]["actual_quality"]) == set(profile.benchmark_spec)


def test_every_profile_fn_is_registered(provider):
    for commodity in provider.list_commodities():
        profile = provider.get_commodity_profile(commodity)
        assert callable(get_adjustment_fn(profile.quality_adjustment_fn))


def test_original_session1_fns_still_registered():
    assert callable(get_adjustment_fn("bauxite_linear"))
    assert callable(get_adjustment_fn("spodumene_linear"))


def test_every_route_validates_and_is_fully_covered(provider):
    assert provider.list_routes("iron_ore") == ["morebaya_qingdao",
                                                "morebaya_rotterdam"]
    assert provider.list_routes("crude_oil") == ["ras_tanura_ningbo",
                                                 "ras_tanura_rotterdam"]
    for route_id in provider.list_routes():
        route = provider.get_route(route_id)
        assert isinstance(route, Route)
        # every route has a freight rate and fees at both ends
        assert provider.get_freight_rate(route) > 0
        assert provider.get_port_fee(route.load_port, "load") > 0
        assert provider.get_port_fee(route.discharge_port, "discharge") > 0


def test_benchmark_prices(provider):
    assert provider.get_benchmark_price("iron_ore") == 108.0
    assert provider.get_benchmark_price("crude_oil") == 78.0


def test_unknown_keys_raise_helpful_errors(provider):
    with pytest.raises(KeyError, match="Available"):
        provider.get_commodity_profile("uranium")
    with pytest.raises(KeyError, match="Available"):
        provider.get_route("morebaya_mars")
    with pytest.raises(KeyError, match="Available"):
        provider.get_port_fee("Atlantis", "load")
    with pytest.raises(ValueError):
        provider.get_port_fee("Qingdao", "sideways")
    with pytest.raises(KeyError, match="Known routes"):
        provider.get_freight_rate(Route(load_port="Atlantis", discharge_port="Qingdao",
                                        distance_nm=1, transit_days=1,
                                        vessel_type="Capesize"))


def test_default_cost_inputs_fully_populated(provider):
    inputs = provider.get_default_cost_inputs("iron_ore", "morebaya_qingdao")
    assert isinstance(inputs, CostInputs)
    assert inputs.price_basis == 108.0            # benchmark by default
    assert inputs.freight_rate_per_unit == 22.5
    assert inputs.load_port_fee_per_unit == 2.6
    assert inputs.discharge_port_fee_per_unit == 1.9
    # overrides win
    custom = provider.get_default_cost_inputs("iron_ore", "morebaya_qingdao",
                                              price_basis=95.0, quantity=1000)
    assert custom.price_basis == 95.0
    assert custom.quantity == 1000


# --- end-to-end: provider data through the core engine -----------------------

def test_iron_ore_end_to_end_netback(provider):
    inputs = provider.get_default_cost_inputs("iron_ore", "morebaya_qingdao")
    route = provider.get_route("morebaya_qingdao")
    profile = provider.get_commodity_profile("iron_ore")
    result = compute_netback(inputs, route, profile, mode="netback")

    assert result.freight_cost == pytest.approx(22.5, abs=0.005)
    assert result.insurance_cost == pytest.approx(0.502425, abs=0.005)
    assert result.financing_cost == pytest.approx(1.230904, abs=0.005)
    assert result.port_fees_total == pytest.approx(4.5, abs=0.005)
    assert result.commission_cost == pytest.approx(0.54, abs=0.005)
    assert result.quality_adjustment == pytest.approx(0.65, abs=0.005)
    assert result.result_price == pytest.approx(79.376671, abs=0.005)


def test_crude_oil_end_to_end_netback(provider):
    inputs = provider.get_default_cost_inputs("crude_oil", "ras_tanura_ningbo")
    route = provider.get_route("ras_tanura_ningbo")
    profile = provider.get_commodity_profile("crude_oil")
    result = compute_netback(inputs, route, profile, mode="netback")

    assert result.quality_adjustment == pytest.approx(1.20, abs=0.005)
    assert result.result_price == pytest.approx(75.898535, abs=0.005)


def test_landed_cost_mode_also_flows(provider):
    inputs = provider.get_default_cost_inputs("crude_oil", "ras_tanura_rotterdam",
                                              price_basis=74.0)
    route = provider.get_route("ras_tanura_rotterdam")
    profile = provider.get_commodity_profile("crude_oil")
    result = compute_netback(inputs, route, profile, mode="landed_cost")
    assert result.result_price > inputs.price_basis + inputs.freight_rate_per_unit


# --- skeleton profile: new commodity without touching code -------------------

def test_skeleton_lithium_profile_runs_through_engine(provider):
    """lithium_spodumene has no reference routes/prices, only a profile that
    reuses an already-registered formula — pure config, zero code change."""
    profile = provider.get_commodity_profile("lithium_spodumene")
    assert profile.quality_adjustment_fn == "spodumene_linear"

    route = Route(load_port="Port Hedland", discharge_port="Ningbo",
                  distance_nm=3200, transit_days=12, vessel_type="Handysize")
    inputs = CostInputs(
        quantity=15000, price_basis=900.0, freight_rate_per_unit=28.0,
        insurance_rate_pct=0.4, financing_rate_annual_pct=7.0,
        payment_terms_days=30, load_port_fee_per_unit=3.0,
        discharge_port_fee_per_unit=2.5, actual_quality={"Li2O": 5.7},
    )
    result = compute_netback(inputs, route, profile, mode="netback")
    assert result.quality_adjustment == pytest.approx(-0.3 * 145.0)
    assert 0 < result.result_price < 900.0


def test_skeleton_profile_has_no_full_reference_data(provider):
    with pytest.raises(KeyError, match="skeleton"):
        provider.get_benchmark_price("lithium_spodumene")
    with pytest.raises(KeyError, match="skeleton"):
        provider.get_default_cost_inputs("lithium_spodumene", "morebaya_qingdao")
    assert provider.list_routes("lithium_spodumene") == []


# --- live provider stub ------------------------------------------------------

def test_live_provider_is_a_stub():
    live = LiveDataProvider()
    assert isinstance(live, PriceDataProvider)
    route = Route(load_port="A", discharge_port="B", distance_nm=1,
                  transit_days=1, vessel_type="VLCC")
    for call in (lambda: live.list_commodities(),
                 lambda: live.get_commodity_profile("iron_ore"),
                 lambda: live.get_benchmark_price("iron_ore"),
                 lambda: live.list_routes(),
                 lambda: live.get_route("morebaya_qingdao"),
                 lambda: live.get_freight_rate(route),
                 lambda: live.get_port_fee("Qingdao", "load"),
                 lambda: live.get_default_cost_inputs("iron_ore", "morebaya_qingdao")):
        with pytest.raises(NotImplementedError, match="not implemented"):
            call()
