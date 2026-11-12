"""Freight cost. The rate itself comes from the data layer; this module only
applies it, so the central calculation stays simple and auditable."""


def freight_cost(quantity: float, freight_rate_per_unit: float) -> float:
    """Total freight cost for the cargo.

    freight_cost = quantity x freight_rate_per_unit
    """
    return quantity * freight_rate_per_unit


def wet_to_dry_rate(rate_per_wet_unit: float, moisture_pct: float) -> float:
    """Convert a freight rate quoted per wet tonne into $/dry tonne.

    Dry bulk freight is paid on the wet (shipped) tonnage while ore is priced
    per dry tonne: one dmt ships as 1 / (1 - moisture) wmt.

    rate_per_dry_unit = rate_per_wet_unit / (1 - moisture_pct / 100)
    """
    if not 0.0 <= moisture_pct < 100.0:
        raise ValueError(f"moisture_pct must be in [0, 100), got {moisture_pct}")
    return rate_per_wet_unit / (1.0 - moisture_pct / 100.0)
