"""Cost of capital tied up during transit plus payment terms."""

DAYS_PER_YEAR = 365.0


def financing_cost(base_price: float, quantity: float,
                   financing_rate_annual_pct: float,
                   transit_days: float, payment_terms_days: float) -> float:
    """Total financing cost for the cargo.

    days_exposed = transit_days + payment_terms_days
    financing_cost = (base_price x quantity) x (annual_rate / 365) x days_exposed
    """
    days_exposed = transit_days + payment_terms_days
    return (base_price * quantity) * (financing_rate_annual_pct / 100.0
                                      / DAYS_PER_YEAR) * days_exposed
