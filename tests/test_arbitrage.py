"""Arbitrage ranking and destination-specific market terms.

Copper concentrate, default cargo (net value 3,697.3734 $/dmt on benchmark
terms, see test_concentrate.py). Dar es Salaam -> Fangchenggang carries
illustrative spot-linked terms: TC -100 $/dmt, RC Cu -1.0 c/lb.

    value = 3,697.3734 + 100 + 0.255 x 2,204.62 x 0.01 (5.6218) = 3,802.9952

Iron ore Morebaya -> Rotterdam, CFR 108 - 6 = 102, 8.5 % moisture:
    freight 9.5 / 0.915 = 10.3825 | financing 102 x 6.5 % / 365 x 40 = 0.7266
    netback = 102 - 10.3825 - 0.7266 - 2.6 - 0.51 + 0.65 = 88.4309
    vs Qingdao 79.6889 (test_data_providers.py) -> Rotterdam best by 8.742
"""

import pytest

from netback.core.arbitrage import rank_outlets
from netback.core.netback import compute_concentrate_netback, compute_netback
from netback.data.providers import StaticDataProvider


@pytest.fixture
def provider():
    return StaticDataProvider()


def _iron_ore_results(provider):
    return {rid: compute_netback(provider.get_default_cost_inputs("iron_ore", rid),
                                 provider.get_route(rid),
                                 provider.get_commodity_profile("iron_ore"))
            for rid in provider.list_routes("iron_ore")}


def test_destination_differential_sets_delivered_price(provider):
    rotterdam = provider.get_default_cost_inputs("iron_ore", "morebaya_rotterdam")
    assert rotterdam.price_basis == pytest.approx(102.0)
    # explicit price still wins over the differential
    assert provider.get_default_cost_inputs(
        "iron_ore", "morebaya_rotterdam", price_basis=99.0).price_basis == 99.0


def test_destination_smelter_terms_override_benchmark(provider):
    profile = provider.get_commodity_profile("copper_concentrate",
                                             "dar_es_salaam_fangchenggang")
    terms = profile.concentrate_terms
    assert terms.treatment_charge == -100.0
    assert {p.element: p.refining_charge for p in terms.payables} == {
        "Cu": -0.01, "Au": 5.0, "Ag": 0.4}       # unlisted RCs keep the default
    inputs = provider.get_default_cost_inputs("copper_concentrate",
                                              "dar_es_salaam_fangchenggang")
    assert inputs.price_basis == pytest.approx(3802.9952, abs=0.001)


def test_rank_outlets_iron_ore(provider):
    ranking = rank_outlets(_iron_ore_results(provider), quantity=180000)
    best, second = ranking
    assert (best.outlet, best.rank) == ("morebaya_rotterdam", 1)
    assert best.netback == pytest.approx(88.4309, abs=0.001)
    assert best.spread_vs_best == 0.0
    assert best.cushion == pytest.approx(8.742, abs=0.001)
    assert second.spread_vs_best == pytest.approx(-8.742, abs=0.001)
    assert second.cargo_spread_vs_best == pytest.approx(-8.742 * 180000, rel=1e-4)
    assert best.freight == pytest.approx(10.3825, abs=0.001)


def test_rank_outlets_concentrate(provider):
    c = "copper_concentrate"
    results = {rid: compute_concentrate_netback(
                   provider.get_default_cost_inputs(c, rid), provider.get_route(rid),
                   provider.get_commodity_profile(c, rid), provider.get_metal_prices(c))
               for rid in provider.list_routes(c)}
    ranking = rank_outlets(results, quantity=10000)
    assert [r.outlet for r in ranking] == ["dar_es_salaam_fangchenggang",
                                           "lobito_huelva", "lobito_qingdao"]
    assert [r.rank for r in ranking] == [1, 2, 3]
    assert all(r.spread_vs_best <= 0 for r in ranking)


def test_single_outlet_has_zero_cushion(provider):
    results = _iron_ore_results(provider)
    only = {"morebaya_qingdao": results["morebaya_qingdao"]}
    assert rank_outlets(only, 1000)[0].cushion == 0.0
    assert rank_outlets({}, 1000) == []


def test_rank_rejects_landed_cost_results(provider):
    r = compute_netback(provider.get_default_cost_inputs("iron_ore", "morebaya_qingdao"),
                        provider.get_route("morebaya_qingdao"),
                        provider.get_commodity_profile("iron_ore"), mode="landed_cost")
    with pytest.raises(ValueError, match="netbacks only"):
        rank_outlets({"x": r}, 1000)
