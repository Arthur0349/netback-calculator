"""Abstract data provider interface.

The core engine never talks to a data source directly: everything it needs is
built into ``CostInputs`` / ``Route`` / ``CommodityProfile`` by a provider that
implements this interface. Swapping the static reference tables for a live
source (Platts, Baltic Exchange, ...) means writing one new provider — the
engine and the app do not change.

Lookup failures raise ``KeyError`` with a message listing what is available,
matching the convention of the quality-adjustment registry.
"""

from abc import ABC, abstractmethod

from netback.core.voyage import VoyageInputs
from netback.models.schemas import CommodityProfile, CostInputs, Route

Direction = str  # "load" | "discharge"


class PriceDataProvider(ABC):

    @abstractmethod
    def list_commodities(self) -> list[str]:
        """Keys of every commodity the provider knows about."""

    @abstractmethod
    def get_commodity_profile(self, commodity: str,
                              route_id: str | None = None) -> CommodityProfile:
        """Validated profile for a commodity key. With a route, concentrate
        terms carry that destination smelter's TC/RCs."""

    @abstractmethod
    def get_destination_market(self, route_id: str) -> dict:
        """Destination pricing for a route: ``price_differential`` ($/unit vs
        the benchmark) for index-priced commodities, ``treatment_charge`` and
        ``refining_charges`` for concentrates. Empty if none."""

    @abstractmethod
    def get_benchmark_price(self, commodity: str) -> float:
        """Benchmark price in $/unit on the basis documented in the data.
        For concentrates: the valuation of the benchmark assays."""

    @abstractmethod
    def get_metal_prices(self, commodity: str) -> dict[str, float]:
        """Metal prices used to value a concentrate ($/t base metals, $/oz
        precious). Empty for commodities priced off a flat index."""

    @abstractmethod
    def list_routes(self, commodity: str | None = None) -> list[str]:
        """Route ids, optionally filtered to one commodity."""

    @abstractmethod
    def get_route(self, route_id: str) -> Route:
        """Validated route for a route id."""

    @abstractmethod
    def get_freight_rate(self, route: Route) -> float:
        """Freight rate in $/unit for a route (matched on ports + vessel)."""

    @abstractmethod
    def get_port_fee(self, port: str, direction: Direction) -> float:
        """Port fee in $/unit, ``direction`` is "load" or "discharge"."""

    @abstractmethod
    def get_default_cost_inputs(self, commodity: str, route_id: str,
                                price_basis: float | None = None,
                                quantity: float | None = None) -> CostInputs:
        """A fully populated ``CostInputs`` for one commodity on one route,
        using reference defaults for every field the caller does not override.
        ``price_basis`` defaults to the commodity's benchmark price (for
        concentrates: the valuation of the default cargo assays)."""

    @abstractmethod
    def get_voyage_inputs(self, route_id: str) -> VoyageInputs:
        """Reference voyage estimate for a route: the vessel class of the
        route, its distance, bunker price, port and canal costs. Feeds
        ``core.voyage`` (freight from hire, TCE from freight)."""

    @abstractmethod
    def get_route_path(self, route_id: str) -> list[tuple[float, float]]:
        """Sea lane of a route as ``(lat, lon)`` points, load port first,
        discharge port last. For maps only, not for distances."""
