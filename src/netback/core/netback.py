"""Netback orchestrator: combines all cost modules in both directions.

- ``netback`` (backward): CIF sale price -> deductions -> equivalent FOB netback.
- ``landed_cost`` (forward): FOB price -> additions -> delivered CIF/DAP cost.

Both modes share the same cost modules; only the sign of the cost legs flips.
The quality adjustment keeps its own sign in both modes (a premium cargo has a
higher netback and a higher delivered value).

All figures in the returned ``NetbackResult`` are $/unit, on the same basis as
``inputs.price_basis``, so the breakdown maps directly onto a waterfall chart.
"""

from typing import Literal

from netback.core.financing import financing_cost
from netback.core.freight import freight_cost
from netback.core.insurance import insurance_cost
from netback.core.port_fees import port_fees_total
from netback.core.quality_adjustment import quality_adjustment
from netback.models.schemas import CommodityProfile, CostInputs, NetbackResult, Route

_RESULT_LABEL = {"netback": "FOB netback", "landed_cost": "Landed cost"}


def compute_netback(inputs: CostInputs, route: Route, profile: CommodityProfile,
                    mode: Literal["netback", "landed_cost"] = "netback") -> NetbackResult:
    if mode not in _RESULT_LABEL:
        raise ValueError(f"mode must be 'netback' or 'landed_cost', got {mode!r}")

    q = inputs.quantity
    base = inputs.price_basis

    freight = freight_cost(q, inputs.freight_rate_per_unit) / q
    insurance = insurance_cost(base, freight, inputs.insurance_rate_pct)
    financing = financing_cost(base, q, inputs.financing_rate_annual_pct,
                               route.transit_days, inputs.payment_terms_days) / q
    ports = port_fees_total(q, inputs.load_port_fee_per_unit,
                            inputs.discharge_port_fee_per_unit) / q
    commission = base * inputs.commission_pct / 100.0
    quality = quality_adjustment(profile.quality_adjustment_fn,
                                 inputs.actual_quality, profile.benchmark_spec,
                                 profile.quality_params)

    sign = -1.0 if mode == "netback" else 1.0
    result = base + sign * (freight + insurance + financing + ports + commission) + quality

    breakdown = [
        ("Base price", base),
        ("Freight", sign * freight),
        ("Insurance", sign * insurance),
        ("Financing", sign * financing),
        ("Port fees", sign * ports),
        ("Commission", sign * commission),
        ("Quality adjustment", quality),
        (_RESULT_LABEL[mode], result),
    ]

    return NetbackResult(
        mode=mode,
        base_price=base,
        freight_cost=freight,
        insurance_cost=insurance,
        financing_cost=financing,
        port_fees_total=ports,
        quality_adjustment=quality,
        commission_cost=commission,
        result_price=result,
        breakdown=breakdown,
    )
