"""Voyage estimate: where a freight rate comes from.

A freight rate is not a market given, it is the price at which a voyage
covers the ship. The owner's (or the charterer's time-charter) economics are:

    days      = laden sea days + ballast sea days + port days + canal days
    bunkers   = sea days x sea consumption + port days x port consumption
    costs     = bunkers x bunker price + port costs + canal dues
    freight   = (hire x days + costs) / (1 - commission)        [lumpsum]
    rate      = freight / cargo intake                          [$/t or $/bbl]

and, read the other way, the **time-charter equivalent** of a quoted rate:

    TCE       = (rate x cargo x (1 - commission) - costs) / days   [$/day]

The TCE is what the voyage pays the ship per day once the voyage costs are
out: the number an owner compares with the time-charter market, and the
number a charterer uses to tell whether a quoted rate is cheap or rich.

Both directions share one voyage profile, so ``freight_from_hire`` and
``tce_from_freight`` are exact inverses. Pure functions, no I/O.
"""

from pydantic import BaseModel, Field

HOURS_PER_DAY = 24.0


class VoyageInputs(BaseModel):
    """One voyage. ``cargo_intake`` is in the unit freight is quoted in
    (wet tonnes for dry bulk, barrels for tankers); money in USD."""

    distance_nm: float = Field(gt=0)            # laden leg
    ballast_pct: float = Field(default=100.0, ge=0)
    # ballast leg as % of the laden distance: 100 = round voyage back to the
    # load port, 0 = the ship is repositioned at someone else's cost
    cargo_intake: float = Field(gt=0)
    speed_laden_kn: float = Field(gt=0)
    speed_ballast_kn: float = Field(gt=0)
    sea_margin_pct: float = Field(default=5.0, ge=0)    # weather, currents
    cons_laden_tpd: float = Field(ge=0)         # fuel, tonnes per sea day
    cons_ballast_tpd: float = Field(ge=0)
    cons_port_tpd: float = Field(ge=0)
    port_days_load: float = Field(ge=0)         # incl. waiting for berth
    port_days_discharge: float = Field(ge=0)
    canal_days: float = Field(default=0.0, ge=0)
    bunker_price: float = Field(ge=0)           # USD per tonne of fuel
    port_cost_load: float = Field(ge=0)         # disbursements, USD lumpsum
    port_cost_discharge: float = Field(ge=0)
    canal_dues: float = Field(default=0.0, ge=0)
    commission_pct: float = Field(default=3.75, ge=0, lt=100)
    # address + brokerage commission, % of gross freight


class VoyageEstimate(BaseModel):
    """Result of a voyage estimate. Costs in USD for the voyage,
    ``freight_rate`` per unit of cargo, ``tce`` and ``hire`` per day."""

    days_laden: float
    days_ballast: float
    days_port: float
    days_canal: float
    days_total: float
    bunkers_sea_t: float
    bunkers_port_t: float
    bunkers_t: float
    bunker_cost: float
    port_costs: float
    canal_dues: float
    voyage_costs: float             # bunkers + ports + canal
    hire_cost: float                # daily earnings x days
    commission: float
    gross_freight: float            # lumpsum
    freight_rate: float             # per cargo unit
    tce: float                      # USD/day
    breakdown: list[tuple[str, float]]
    # per cargo unit, sums to ``freight_rate``: hire, bunkers, ports, canal,
    # commission

    @property
    def bunker_share(self) -> float:
        """Bunkers as a share of the gross freight."""
        return self.bunker_cost / self.gross_freight if self.gross_freight else 0.0


def _sea_days(distance_nm: float, speed_kn: float, margin_pct: float) -> float:
    return distance_nm / (speed_kn * HOURS_PER_DAY) * (1.0 + margin_pct / 100.0)


def _estimate(v: VoyageInputs, hire_cost: float | None,
              gross_freight: float | None) -> VoyageEstimate:
    days_laden = _sea_days(v.distance_nm, v.speed_laden_kn, v.sea_margin_pct)
    days_ballast = _sea_days(v.distance_nm * v.ballast_pct / 100.0,
                             v.speed_ballast_kn, v.sea_margin_pct)
    days_port = v.port_days_load + v.port_days_discharge
    days_total = days_laden + days_ballast + days_port + v.canal_days

    bunkers_sea = (days_laden * v.cons_laden_tpd
                   + days_ballast * v.cons_ballast_tpd)
    # the ship idles at port consumption while waiting for the canal convoy
    bunkers_port = (days_port + v.canal_days) * v.cons_port_tpd
    bunker_cost = (bunkers_sea + bunkers_port) * v.bunker_price
    port_costs = v.port_cost_load + v.port_cost_discharge
    voyage_costs = bunker_cost + port_costs + v.canal_dues

    net_share = 1.0 - v.commission_pct / 100.0
    if gross_freight is None:
        gross_freight = (hire_cost + voyage_costs) / net_share
    commission = gross_freight * v.commission_pct / 100.0
    if hire_cost is None:
        hire_cost = gross_freight - commission - voyage_costs

    q = v.cargo_intake
    return VoyageEstimate(
        days_laden=days_laden, days_ballast=days_ballast, days_port=days_port,
        days_canal=v.canal_days, days_total=days_total,
        bunkers_sea_t=bunkers_sea, bunkers_port_t=bunkers_port,
        bunkers_t=bunkers_sea + bunkers_port,
        bunker_cost=bunker_cost, port_costs=port_costs,
        canal_dues=v.canal_dues, voyage_costs=voyage_costs,
        hire_cost=hire_cost, commission=commission,
        gross_freight=gross_freight, freight_rate=gross_freight / q,
        tce=hire_cost / days_total,
        breakdown=[
            ("Hire", hire_cost / q),
            ("Bunkers", bunker_cost / q),
            ("Port costs", port_costs / q),
            ("Canal dues", v.canal_dues / q),
            ("Commission", commission / q),
        ],
    )


