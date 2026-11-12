"""Concentrate valuation, checked against a hand-computed copper case.

Assays Cu 26.5 %, Au 2.2 g/dmt, Ag 45 g/dmt, As 0.35 %. Prices Cu 13,800 $/t,
Au 4,100 $/oz, Ag 52 $/oz. Terms: Cu 96.5 % min. 1 unit, Au 90 % min. 1 g,
Ag 90 % min. 30 g, TC 0, RC Cu 0 c/lb, Au 5 $/oz, Ag 0.40 $/oz,
As 3 $ per 0.1 % above 0.2 %.

    Cu payable  min(25.5725, 25.5) = 25.5 %  -> 0.255 t x 13,800 = 3,519.00
    Au payable  min(1.98, 1.2) = 1.2 g = 0.038581 oz x 4,100      =   158.18
    Ag payable  min(40.5, 15) = 15 g = 0.482261 oz x 52           =    25.08
    RC          0.038581 x 5 + 0.482261 x 0.40                    =     0.39
    As penalty  (0.35 - 0.2) / 0.1 = 1.5 steps x 3                =     4.50
    net invoice value = 3,519 + 158.1816 + 25.0776 - 0.3858 - 4.5 = 3,697.3734

Netback Lobito -> Qingdao, CIF, 9.5 % moisture, 38 d transit + 30 d terms:
    freight 45 / 0.905 = 49.7238 | insurance 3,697.37 x 1.10 x 0.15 % = 6.1007
    financing 3,697.37 x 6.5 % / 365 x 68 = 44.7737 | load port 6.0
    netback = 3,697.3734 - 49.7238 - 6.1007 - 44.7737 - 6.0 = 3,590.7752
"""

import pytest

from netback.core.concentrate import (payable_content, penalty_charge,
                                      value_concentrate)
from netback.core.netback import compute_concentrate_netback, compute_netback
from netback.data.providers import StaticDataProvider
from netback.models.schemas import ConcentrateTerms

ASSAYS = {"Cu": 26.5, "Au": 2.2, "Ag": 45.0, "As": 0.35, "moisture": 9.5}
PRICES = {"Cu": 13800.0, "Au": 4100.0, "Ag": 52.0}


@pytest.fixture
def provider():
    return StaticDataProvider()


@pytest.fixture
def terms(provider):
    return provider.get_commodity_profile("copper_concentrate").concentrate_terms


def test_payable_takes_the_lower_of_pct_and_deduction():
    assert payable_content(26.5, 96.5, 1.0) == pytest.approx(25.5)     # deduction bites
    assert payable_content(40.0, 96.5, 1.0) == pytest.approx(38.6)     # % bites
    assert payable_content(0.8, 90.0, 1.0) == 0.0                      # below deduction


def test_penalty_pro_rata_and_full_steps():
    assert penalty_charge(0.35, 0.2, 0.1, 3.0) == pytest.approx(4.5)
    assert penalty_charge(0.35, 0.2, 0.1, 3.0, pro_rata=False) == pytest.approx(3.0)
    assert penalty_charge(0.15, 0.2, 0.1, 3.0) == 0.0


def test_copper_concentrate_valuation_hand_case(terms):
    v = value_concentrate(ASSAYS, terms, PRICES)
    lines = dict(v.build_up)
    assert lines["Payable Cu"] == pytest.approx(3519.0)
    assert lines["Payable Au"] == pytest.approx(158.1816, abs=0.001)
    assert lines["Payable Ag"] == pytest.approx(25.0776, abs=0.001)
    assert v.refining_charge == pytest.approx(0.3858, abs=0.001)
    assert v.penalties == pytest.approx(4.5)
    assert v.net_value == pytest.approx(3697.3734, abs=0.001)
    assert sum(val for _, val in v.build_up) == pytest.approx(v.net_value)


def test_negative_tc_raises_the_value(terms):
    spot = terms.model_copy(update={"treatment_charge": -120.0})
    base = value_concentrate(ASSAYS, terms, PRICES).net_value
    assert value_concentrate(ASSAYS, spot, PRICES).net_value == pytest.approx(base + 120.0)


def test_copper_rc_in_dollars_per_payable_lb():
    terms = ConcentrateTerms(payables=[{
        "element": "Cu", "unit": "pct", "payable_pct": 96.5, "min_deduction": 1.0,
        "price_key": "Cu", "refining_charge": 0.02}])           # 2.0 c/lb
    v = value_concentrate({"Cu": 26.5}, terms, PRICES)
    assert v.refining_charge == pytest.approx(0.255 * 2204.62 * 0.02)


def test_missing_assay_or_price_raises(terms):
    with pytest.raises(KeyError, match="As"):
        value_concentrate({k: v for k, v in ASSAYS.items() if k != "As"}, terms, PRICES)
    with pytest.raises(KeyError, match="Available"):
        value_concentrate(ASSAYS, terms, {"Cu": 13800.0})


def test_copper_concentrate_end_to_end_netback(provider):
    profile = provider.get_commodity_profile("copper_concentrate")
    inputs = provider.get_default_cost_inputs("copper_concentrate", "lobito_qingdao")
    assert inputs.price_basis == pytest.approx(3697.3734, abs=0.001)
    result = compute_concentrate_netback(inputs, provider.get_route("lobito_qingdao"),
                                         profile, provider.get_metal_prices("copper_concentrate"))
    assert result.freight_cost == pytest.approx(49.7238, abs=0.001)
    assert result.insurance_cost == pytest.approx(6.1007, abs=0.001)
    assert result.financing_cost == pytest.approx(44.7737, abs=0.001)
    assert result.result_price == pytest.approx(3590.7752, abs=0.005)
    # the waterfall starts from the payables, and quality is not double-counted
    assert result.price_build_up[0][0] == "Payable Cu"
    assert "Quality adjustment" not in [label for label, _ in result.breakdown]


def test_price_build_up_must_match_price_and_mode(provider):
    profile = provider.get_commodity_profile("copper_concentrate")
    inputs = provider.get_default_cost_inputs("copper_concentrate", "lobito_qingdao")
    route = provider.get_route("lobito_qingdao")
    with pytest.raises(ValueError, match="sums to"):
        compute_netback(inputs, route, profile, price_build_up=[("Payable Cu", 1.0)])
    with pytest.raises(ValueError, match="netback mode"):
        compute_netback(inputs, route, profile, mode="landed_cost",
                        price_build_up=[("Payable Cu", inputs.price_basis)])
