"""Voyage estimate, checked against a hand-computed voyage.

6,000 nm laden and 6,000 nm ballast at 12.5 kn, no sea margin:
    sea days 6,000 / (12.5 x 24) = 20 each way | port 3 + 2 = 5 | total 45
    bunkers 20 x 40 + 20 x 30 = 1,400 t at sea, 5 x 5 = 25 t in port
    bunker cost 1,425 x 500 = 712,500 | ports 100,000 + 150,000
    voyage costs = 962,500
Hire 20,000 $/day:
    hire 45 x 20,000 = 900,000
    gross freight (900,000 + 962,500) / 0.95 = 1,960,526.32
    rate / 100,000 t = 19.605263 | commission 98,026.32
Bunkers +100 $/t: 1,425 x 100 / 0.95 / 100,000 = +1.50 $/t
"""

import pytest

from netback.core.voyage import (VoyageInputs, at_speed, bunker_delta,
                                 freight_from_hire, tce_from_freight,
                                 voyage_sensitivity)
from netback.data.providers import StaticDataProvider


@pytest.fixture
def voyage():
    return VoyageInputs(
        distance_nm=6000, ballast_pct=100, cargo_intake=100_000,
        speed_laden_kn=12.5, speed_ballast_kn=12.5, sea_margin_pct=0,
        cons_laden_tpd=40, cons_ballast_tpd=30, cons_port_tpd=5,
        port_days_load=3, port_days_discharge=2, bunker_price=500,
        port_cost_load=100_000, port_cost_discharge=150_000,
        commission_pct=5.0)


def test_freight_from_hire_reference_voyage(voyage):
    e = freight_from_hire(voyage, 20_000)
    assert (e.days_laden, e.days_ballast, e.days_port) == (20, 20, 5)
    assert e.days_total == 45
    assert e.bunkers_t == 1425
    assert e.bunker_cost == 712_500
    assert e.voyage_costs == 962_500
    assert e.hire_cost == 900_000
    assert e.gross_freight == pytest.approx(1_960_526.32, abs=0.01)
    assert e.commission == pytest.approx(98_026.32, abs=0.01)
    assert e.freight_rate == pytest.approx(19.605263, abs=1e-6)
    assert e.tce == pytest.approx(20_000)
    assert e.bunker_share == pytest.approx(712_500 / 1_960_526.32, abs=1e-6)


def test_breakdown_sums_to_the_rate(voyage):
    e = freight_from_hire(voyage, 20_000)
    assert sum(v for _, v in e.breakdown) == pytest.approx(e.freight_rate)
    assert [label for label, _ in e.breakdown] == [
        "Hire", "Bunkers", "Port costs", "Canal dues", "Commission"]


def test_tce_is_the_inverse_of_freight(voyage):
    rate = freight_from_hire(voyage, 20_000).freight_rate
    assert tce_from_freight(voyage, rate).tce == pytest.approx(20_000)
    for hire in (0.0, 7_500.0, 60_000.0):
        rate = freight_from_hire(voyage, hire).freight_rate
        assert tce_from_freight(voyage, rate).tce == pytest.approx(hire)


def test_tce_goes_negative_below_voyage_costs(voyage):
    # 9.00 $/t x 100,000 x 0.95 = 855,000 < 962,500 of voyage costs
    e = tce_from_freight(voyage, 9.0)
    assert e.tce == pytest.approx((855_000 - 962_500) / 45)
    assert e.tce < 0


def test_sea_margin_canal_and_ballast(voyage):
    v = voyage.model_copy(update={"sea_margin_pct": 5.0, "canal_days": 1.0,
                                  "canal_dues": 400_000, "ballast_pct": 50.0})
    e = freight_from_hire(v, 20_000)
    assert e.days_laden == pytest.approx(21.0)
    assert e.days_ballast == pytest.approx(10.5)
    assert e.days_total == pytest.approx(21.0 + 10.5 + 5 + 1)
    # waiting for the canal burns port consumption: (5 + 1) x 5 = 30 t
    assert e.bunkers_port_t == pytest.approx(30.0)
    assert e.canal_dues == 400_000
    assert dict(e.breakdown)["Canal dues"] == pytest.approx(4.0)


