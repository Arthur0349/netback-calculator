"""Sensitivity and breakeven analysis on top of the netback engine.

- ``tornado``: shock one driver at a time, down and up, and report the result
  each way. Sorted by swing, it is the data behind a tornado chart: which
  assumption the netback actually hangs on.
- ``breakeven``: the value of one driver (freight, price, a metal price) at
  which the result hits a target, e.g. the highest freight a deal can bear.
  The engine is linear in each of these drivers, so two evaluations solve it
  exactly.

Pure functions, no I/O.
"""

from typing import Literal

from pydantic import BaseModel

from netback.core.netback import compute_result
from netback.models.schemas import CommodityProfile, CostInputs, Route

Mode = Literal["netback", "landed_cost"]


class SensitivityRow(BaseModel):
    driver: str
    shock: str              # e.g. "±10 %", "±1 pt", "±50 USD/dmt"
    low: float              # result with the driver shocked down
    high: float             # result with the driver shocked up
    delta_low: float        # low - base
    delta_high: float       # high - base

    @property
    def swing(self) -> float:
        return max(abs(self.delta_low), abs(self.delta_high))


def _run(inputs, route, profile, mode, prices) -> float:
    return compute_result(inputs, route, profile, mode, prices).result_price


def tornado(inputs: CostInputs, route: Route, profile: CommodityProfile,
            mode: Mode = "netback", metal_prices: dict[str, float] | None = None,
            shock_pct: float = 10.0, grade_shock: float = 1.0,
            tc_shock: float = 50.0) -> tuple[float, list[SensitivityRow]]:
    """Base result and one row per driver, largest swing first.

    Relative shocks (``shock_pct``) on prices, freight, financing rate,
    transit time and port fees; absolute shocks on the main grade and on
    moisture (``grade_shock`` points) and on the TC (``tc_shock`` $/dmt).
    Drivers with no effect on the result are dropped.
    """
    prices = dict(metal_prices or {})
    k = shock_pct / 100.0
    pct = f"±{shock_pct:g} %"
    base = _run(inputs, route, profile, mode, prices)
    cases: list[tuple[str, str, tuple, tuple]] = []

    def add(driver, shock, low, high):
        full = lambda v: (v.get("inputs", inputs), v.get("route", route),
                          v.get("profile", profile), v.get("prices", prices))
        cases.append((driver, shock, full(low), full(high)))

    def scaled_inputs(**fields):
        return ({"inputs": inputs.model_copy(update={
                    f: getattr(inputs, f) * (1 - k) for f in fields})},
                {"inputs": inputs.model_copy(update={
                    f: getattr(inputs, f) * (1 + k) for f in fields})})

    terms = profile.concentrate_terms
    if terms is not None:
        for key in dict.fromkeys(p.price_key for p in terms.payables):
            if key in prices:
                add(f"{key} price", pct,
                    {"prices": {**prices, key: prices[key] * (1 - k)}},
                    {"prices": {**prices, key: prices[key] * (1 + k)}})
        add("TC", f"±{tc_shock:g} USD/{profile.unit}",
            {"profile": profile.model_copy(update={"concentrate_terms": terms.model_copy(
                update={"treatment_charge": terms.treatment_charge - tc_shock})})},
            {"profile": profile.model_copy(update={"concentrate_terms": terms.model_copy(
                update={"treatment_charge": terms.treatment_charge + tc_shock})})})
    else:
        add("Delivered price" if mode == "netback" else "FOB price", pct,
            *scaled_inputs(price_basis=1))

    add("Freight rate", pct, *scaled_inputs(freight_rate_per_unit=1))
    add("Financing rate", pct, *scaled_inputs(financing_rate_annual_pct=1))
    add("Transit time", pct,
        {"route": route.model_copy(update={"transit_days": route.transit_days * (1 - k)})},
        {"route": route.model_copy(update={"transit_days": route.transit_days * (1 + k)})})
    add("Port fees", pct, *scaled_inputs(load_port_fee_per_unit=1,
                                         discharge_port_fee_per_unit=1))

    def quality_shift(key):
        q = inputs.actual_quality
        return ({"inputs": inputs.model_copy(update={"actual_quality": {
                    **q, key: max(0.0, q[key] - grade_shock)}})},
                {"inputs": inputs.model_copy(update={"actual_quality": {
                    **q, key: q[key] + grade_shock}})})

    moisture_key = profile.freight_moisture_key
    grade_key = next((key for key in profile.benchmark_spec
                      if key != moisture_key and key in inputs.actual_quality), None)
    pt = f"±{grade_shock:g} pt"
    if grade_key is not None:
        add(f"{grade_key} grade", pt, *quality_shift(grade_key))
    if moisture_key is not None and moisture_key in inputs.actual_quality:
        add("Moisture", pt, *quality_shift(moisture_key))

    rows = []
    for driver, shock, low, high in cases:
        lo, hi = _run(low[0], low[1], low[2], mode, low[3]), \
                 _run(high[0], high[1], high[2], mode, high[3])
        row = SensitivityRow(driver=driver, shock=shock, low=lo, high=hi,
                             delta_low=lo - base, delta_high=hi - base)
        if row.swing > 1e-9:
            rows.append(row)
    rows.sort(key=lambda r: r.swing, reverse=True)
    return base, rows


def breakeven(inputs: CostInputs, route: Route, profile: CommodityProfile,
              target: float, driver: str, mode: Mode = "netback",
              metal_prices: dict[str, float] | None = None) -> float | None:
    """Value of ``driver`` at which the result equals ``target``.

    ``driver``: ``"freight"`` (freight rate, quoted basis), ``"price"``
    (``price_basis``) or ``"metal:<key>"`` (a concentrate metal price).
    Returns ``None`` when the driver does not move the result or the
    solution would be negative.
    """
    prices = dict(metal_prices or {})

    if driver == "freight":
        x0 = inputs.freight_rate_per_unit
        run = lambda x: _run(inputs.model_copy(update={"freight_rate_per_unit": x}),
                             route, profile, mode, prices)
    elif driver == "price":
        x0 = inputs.price_basis
        run = lambda x: _run(inputs.model_copy(update={"price_basis": x}),
                             route, profile, mode, prices)
    elif driver.startswith("metal:"):
        key = driver.split(":", 1)[1]
        if key not in prices:
            raise KeyError(f"No metal price for {key!r}. Available: {sorted(prices)}")
        x0 = prices[key]
        run = lambda x: _run(inputs, route, profile, mode, {**prices, key: x})
    else:
        raise ValueError(f"Unknown breakeven driver {driver!r}")

    x1 = x0 + max(1.0, abs(x0) * 0.01)
    y0, y1 = run(x0), run(x1)
    slope = (y1 - y0) / (x1 - x0)
    if abs(slope) < 1e-12:
        return None
    x = x0 + (target - y0) / slope
    return x if x >= 0 else None
