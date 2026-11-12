"""Netback orchestrator: combines all cost modules in both directions.

- ``netback`` (backward): delivered sale price -> deductions -> FOB netback.
- ``landed_cost`` (forward): FOB price -> additions -> delivered cost.

Which legs apply is decided by ``inputs.delivery_term`` (Incoterms 2020, see
``DELIVERY_TERM_LEGS``) and by who bears the cost:

- freight, financing and commission: always;
- insurance: CIF, DAP, DPU (not CFR, where the buyer insures);
- discharge port fees: DPU only (unloading is the buyer's under CFR/CIF/DAP);
- load port fees: seller-side costs below FOB. Deducted in netback mode
  (the netback is the seller's realisation net of loading), never added in
  landed-cost mode (a FOB price already includes loading).

The quality adjustment keeps its own sign in both modes (a premium cargo has a
higher netback and a higher delivered value).

All figures in the returned ``NetbackResult`` are $/unit, on the same basis as
``inputs.price_basis``, so the breakdown maps directly onto a waterfall chart.
Legs that do not apply under the delivery term are 0 and left out of the
breakdown.
"""

from typing import Literal

from netback.core.financing import financing_cost
from netback.core.freight import freight_cost, wet_to_dry_rate
from netback.core.insurance import insurance_cost
from netback.core.port_fees import port_fees_total
from netback.core.quality_adjustment import quality_adjustment
from netback.models.schemas import (DELIVERY_TERM_LEGS, CommodityProfile,
                                    CostInputs, NetbackResult, Route)

_RESULT_LABEL = {"netback": "FOB netback", "landed_cost": "Landed cost"}


def freight_rate_per_priced_unit(inputs: CostInputs,
                                 profile: CommodityProfile) -> float:
    """Freight rate on the commodity's pricing basis ($/dmt for ores whose
    freight is quoted per wmt, unchanged otherwise)."""
    key = profile.freight_moisture_key
    if key is None:
        return inputs.freight_rate_per_unit
    try:
        moisture = inputs.actual_quality[key]
    except KeyError:
        raise KeyError(
            f"{profile.name} freight is quoted per wet tonne: actual_quality "
            f"needs a {key!r} value to convert it to the dry basis"
        ) from None
    return wet_to_dry_rate(inputs.freight_rate_per_unit, moisture)


def compute_netback(inputs: CostInputs, route: Route, profile: CommodityProfile,
                    mode: Literal["netback", "landed_cost"] = "netback") -> NetbackResult:
    if mode not in _RESULT_LABEL:
        raise ValueError(f"mode must be 'netback' or 'landed_cost', got {mode!r}")

    q = inputs.quantity
    base = inputs.price_basis
    legs = DELIVERY_TERM_LEGS[inputs.delivery_term]

    freight = freight_cost(q, freight_rate_per_priced_unit(inputs, profile)) / q

    load_fee = inputs.load_port_fee_per_unit if mode == "netback" else 0.0
    discharge_fee = (inputs.discharge_port_fee_per_unit
                     if legs["discharge_port"] else 0.0)
    ports = port_fees_total(q, load_fee, discharge_fee) / q

    if legs["insurance"]:
        # Netback: the delivered price is the CIF value (net of unloading
        # under DPU). Landed cost: CIF value is built up as FOB + freight.
        cif_value = (base - discharge_fee if mode == "netback"
                     else base + freight)
        insurance = insurance_cost(cif_value, inputs.insurance_rate_pct)
    else:
        insurance = 0.0

    financing = financing_cost(base, q, inputs.financing_rate_annual_pct,
                               route.transit_days, inputs.payment_terms_days) / q
    commission = base * inputs.commission_pct / 100.0
    quality = quality_adjustment(profile.quality_adjustment_fn,
                                 inputs.actual_quality, profile.benchmark_spec,
                                 profile.quality_params)

    sign = -1.0 if mode == "netback" else 1.0
    result = base + sign * (freight + insurance + financing + ports + commission) + quality

    applies = {
        "Freight": True,
        "Insurance": legs["insurance"],
        "Financing": True,
        "Port fees": mode == "netback" or legs["discharge_port"],
        "Commission": True,
        "Quality adjustment": True,
    }
    values = {
        "Freight": sign * freight,
        "Insurance": sign * insurance,
        "Financing": sign * financing,
        "Port fees": sign * ports,
        "Commission": sign * commission,
        "Quality adjustment": quality,
    }
    breakdown = ([("Base price", base)]
                 + [(label, values[label]) for label, on in applies.items() if on]
                 + [(_RESULT_LABEL[mode], result)])

    return NetbackResult(
        mode=mode,
        delivery_term=inputs.delivery_term,
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
