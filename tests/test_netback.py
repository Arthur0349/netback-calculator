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
    assert result.delivery_term == "CIF"
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


# --- delivery term decides which legs apply ---------------------------------

def _inputs(term: str) -> CostInputs:
    return CostInputs(**{**CASES["netback_case"]["inputs"], "delivery_term": term})


def _labels(result) -> list[str]:
    return [label for label, _ in result.breakdown]


def test_cfr_has_no_insurance_leg(profile, route):
    result = compute_netback(_inputs("CFR"), route, profile, mode="netback")
    assert result.insurance_cost == 0.0
    assert "Insurance" not in _labels(result)
    # 75 - 22 - 0.801370 - 2.5 - 0.375 - 5
    assert result.result_price == pytest.approx(44.32363, abs=0.005)


def test_cif_and_dap_insure_but_leave_unloading_to_buyer(profile, route):
    for term in ("CIF", "DAP"):
        result = compute_netback(_inputs(term), route, profile, mode="netback")
        assert result.insurance_cost == pytest.approx(0.33)
        assert result.port_fees_total == pytest.approx(2.5)   # load port only


def test_dpu_deducts_discharge_and_insures_net_of_unloading(profile, route):
    result = compute_netback(_inputs("DPU"), route, profile, mode="netback")
    assert result.port_fees_total == pytest.approx(5.5)       # 2.5 + 3.0
    # insured on the CIF value = 75 - 3 unloading -> 72 x 1.10 x 0.4 %
    assert result.insurance_cost == pytest.approx(0.3168)


def test_netback_does_not_double_count_freight_in_insurance(profile, route):
    """Regression: in netback mode the CIF sale price already contains
    freight; the insured value must not add freight on top of it."""
    result = compute_netback(_inputs("CIF"), route, profile, mode="netback")
    assert result.insurance_cost == pytest.approx(75.0 * 1.10 * 0.004)


def test_landed_cost_never_adds_load_port_fees(profile, route):
    for term in ("CFR", "CIF", "DAP"):
        result = compute_netback(_inputs(term), route, profile, mode="landed_cost")
        assert result.port_fees_total == 0.0
        assert "Port fees" not in _labels(result)
    dpu = compute_netback(_inputs("DPU"), route, profile, mode="landed_cost")
    assert dpu.port_fees_total == pytest.approx(3.0)          # unloading only


# --- wet freight vs dry pricing ---------------------------------------------

def test_wet_freight_converted_to_dry_basis(route):
    profile = CommodityProfile(**{**CASES["profile"],
                                  "benchmark_spec": {**CASES["profile"]["benchmark_spec"],
                                                     "moisture": 10.0},
                                  "freight_moisture_key": "moisture"})
    inputs = CostInputs(**{**CASES["netback_case"]["inputs"],
                           "actual_quality": {"Al2O3": 47.0, "SiO2": 6.0,
                                              "moisture": 12.0}})
    result = compute_netback(inputs, route, profile, mode="netback")
    assert result.freight_cost == pytest.approx(22.0 / 0.88)  # 25.00 $/dmt


def test_wet_freight_requires_moisture_value(route):
    profile = CommodityProfile(**{**CASES["profile"], "freight_moisture_key": "moisture"})
    with pytest.raises(KeyError, match="moisture"):
        compute_netback(_inputs("CIF"), route, profile, mode="netback")


def test_invalid_mode_rejected(profile, route):
    inputs = CostInputs(**CASES["netback_case"]["inputs"])
    with pytest.raises(ValueError):
        compute_netback(inputs, route, profile, mode="sideways")