def test_bunker_delta_matches_a_repricing(voyage):
    assert bunker_delta(voyage) == pytest.approx(1.5)
    up = voyage.model_copy(update={"bunker_price": 600.0})
    assert (freight_from_hire(up, 20_000).freight_rate
            - freight_from_hire(voyage, 20_000).freight_rate) == pytest.approx(1.5)


def test_cube_law_slow_steaming(voyage):
    slow = at_speed(voyage, -1.0)
    assert slow.speed_laden_kn == 11.5
    assert slow.cons_laden_tpd == pytest.approx(40 * (11.5 / 12.5) ** 3)
    assert slow.cons_ballast_tpd == pytest.approx(30 * (11.5 / 12.5) ** 3)
    # slower: more days, but less fuel over the voyage
    a, b = freight_from_hire(voyage, 20_000), freight_from_hire(slow, 20_000)
    assert b.days_total > a.days_total and b.bunkers_t < a.bunkers_t


def test_sensitivity_rows(voyage):
    base, rows = voyage_sensitivity(voyage, hire_per_day=20_000)
    by = {r.driver: r for r in rows}
    assert base == pytest.approx(19.605263, abs=1e-6)
    assert by["Bunker price"].delta_high == pytest.approx(1.5)
    assert by["Bunker price"].delta_low == pytest.approx(-1.5)
    # hire +10 %: 90,000 / 0.95 / 100,000
    assert by["Hire"].delta_high == pytest.approx(0.947368, abs=1e-6)
    assert rows == sorted(rows, key=lambda r: r.swing, reverse=True)

    base, rows = voyage_sensitivity(voyage, freight_rate=19.605263)
    by = {r.driver: r for r in rows}
    assert base == pytest.approx(20_000, abs=0.01)
    assert "Hire" not in by
    assert by["Bunker price"].delta_high == pytest.approx(-142_500 / 45)
    with pytest.raises(ValueError, match="exactly one"):
        voyage_sensitivity(voyage)


def test_reference_voyages_are_plausible():
    """Every reference route has a vessel class, and its reference freight
    rate implies a TCE a broker would not laugh at."""
    p = StaticDataProvider()
    for rid in p.list_routes():
        route = p.get_route(rid)
        v = p.get_voyage_inputs(rid)
        assert v.distance_nm == route.distance_nm
        e = tce_from_freight(v, p.get_freight_rate(route))
        assert 5_000 < e.tce < 60_000, (rid, e.tce)
        # transit days in routes.json follow the same speed convention
        allowance = v.canal_days
        assert abs(e.days_laden + allowance - route.transit_days) <= 0.75, rid


def test_route_voyage_overrides():
    p = StaticDataProvider()
    v = p.get_voyage_inputs("ras_tanura_rotterdam")       # laden via Suez
    assert (v.canal_dues, v.canal_days, v.ballast_pct) == (420_000, 1.0, 60.0)
    assert p.get_voyage_inputs("ras_tanura_ningbo").canal_dues == 0
    with pytest.raises(KeyError, match="Unknown vessel class"):
        p.get_vessel("Rowing boat")


def test_route_paths_run_port_to_port():
    p = StaticDataProvider()
    for rid in p.list_routes():
        route, path = p.get_route(rid), p.get_route_path(rid)
        assert path[0] == p.get_port_position(route.load_port)
        assert path[-1] == p.get_port_position(route.discharge_port)
        assert len(path) >= 4, rid                 # a sea lane, not a chord
        assert all(-90 <= lat <= 90 and -180 <= lon <= 180 for lat, lon in path)
