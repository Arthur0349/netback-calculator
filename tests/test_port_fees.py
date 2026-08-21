import pytest

from netback.core.port_fees import port_fees_total


def test_port_fees_hand_case():
    # 1000 t x (2 + 3) $/t = 5000 $
    assert port_fees_total(1000.0, 2.0, 3.0) == pytest.approx(5000.0)


def test_port_fees_zero():
    assert port_fees_total(1000.0, 0.0, 0.0) == 0.0
