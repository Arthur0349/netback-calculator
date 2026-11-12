"""Static data provider: serves the reference tables in ``data/reference/``.

Feeds every input the engine needs for a (commodity, route) pair from the
bundled JSON files. Keys starting with ``_`` in the JSON are documentation
(sources, bases) and are ignored here.
"""

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from netback.core.concentrate import value_concentrate
from netback.core.voyage import VoyageInputs
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

    @cached_property
    def _vessels(self) -> dict[str, Any]:
        return _load("vessels.json")

    @cached_property
    def _lanes(self) -> dict[str, Any]:
        return _load("sea_lanes.json")

    def _spec(self, commodity: str) -> dict[str, Any]:
        try:
            return self._specs[commodity]
        except KeyError:
            raise KeyError(
                f"Unknown commodity {commodity!r}. "
                f"Available: {sorted(self._specs)}"
            ) from None

    @property
    def as_of(self) -> str:
        """Date label of the reference figures (documentation key)."""
        raw = json.loads((self._dir / "commodity_specs.json").read_text())
        return raw.get("_as_of", "")

    @property
    def is_live(self) -> bool:
        return False

    @property
    def data_note(self) -> str:
        """One sentence on where the figures come from, for page captions."""
        return ("Reference prices, freight and port fees are static, "
                f"indicative figures as of {self.as_of}.")

    def list_commodities(self) -> list[str]:
        return sorted(self._specs)

    def get_commodity_profile(self, commodity: str,
                              route_id: str | None = None) -> CommodityProfile:
        profile = CommodityProfile(**self._spec(commodity)["profile"])
        if route_id is None or profile.concentrate_terms is None:
            return profile
        market = self.get_destination_market(route_id)
        terms = profile.concentrate_terms
        rcs = market.get("refining_charges", {})
        payables = [p.model_copy(update={"refining_charge": rcs[p.element]})
                    if p.element in rcs else p for p in terms.payables]
        terms = terms.model_copy(update={
            "payables": payables,
            "treatment_charge": market.get("treatment_charge",
                                           terms.treatment_charge)})
        return profile.model_copy(update={"concentrate_terms": terms})

    def get_destination_market(self, route_id: str) -> dict:
        self.get_route(route_id)                     # validates the id
        market = self._routes[route_id].get("market", {})
        return {k: v for k, v in market.items() if not k.startswith("_")}

    def get_metal_prices(self, commodity: str) -> dict[str, float]:
        return {k: float(v) for k, v in
                self._spec(commodity).get("metal_prices", {}).items()}

    def _concentrate_value(self, commodity: str, assays: dict[str, float],
                           route_id: str | None = None) -> float:
        profile = self.get_commodity_profile(commodity, route_id)
        return value_concentrate(assays, profile.concentrate_terms,
                                 self.get_metal_prices(commodity)).net_value

    def get_benchmark_price(self, commodity: str) -> float:
        spec = self._spec(commodity)
        profile = self.get_commodity_profile(commodity)
        if profile.concentrate_terms is not None and "metal_prices" in spec:
            return self._concentrate_value(commodity, profile.benchmark_spec)
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
        if price_basis is None:
            if self.get_commodity_profile(commodity).concentrate_terms is not None:
                price_basis = self._concentrate_value(
                    commodity, defaults["actual_quality"], route_id)
            else:
                price_basis = (self.get_benchmark_price(commodity)
                               + self.get_destination_market(route_id)
                               .get("price_differential", 0.0))
        return CostInputs(
            quantity=quantity if quantity is not None else defaults["quantity"],
            price_basis=price_basis,
            freight_rate_per_unit=self.get_freight_rate(route),
            insurance_rate_pct=defaults["insurance_rate_pct"],
            financing_rate_annual_pct=defaults["financing_rate_annual_pct"],
            payment_terms_days=defaults["payment_terms_days"],
            load_port_fee_per_unit=self.get_port_fee(route.load_port, "load"),
            discharge_port_fee_per_unit=self.get_port_fee(route.discharge_port, "discharge"),
            actual_quality=dict(defaults["actual_quality"]),
            commission_pct=defaults["commission_pct"],
            delivery_term=defaults.get("delivery_term", "CIF"),
        )

    # --- voyage estimate and map ---------------------------------------------

    @property
    def bunker_price(self) -> float:
        """Reference bunker price, USD per tonne of fuel."""
        return float(self._vessels["bunkers"]["vlsfo_usd_per_t"])

    def get_vessel(self, vessel_type: str) -> dict[str, Any]:
        """Vessel class reference card (name, cargo unit, intake, speeds,
        consumption, port time and costs)."""
        classes = self._vessels["classes"]
        try:
            return dict(classes[vessel_type])
        except KeyError:
            raise KeyError(
                f"Unknown vessel class {vessel_type!r}. "
                f"Available: {sorted(classes)}"
            ) from None

    def get_voyage_inputs(self, route_id: str) -> VoyageInputs:
        route = self.get_route(route_id)
        vessel = self.get_vessel(route.vessel_type)
        fields = {k: v for k, v in vessel.items()
                  if k not in ("name", "cargo_unit")}
        overrides = {k: v for k, v in
                     self._routes[route_id].get("voyage", {}).items()
                     if not k.startswith("_")}
        return VoyageInputs(**{
            **fields,
            "distance_nm": route.distance_nm,
            "bunker_price": self.bunker_price,
            "commission_pct": self._vessels["commission_pct"],
            "sea_margin_pct": self._vessels["sea_margin_pct"],
            **overrides,
        })

    def get_port_position(self, port: str) -> tuple[float, float]:
        try:
            entry = self._ports[port]
        except KeyError:
            raise KeyError(
                f"Unknown port {port!r}. Available: {sorted(self._ports)}"
            ) from None
        return float(entry["lat"]), float(entry["lon"])

    def get_route_path(self, route_id: str) -> list[tuple[float, float]]:
        route = self.get_route(route_id)
        waypoints = self._lanes["waypoints"]
        lane = self._lanes["lanes"].get(route_id, [])
        return ([self.get_port_position(route.load_port)]
                + [(float(waypoints[w][0]), float(waypoints[w][1])) for w in lane]
                + [self.get_port_position(route.discharge_port)])
