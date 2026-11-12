import pytest
from netback.core.freight import freight_cost, wet_to_dry_rate


def test_freight_cost_hand_case():
    # 55 000 t at 22 $/t
    assert freight_cost(55_000, 22.0) == 1_210_000.0


def test_freight_cost_zero_rate():
    assert freight_cost(55_000, 0.0) == 0.0


def test_freight_cost_per_unit_basis():
    # Called with quantity=1, returns the per-unit rate unchanged.
    assert freight_cost(1, 22.0) == 22.0


def test_wet_to_dry_rate_hand_case():
    # 22.5 $/wmt at 10 % moisture: 1 dmt ships as 1/0.9 wmt -> 25.00 $/dmt
    assert wet_to_dry_rate(22.5, 10.0) == pytest.approx(25.0)


def test_wet_to_dry_rate_dry_cargo_unchanged():
    assert wet_to_dry_rate(22.5, 0.0) == 22.5


def test_wet_to_dry_rate_rejects_bad_moisture():
    with pytest.raises(ValueError):
        wet_to_dry_rate(22.5, 100.0)