def freight_from_hire(v: VoyageInputs, hire_per_day: float) -> VoyageEstimate:
    """Freight rate that pays ``hire_per_day`` for every day of the voyage
    on top of the voyage costs."""
    days = _estimate(v, hire_cost=0.0, gross_freight=None).days_total
    return _estimate(v, hire_cost=hire_per_day * days, gross_freight=None)


def tce_from_freight(v: VoyageInputs, freight_rate: float) -> VoyageEstimate:
    """Time-charter equivalent earned at a quoted ``freight_rate`` (per
    cargo unit). Negative when the rate does not cover the voyage costs."""
    return _estimate(v, hire_cost=None,
                     gross_freight=freight_rate * v.cargo_intake)


def bunker_delta(v: VoyageInputs, bunker_move: float = 100.0) -> float:
    """Change in the freight rate for a ``bunker_move`` change in the bunker
    price at constant hire: bunkers burnt per cargo unit, grossed up for
    commission. Linear, so it scales with the move."""
    e = _estimate(v, hire_cost=0.0, gross_freight=None)
    return (e.bunkers_t * bunker_move
            / (1.0 - v.commission_pct / 100.0) / v.cargo_intake)


# --- sensitivity -------------------------------------------------------------

def at_speed(v: VoyageInputs, delta_kn: float) -> VoyageInputs:
    """The same voyage steamed ``delta_kn`` faster (or slower) on both legs.
    Daily consumption follows the cube law: fuel per day scales with the
    cube of the speed, which is why slow steaming pays when bunkers are
    dear and hire is cheap."""
    def leg(speed: float, cons: float) -> tuple[float, float]:
        new = max(1.0, speed + delta_kn)
        return new, cons * (new / speed) ** 3

    speed_l, cons_l = leg(v.speed_laden_kn, v.cons_laden_tpd)
    speed_b, cons_b = leg(v.speed_ballast_kn, v.cons_ballast_tpd)
    return v.model_copy(update={
        "speed_laden_kn": speed_l, "cons_laden_tpd": cons_l,
        "speed_ballast_kn": speed_b, "cons_ballast_tpd": cons_b})


def voyage_sensitivity(v: VoyageInputs, *, hire_per_day: float | None = None,
                       freight_rate: float | None = None,
                       shock_pct: float = 10.0, bunker_move: float = 100.0,
                       speed_move: float = 1.0, port_days_move: float = 2.0,
                       ballast_move: float = 20.0):
    """One driver shocked at a time, largest swing first.

    Give ``hire_per_day`` to see what moves the freight rate at constant
    hire, or ``freight_rate`` to see what moves the TCE at a constant rate.
    Returns ``(base, rows)`` with ``rows`` as ``SensitivityRow``.
    """
    from netback.core.sensitivity import SensitivityRow

    if (hire_per_day is None) == (freight_rate is None):
        raise ValueError("Give exactly one of hire_per_day or freight_rate")
    if hire_per_day is not None:
        run = lambda voyage, x=hire_per_day: freight_from_hire(voyage, x).freight_rate
        own = ("Hire", lambda k: freight_from_hire(v, hire_per_day * k).freight_rate)
    else:
        run = lambda voyage, x=freight_rate: tce_from_freight(voyage, x).tce
        own = ("Freight rate", lambda k: tce_from_freight(v, freight_rate * k).tce)

    k = shock_pct / 100.0
    shift = lambda **fields: v.model_copy(update=fields)
    half = port_days_move / 2.0
    cases = [
        (own[0], f"±{shock_pct:g} %", own[1](1 - k), own[1](1 + k)),
        ("Bunker price", f"±{bunker_move:g} USD/t",
         run(shift(bunker_price=max(0.0, v.bunker_price - bunker_move))),
         run(shift(bunker_price=v.bunker_price + bunker_move))),
        ("Speed", f"±{speed_move:g} kn, cube law",
         run(at_speed(v, -speed_move)), run(at_speed(v, speed_move))),
        ("Port time", f"±{port_days_move:g} d",
         run(shift(port_days_load=max(0.0, v.port_days_load - half),
                   port_days_discharge=max(0.0, v.port_days_discharge - half))),
         run(shift(port_days_load=v.port_days_load + half,
                   port_days_discharge=v.port_days_discharge + half))),
        ("Ballast leg", f"±{ballast_move:g} pts",
         run(shift(ballast_pct=max(0.0, v.ballast_pct - ballast_move))),
         run(shift(ballast_pct=v.ballast_pct + ballast_move))),
    ]
    base = run(v)
    rows = [SensitivityRow(driver=d, shock=s, low=lo, high=hi,
                           delta_low=lo - base, delta_high=hi - base)
            for d, s, lo, hi in cases]
    rows = [r for r in rows if r.swing > 1e-9]
    rows.sort(key=lambda r: r.swing, reverse=True)
    return base, rows
