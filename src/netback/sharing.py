"""Shareable case links: one Calculator case as URL query parameters.

A case is everything the result depends on that the user can edit:
commodity, route, direction, the cost inputs, the cargo quality or assays
and, for concentrates, the metal prices and smelter terms. Encoded as short,
readable query parameters (no opaque blob), so a link can be read and edited
by hand:

    ?c=copper_concentrate&r=lobito_qingdao&m=netback&term=CIF&q=10000&f=45...

Decoding is tolerant by design: a link is user input. Unknown keys, values
that do not parse and non-finite numbers are dropped, never raised; whatever
is missing falls back to the reference defaults.

Pure functions, no Streamlit.
"""

import math
from collections.abc import Mapping

from pydantic import BaseModel, Field

from netback.models.schemas import (DELIVERY_TERM_LEGS, ConcentrateTerms,
                                    CostInputs, Route)

MODES = ("netback", "landed_cost")

# query key -> CostInputs field
NUMERIC_FIELDS = {
    "p": "price_basis",
    "q": "quantity",
    "f": "freight_rate_per_unit",
    "ins": "insurance_rate_pct",
    "fin": "financing_rate_annual_pct",
    "cd": "payment_terms_days",
    "lf": "load_port_fee_per_unit",
    "df": "discharge_port_fee_per_unit",
    "com": "commission_pct",
}
# manual routes (commodities without reference routes)
ROUTE_TEXT = {"lp": "load_port", "dp": "discharge_port", "vt": "vessel_type"}
ROUTE_NUMERIC = {"nm": "distance_nm", "td": "transit_days"}

QUALITY, METAL, RC = "x.", "px.", "rc."


class CaseLink(BaseModel):
    """A decoded case. Every part is optional: an empty ``CaseLink`` means
    "reference defaults"."""
    commodity: str | None = None
    route_id: str | None = None
    mode: str | None = None
    delivery_term: str | None = None
    values: dict[str, float] = Field(default_factory=dict)    # CostInputs fields
    quality: dict[str, float] = Field(default_factory=dict)
    metal_prices: dict[str, float] = Field(default_factory=dict)
    treatment_charge: float | None = None
    refining_charges: dict[str, float] = Field(default_factory=dict)
    deal_price: float | None = None
    route_text: dict[str, str] = Field(default_factory=dict)
    route_values: dict[str, float] = Field(default_factory=dict)


def _fmt(value: float) -> str:
    """Shortest exact-enough text: 45.0 -> '45', 0.35 -> '0.35'."""
    return format(float(value), ".10g")


def _num(text: str) -> float | None:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def encode_case(commodity: str, route_id: str | None, mode: str,
                inputs: CostInputs, *, with_price: bool = True,
                metal_prices: Mapping[str, float] | None = None,
                terms: ConcentrateTerms | None = None,
                deal_price: float | None = None,
                route: Route | None = None) -> dict[str, str]:
    """Query parameters for one case. ``with_price=False`` for concentrates
    (their price is computed from assays, metal prices and terms).
    ``route`` only for manual routes (``route_id`` is None)."""
    params = {"c": commodity}
    if route_id is not None:
        params["r"] = route_id
    elif route is not None:
        params.update({k: getattr(route, f) for k, f in ROUTE_TEXT.items()})
        params.update({k: _fmt(getattr(route, f))
                       for k, f in ROUTE_NUMERIC.items()})
    params["m"] = mode
    params["term"] = inputs.delivery_term
    for key, field in NUMERIC_FIELDS.items():
        if field == "price_basis" and not with_price:
            continue
        params[key] = _fmt(getattr(inputs, field))
    for name, value in inputs.actual_quality.items():
        params[f"{QUALITY}{name}"] = _fmt(value)
    for name, value in (metal_prices or {}).items():
        params[f"{METAL}{name}"] = _fmt(value)
    if terms is not None:
        params["tc"] = _fmt(terms.treatment_charge)
        for payable in terms.payables:
            params[f"{RC}{payable.element}"] = _fmt(payable.refining_charge)
    if deal_price is not None:
        params["deal"] = _fmt(deal_price)
    return params


def decode_case(params: Mapping[str, str]) -> CaseLink:
    """Parse query parameters into a ``CaseLink``. Never raises."""
    link = CaseLink()
    for key, raw in params.items():
        text = str(raw).strip()
        if not text:
            continue
        if key == "c":
            link.commodity = text
        elif key == "r":
            link.route_id = text
        elif key == "m" and text in MODES:
            link.mode = text
        elif key == "term" and text in DELIVERY_TERM_LEGS:
            link.delivery_term = text
        elif key in ROUTE_TEXT:
            link.route_text[ROUTE_TEXT[key]] = text[:60]
        else:
            value = _num(text)
            if value is None:
                continue
            if key in NUMERIC_FIELDS:
                if value >= 0:
                    link.values[NUMERIC_FIELDS[key]] = value
            elif key in ROUTE_NUMERIC:
                if value > 0:
                    link.route_values[ROUTE_NUMERIC[key]] = value
            elif key == "tc":
                link.treatment_charge = value         # may be negative
            elif key == "deal":
                if value >= 0:
                    link.deal_price = value
            elif key.startswith(QUALITY) and value >= 0:
                link.quality[key[len(QUALITY):]] = value
            elif key.startswith(METAL) and value >= 0:
                link.metal_prices[key[len(METAL):]] = value
            elif key.startswith(RC):
                link.refining_charges[key[len(RC):]] = value
    return link
