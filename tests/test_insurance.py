import pytest

from netback.core.insurance import insurance_cost


def test_insurance_cost_hand_case():
    # (100 + 10) x 1.10 = 121 insured value, at 1 % -> 1.21
    assert insurance_cost(100.0, 10.0, 1.0) == pytest.approx(1.21)


def test_insurance_cost_zero_rate():
    assert insurance_cost(100.0, 10.0, 0.0) == 0.0


def test_insurance_uses_110_pct_of_cif_value():
    # 0.4 % on (75 + 22) x 1.10 = 106.7 -> 0.4268
    assert insurance_cost(75.0, 22.0, 0.4) == pytest.approx(0.4268)
