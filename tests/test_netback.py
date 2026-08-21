"""Integration test for the orchestrator: a full bauxite case with every value
known, checked against hand-computed figures to 2 decimal places."""

import json
from pathlib import Path

import pytest

from netback.core.netback import compute_netback
from netback.models.schemas import CommodityProfile, CostInputs, Route

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "reference_cases.json").read_text()
)


@pytest.fixture
def profile():
    return CommodityProfile(**CASES["profile"])


@pytest.fixture
def route():
    return Route(**CASES["route"])


def test_netback_full_bauxite_case(profile, route):
    case = CASES["netback_case"]
    result = compute_netback(CostInputs(**case["inputs"]), route, profile,
                             mode="netback")
    expected = case["expected"]

    assert result.mode == "netback"
    assert result.base_price == 75.0
    assert result.freight_cost == pytest.approx(expected["freight_cost"], abs=0.005)
    assert result.insurance_cost == pytest.approx(expected["insurance_cost"], abs=0.005)
    assert result.financing_cost == pytest.approx(expected["financing_cost"], abs=0.005)
    assert result.port_fees_total == pytest.approx(expected["port_fees_total"], abs=0.005)
    assert result.commission_cost == pytest.approx(expected["commission_cost"], abs=0.005)
    assert result.quality_adjustment == pytest.approx(expected["quality_adjustment"], abs=0.005)
    assert result.result_price == pytest.approx(expected["result_price"], abs=0.005)


def test_landed_cost_full_bauxite_case(profile, route):
    case = CASES["landed_cost_case"]
    result = compute_netback(CostInputs(**case["inputs"]), route, profile,
                             mode="landed_cost")
    assert result.mode == "landed_cost"
    assert result.result_price == pytest.approx(case["expected"]["result_price"], abs=0.005)


def test_breakdown_walks_from_base_to_result(profile, route):
    """The waterfall breakdown must be internally consistent:
    base + all signed deltas == final result, in both modes."""
    for mode in ("netback", "landed_cost"):
        case = CASES["netback_case"]
        result = compute_netback(CostInputs(**case["inputs"]), route, profile,
                                 mode=mode)
        base_label, base_value = result.breakdown[0]
        result_label, result_value = result.breakdown[-1]
        deltas = sum(v for _, v in result.breakdown[1:-1])

        assert base_label == "Base price"
        assert base_value == result.base_price
        assert base_value + deltas == pytest.approx(result_value)
        assert result_value == pytest.approx(result.result_price)


def test_netback_costs_are_deducted_and_landed_costs_added(profile, route):
    inputs = CostInputs(**CASES["netback_case"]["inputs"])
    backward = compute_netback(inputs, route, profile, mode="netback")
    forward = compute_netback(inputs, route, profile, mode="landed_cost")

    # Same cost magnitudes in both modes; only the direction differs.
    assert backward.freight_cost == forward.freight_cost
    assert backward.result_price < inputs.price_basis < forward.result_price


def test_invalid_mode_rejected(profile, route):
    inputs = CostInputs(**CASES["netback_case"]["inputs"])
    with pytest.raises(ValueError):
        compute_netback(inputs, route, profile, mode="sideways")
