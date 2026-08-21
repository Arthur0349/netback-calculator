"""Static data provider: serves the reference tables in ``data/reference/``.

Feeds every input the engine needs for a (commodity, route) pair from the
bundled JSON files. Keys starting with ``_`` in the JSON are documentation
(sources, bases) and are ignored here.
"""

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from netback.data.providers.base import PriceDataProvider
from netback.models.schemas import CommodityProfile, CostInputs, Route

_REFERENCE_DIR = Path(__file__).resolve().parents[1] / "reference"


def _load(name: str) -> dict[str, Any]:
    raw = json.loads((_REFERENCE_DIR / name).read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


class StaticDataProvider(PriceDataProvider):

    def __init__(self, reference_dir: Path = _REFERENCE_DIR):
        self._dir = reference_dir

    @cached_property
    def _specs(self) -> dict[str, Any]:
        return _load("commodity_specs.json")

    @cached_property
    def _routes(self) -> dict[str, Any]:
        return _load("routes.json")

    @cached_property
    def _ports(self) -> dict[str, Any]:
        return _load("ports.json")

    @cached_property
    def _freight(self) -> dict[str, Any]:
        return _load("freight_rates.json")

    def _spec(self, commodity: str) -> dict[str, Any]:
        try:
            return self._specs[commodity]
        except KeyError:
            raise KeyError(
                f"Unknown commodity {commodity!r}. "
                f"Available: {sorted(self._specs)}"
            ) from None

    def list_commodities(self) -> list[str]:
        return sorted(self._specs)

    def get_commodity_profile(self, commodity: str) -> CommodityProfile:
        return CommodityProfile(**self._spec(commodity)["profile"])

    def get_benchmark_price(self, commodity: str) -> float:
        spec = self._spec(commodity)
        if "benchmark_price" not in spec:
            raise KeyError(
                f"No benchmark price in the reference data for {commodity!r} "
                f"(config skeleton — supply a price explicitly)"
            )
        return float(spec["benchmark_price"])

    def list_routes(self, commodity: str | None = None) -> list[str]:
        return sorted(
            rid for rid, entry in self._routes.items()
            if commodity is None or entry["commodity"] == commodity
        )

    def get_route(self, route_id: str) -> Route:
        try:
            entry = self._routes[route_id]
        except KeyError:
            raise KeyError(
                f"Unknown route {route_id!r}. Available: {sorted(self._routes)}"
            ) from None
        return Route(**entry["route"])

    def get_freight_rate(self, route: Route) -> float:
        for rid, entry in self._routes.items():
            r = entry["route"]
            if (r["load_port"] == route.load_port
                    and r["discharge_port"] == route.discharge_port
                    and r["vessel_type"] == route.vessel_type):
                return float(self._freight[rid]["freight_rate_per_unit"])
        raise KeyError(
            f"No freight rate for {route.load_port} -> {route.discharge_port} "
            f"({route.vessel_type}). Known routes: {sorted(self._routes)}"
        )

    def get_port_fee(self, port: str, direction: str) -> float:
        if direction not in ("load", "discharge"):
            raise ValueError(f"direction must be 'load' or 'discharge', got {direction!r}")
        try:
            entry = self._ports[port]
        except KeyError:
            raise KeyError(
                f"Unknown port {port!r}. Available: {sorted(self._ports)}"
            ) from None
        return float(entry[f"{direction}_fee_per_unit"])

    def get_default_cost_inputs(self, commodity: str, route_id: str,
                                price_basis: float | None = None,
                                quantity: float | None = None) -> CostInputs:
        spec = self._spec(commodity)
        if "defaults" not in spec:
            raise KeyError(
                f"No default cost inputs in the reference data for {commodity!r} "
                f"(config skeleton — build CostInputs explicitly)"
            )
        defaults = spec["defaults"]
        route = self.get_route(route_id)
        return CostInputs(
            quantity=quantity if quantity is not None else defaults["quantity"],
            price_basis=(price_basis if price_basis is not None
                         else self.get_benchmark_price(commodity)),
            freight_rate_per_unit=self.get_freight_rate(route),
            insurance_rate_pct=defaults["insurance_rate_pct"],
            financing_rate_annual_pct=defaults["financing_rate_annual_pct"],
            payment_terms_days=defaults["payment_terms_days"],
            load_port_fee_per_unit=self.get_port_fee(route.load_port, "load"),
            discharge_port_fee_per_unit=self.get_port_fee(route.discharge_port, "discharge"),
            actual_quality=dict(defaults["actual_quality"]),
            commission_pct=defaults["commission_pct"],
        )
