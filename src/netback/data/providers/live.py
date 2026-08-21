"""Live data provider — STUB only in v1.

Will later be wired to a market data source (Platts assessments, Baltic
Exchange freight, ...). It exists now so the rest of the codebase is written
against the ``PriceDataProvider`` interface, not against static files.
"""

from netback.data.providers.base import PriceDataProvider
from netback.models.schemas import CommodityProfile, CostInputs, Route

_MESSAGE = (
    "Live market data is not implemented yet — this is a v1 stub. "
    "Use StaticDataProvider, or implement PriceDataProvider against a "
    "live source (Platts, Baltic Exchange, ...)."
)


class LiveDataProvider(PriceDataProvider):

    def list_commodities(self) -> list[str]:
        raise NotImplementedError(_MESSAGE)

    def get_commodity_profile(self, commodity: str) -> CommodityProfile:
        raise NotImplementedError(_MESSAGE)

    def get_benchmark_price(self, commodity: str) -> float:
        raise NotImplementedError(_MESSAGE)

    def list_routes(self, commodity: str | None = None) -> list[str]:
        raise NotImplementedError(_MESSAGE)

    def get_route(self, route_id: str) -> Route:
        raise NotImplementedError(_MESSAGE)

    def get_freight_rate(self, route: Route) -> float:
        raise NotImplementedError(_MESSAGE)

    def get_port_fee(self, port: str, direction: str) -> float:
        raise NotImplementedError(_MESSAGE)

    def get_default_cost_inputs(self, commodity: str, route_id: str,
                                price_basis: float | None = None,
                                quantity: float | None = None) -> CostInputs:
        raise NotImplementedError(_MESSAGE)
