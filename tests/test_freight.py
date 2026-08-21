from netback.core.freight import freight_cost


def test_freight_cost_hand_case():
    # 55 000 t at 22 $/t
    assert freight_cost(55_000, 22.0) == 1_210_000.0


def test_freight_cost_zero_rate():
    assert freight_cost(55_000, 0.0) == 0.0


def test_freight_cost_per_unit_basis():
    # Called with quantity=1, returns the per-unit rate unchanged.
    assert freight_cost(1, 22.0) == 22.0
