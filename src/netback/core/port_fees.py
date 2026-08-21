"""Port charges at load and discharge ports."""


def port_fees_total(quantity: float, load_port_fee_per_unit: float,
                    discharge_port_fee_per_unit: float) -> float:
    """Total port fees for the cargo.

    port_fees_total = quantity x (load_fee + discharge_fee)
    """
    return quantity * (load_port_fee_per_unit + discharge_port_fee_per_unit)
