import pytest

from netback.core.quality_adjustment import get_adjustment_fn, quality_adjustment

BAUXITE_BENCHMARK = {"Al2O3": 49.0, "SiO2": 5.0}
BAUXITE_PARAMS = {"price_per_unit_alumina": 1.5, "penalty_per_unit_silica": 2.0}


def test_bauxite_penalty_case():
    # 2 units below on alumina (-3.0), 1 unit above on silica (-2.0) -> -5.0
    actual = {"Al2O3": 47.0, "SiO2": 6.0}
    adj = quality_adjustment("bauxite_linear", actual, BAUXITE_BENCHMARK, BAUXITE_PARAMS)
    assert adj == pytest.approx(-5.0)


def test_bauxite_premium_case():
    # 1 unit above on alumina (+1.5), silica below benchmark -> no penalty
    actual = {"Al2O3": 50.0, "SiO2": 4.0}
    adj = quality_adjustment("bauxite_linear", actual, BAUXITE_BENCHMARK, BAUXITE_PARAMS)
    assert adj == pytest.approx(1.5)


def test_bauxite_low_silica_gives_no_bonus():
    # Silica only penalises above benchmark; below it, adjustment is alumina-only.
    on_spec = {"Al2O3": 49.0, "SiO2": 1.0}
    adj = quality_adjustment("bauxite_linear", on_spec, BAUXITE_BENCHMARK, BAUXITE_PARAMS)
    assert adj == 0.0


def test_spodumene_linear_case():
    # 0.3 units below SC6 grade at 20 $/unit -> -6.0
    adj = quality_adjustment(
        "spodumene_linear",
        {"Li2O": 5.7}, {"Li2O": 6.0}, {"price_per_unit_li2o": 20.0},
    )
    assert adj == pytest.approx(-6.0)


def test_unknown_function_raises():
    with pytest.raises(KeyError, match="Unknown quality adjustment"):
        get_adjustment_fn("does_not_exist")
