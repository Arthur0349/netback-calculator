"""Marine cargo insurance. Standard market convention (Institute Cargo
Clauses): the insured value is 110 % of the CIF value.

The caller supplies the CIF value, because what it is depends on the
direction of the calculation: in landed-cost mode it is built up as FOB +
freight; in netback mode the sale price already *is* the CIF value (adding
freight on top of it again would count freight twice).
"""

INSURED_VALUE_FACTOR = 1.10


def insurance_cost(cif_value: float, insurance_rate_pct: float) -> float:
    """Insurance cost on the same basis (per-unit or total) as ``cif_value``.

    insured_value = cif_value x 1.10
    insurance_cost = insured_value x insurance_rate_pct / 100
    """
    return cif_value * INSURED_VALUE_FACTOR * insurance_rate_pct / 100.0
