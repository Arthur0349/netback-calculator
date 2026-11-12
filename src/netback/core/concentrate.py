"""Concentrate valuation: payable metals, treatment/refining charges, penalties.

Concentrates (copper, zinc, lead...) have no flat index price. A cargo's
value per dry tonne is built from its assays under the offtake terms:

    net invoice value = sum(payable metal x metal price)
                        - TC
                        - RC x payable metal
                        - penalties on deleterious elements

The result is a delivered (typically CIF main Asian port) value in $/dmt that
the netback engine then walks back to the load port like any other price.

Conventions (standard smelter contract wording):

- Base metal assays in % ("pct"), precious metal assays in g/dmt ("g_per_t").
- Payable content = the LOWER of ``payable_pct`` of the assay and the assay
  minus ``min_deduction`` (same unit as the assay), floored at 0.
- Prices: $/t metal for "pct" elements, $/oz troy for "g_per_t" elements.
- RC: $/lb of payable metal for "pct" elements, $/oz payable for "g_per_t".
  RC is entered in dollars (copper RC of 2.0 c/lb is ``0.02``).
- TC: $/dmt of concentrate. Both TC and RC may be negative (2026 spot market:
  smelters paying miners for feed).
- Penalty: ``usd_per_step`` for every ``per_step`` of assay above
  ``threshold``, pro rata by default, or per full step only.
"""

import math

from netback.models.schemas import ConcentrateTerms, ConcentrateValuation

GRAMS_PER_TROY_OZ = 31.1035
LB_PER_TONNE = 2204.62


def payable_content(assay: float, payable_pct: float, min_deduction: float) -> float:
    """Payable content in the assay's unit (% or g/dmt).

    payable = max(0, min(assay x payable_pct / 100, assay - min_deduction))
    """
    return max(0.0, min(assay * payable_pct / 100.0, assay - min_deduction))


def penalty_charge(assay: float, threshold: float, per_step: float,
                   usd_per_step: float, pro_rata: bool = True) -> float:
    """$/dmt penalty for one deleterious element.

    steps = (assay - threshold) / per_step  (floored to full steps if not pro rata)
    penalty = max(0, steps) x usd_per_step
    """
    excess = max(0.0, assay - threshold)
    steps = excess / per_step
    if not pro_rata:
        steps = math.floor(steps + 1e-9)
    return steps * usd_per_step


def value_concentrate(assays: dict[str, float], terms: ConcentrateTerms,
                      metal_prices: dict[str, float]) -> ConcentrateValuation:
    """Net invoice value of one dry tonne of concentrate, with its build-up."""
    payables: list[tuple[str, float]] = []
    rc_total = 0.0
    details: list[tuple[str, str, float]] = []

    for p in terms.payables:
        if p.element not in assays:
            raise KeyError(f"Assay missing for payable element {p.element!r}")
        if p.price_key not in metal_prices:
            raise KeyError(f"No metal price for {p.price_key!r}. "
                           f"Available: {sorted(metal_prices)}")
        content = payable_content(assays[p.element], p.payable_pct, p.min_deduction)
        price = metal_prices[p.price_key]
        if p.unit == "pct":
            metal_t = content / 100.0
            value = metal_t * price
            rc = metal_t * LB_PER_TONNE * p.refining_charge
            details.append((f"Payable {p.element}", f"{content:.3f} %", value))
        else:
            oz = content / GRAMS_PER_TROY_OZ
            value = oz * price
            rc = oz * p.refining_charge
            details.append((f"Payable {p.element}", f"{content:.2f} g/dmt", value))
        payables.append((f"Payable {p.element}", value))
        if rc:
            details.append((f"RC {p.element}", "", -rc))
        rc_total += rc

    penalties = 0.0
    for pen in terms.penalties:
        if pen.element not in assays:
            raise KeyError(f"Assay missing for penalty element {pen.element!r}")
        charge = penalty_charge(assays[pen.element], pen.threshold, pen.per_step,
                                pen.usd_per_step, pen.pro_rata)
        if charge:
            details.append((f"Penalty {pen.element}",
                            f"{assays[pen.element]:g} vs {pen.threshold:g}", -charge))
        penalties += charge

    tc = terms.treatment_charge
    details.append(("TC", "", -tc))
    net = sum(v for _, v in payables) - tc - rc_total - penalties

    build_up = payables + [("TC", -tc), ("RC", -rc_total), ("Penalties", -penalties)]
    return ConcentrateValuation(
        payable_value=sum(v for _, v in payables),
        treatment_charge=tc,
        refining_charge=rc_total,
        penalties=penalties,
        net_value=net,
        build_up=build_up,
        details=details,
    )
