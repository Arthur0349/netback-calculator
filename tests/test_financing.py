import pytest

from netback.core.financing import financing_cost


def test_financing_cost_hand_case():
    # 100 $/t x 1000 t = 100 000 $ exposed, 7.3 %/yr = 0.02 %/day, 50 days
    # -> 100 000 x 0.0002 x 50 = 1000
    assert financing_cost(100.0, 1000.0, 7.3, 35.0, 15.0) == pytest.approx(1000.0)


def test_financing_cost_zero_rate():
    assert financing_cost(100.0, 1000.0, 0.0, 35.0, 15.0) == 0.0


def test_financing_days_exposed_is_transit_plus_terms():
    # Same total days split differently gives the same cost.
    assert financing_cost(80.0, 500.0, 6.0, 40.0, 10.0) == pytest.approx(
        financing_cost(80.0, 500.0, 6.0, 25.0, 25.0)
    )
