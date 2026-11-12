"""Sensitivity and breakeven, on the hand-computed bauxite case of
test_netback.py (CIF 75, freight 22, netback 43.99363).

Freight is a pure pass-through in netback mode (insurance is on the CIF
price), so freight -10 % (2.2) lifts the netback by exactly 2.2.
Price +10 % (7.5): insurance +0.033, financing +0.080137, commission +0.0375
    -> netback +7.5 - 0.150637 = +7.349363.
"""

import json
from pathlib import Path

import pytest

from netback.core.netback import compute_netback, compute_result
from netback.core.sensitivity import breakeven, tornado
from netback.data.providers import StaticDataProvider
from netback.models.schemas import CommodityProfile, CostInputs, Route

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "reference_cases.json").read_text()
)


@pytest.fixture
def case():
    return (CostInputs(**CASES["netback_case"]["inputs"]), Route(**CASES["route"]),
            CommodityProfile(**CASES["profile"]))


def test_tornado_hand_case(case):
    base, rows = tornado(*case, mode="netback")
    by = {r.driver: r for r in rows}
    assert base == pytest.approx(43.99363, abs=0.001)
    assert by["Freight rate"].delta_low == pytest.approx(2.2)
    assert by["Freight rate"].delta_high == pytest.approx(-2.2)
    assert by["Delivered price"].delta_high == pytest.approx(7.349363, abs=0.001)
    # Al2O3 +1 pt at 1.5 $/pt
    assert by["Al2O3 grade"].delta_high == pytest.approx(1.5)
    assert rows == sorted(rows, key=lambda r: r.swing, reverse=True)
    assert rows[0].driver == "Delivered price"


def test_tornado_concentrate_drivers():
    p = StaticDataProvider()
    c, rid = "copper_concentrate", "lobito_qingdao"
    base, rows = tornado(p.get_default_cost_inputs(c, rid), p.get_route(rid),
                         p.get_commodity_profile(c, rid),
                         metal_prices=p.get_metal_prices(c))
    by = {r.driver: r for r in rows}
    assert base == pytest.approx(3590.7752, abs=0.01)
    assert rows[0].driver == "Cu price"
    assert "Delivered price" not in by
    # TC is a straight deduction, less the insurance and financing it carried
    assert by["TC"].delta_high < 0 < by["TC"].delta_low
    assert by["TC"].delta_low == pytest.approx(50 * (1 - 0.00165 - 0.065 / 365 * 68), abs=0.01)
    assert {"Moisture", "Cu grade", "Freight rate"} <= set(by)


def test_breakeven_freight_and_price(case):
    inputs, route, profile = case
    base = compute_netback(inputs, route, profile).result_price
    assert breakeven(inputs, route, profile, base - 5.0, "freight") == pytest.approx(27.0)
    price = breakeven(inputs, route, profile, 50.0, "price")
    check = compute_netback(inputs.model_copy(update={"price_basis": price}),
                            route, profile).result_price
    assert check == pytest.approx(50.0)


def test_breakeven_metal_price_round_trip():
    p = StaticDataProvider()
    c, rid = "copper_concentrate", "lobito_qingdao"
    args = (p.get_default_cost_inputs(c, rid), p.get_route(rid),
            p.get_commodity_profile(c, rid))
    prices = p.get_metal_prices(c)
    cu = breakeven(*args, 3000.0, "metal:Cu", metal_prices=prices)
    assert cu < prices["Cu"]
    assert compute_result(*args, "netback", {**prices, "Cu": cu}).result_price \
        == pytest.approx(3000.0)


def test_breakeven_edge_cases(case):
    inputs, route, profile = case
    assert breakeven(inputs, route, profile, 1e6, "freight") is None   # negative freight
    with pytest.raises(ValueError):
        breakeven(inputs, route, profile, 40.0, "weather")


def test_compute_result_rejects_landed_cost_for_concentrates():
    p = StaticDataProvider()
    c, rid = "copper_concentrate", "lobito_qingdao"
    with pytest.raises(ValueError, match="netback mode only"):
        compute_result(p.get_default_cost_inputs(c, rid), p.get_route(rid),
                       p.get_commodity_profile(c, rid), "landed_cost", {})
