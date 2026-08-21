"""Marine cargo insurance. Standard market convention (Institute Cargo
Clauses): the insured value is 110 % of the CIF value."""

INSURED_VALUE_FACTOR = 1.10


def insurance_cost(base_price: float, freight_cost: float,
                   insurance_rate_pct: float) -> float:
    """Insurance cost on the same basis (per-unit or total) as its inputs.

    insured_value = (base_price + freight_cost) x 1.10
    insurance_cost = insured_value x insurance_rate_pct / 100
    """
    insured_value = (base_price + freight_cost) * INSURED_VALUE_FACTOR
    return insured_value * insurance_rate_pct / 100.0
