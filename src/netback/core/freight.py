"""Freight cost. The rate itself comes from the data layer; this module only
applies it, so the central calculation stays simple and auditable."""


def freight_cost(quantity: float, freight_rate_per_unit: float) -> float:
    """Total freight cost for the cargo.

    freight_cost = quantity x freight_rate_per_unit
    """
    return quantity * freight_rate_per_unit
