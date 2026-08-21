"""Pydantic schemas for the netback calculation engine.

Conventions used throughout the engine:

- All monetary amounts in ``NetbackResult`` are expressed **per unit** of the
  commodity (e.g. USD per dmt), on the same basis as ``price_basis``. This is
  the natural basis for a waterfall chart (sale price -> deductions -> netback)
  and for trader comparisons across routes.
- All ``*_pct`` fields are expressed in percent, not fractions:
  ``insurance_rate_pct = 0.4`` means 0.4 %.
"""

from typing import Literal

from pydantic import BaseModel, Field


class CommodityProfile(BaseModel):
    """Configuration profile for a commodity. The engine itself is
    commodity-agnostic: everything specific lives here."""

    name: str                       # "Bauxite", "Spodumene concentrate"
    unit: str                       # "dmt", "wmt", "mt"
    benchmark_spec: dict[str, float]        # e.g. {"Al2O3": 49.0, "SiO2": 5.0}
    quality_adjustment_fn: str      # key into the quality-adjustment registry
    quality_params: dict[str, float] = Field(default_factory=dict)
    # parameters for the adjustment function, e.g. {"price_per_unit_alumina": 1.5}


class Route(BaseModel):
    load_port: str
    discharge_port: str
    distance_nm: float = Field(gt=0)        # nautical miles
    transit_days: float = Field(gt=0)
    vessel_type: str                        # "Handysize", "Panamax", "Capesize"...


class CostInputs(BaseModel):
    quantity: float = Field(gt=0)
    price_basis: float = Field(gt=0)        # $/unit, CIF or FOB depending on mode
    freight_rate_per_unit: float = Field(ge=0)      # $/unit
    insurance_rate_pct: float = Field(ge=0)         # % of insured value
    financing_rate_annual_pct: float = Field(ge=0)  # annualised cost of capital, %
    payment_terms_days: float = Field(ge=0)
    load_port_fee_per_unit: float = Field(ge=0)
    discharge_port_fee_per_unit: float = Field(ge=0)
    actual_quality: dict[str, float]        # measured quality of the cargo
    commission_pct: float = Field(default=0.0, ge=0)


class NetbackResult(BaseModel):
    """All monetary fields are $/unit. Cost fields are positive magnitudes;
    ``quality_adjustment`` keeps its sign (premium > 0, penalty < 0)."""

    mode: Literal["netback", "landed_cost"]
    base_price: float
    freight_cost: float
    insurance_cost: float
    financing_cost: float
    port_fees_total: float
    quality_adjustment: float
    commission_cost: float
    result_price: float                     # FOB netback or landed cost, $/unit
    breakdown: list[tuple[str, float]]      # waterfall chart: base, signed deltas, result
