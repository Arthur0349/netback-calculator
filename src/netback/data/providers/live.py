"""Live data provider: public market quotes over the static reference data.

Only what has a free, public, key-less quote goes live (see
``reference/live_sources.json``):

- concentrate metal prices: copper, gold, silver front-month futures;
- index benchmarks: Brent for crude, SGX 62 % Fe for iron ore;
- the financing rate: latest SOFR plus the credit margin implied by the
  static rate.

Everything else (freight, port fees, TC/RC, destination differentials,
bauxite) stays on the static reference tables, which is why this class
extends ``StaticDataProvider`` instead of replacing it.

Failure is the normal case to design for: every quote is fetched once, in
parallel, with a short timeout; a quote that fails, is stale or falls outside
its plausibility bounds is dropped and the static figure is served in its
place. The provider never raises because a source is down. ``quotes`` records
what happened to each source so the UI can say exactly what is live.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from netback.data.providers.quotes import fetch_sofr, fetch_yahoo_quote
from netback.data.providers.static import _REFERENCE_DIR, StaticDataProvider
from netback.models.schemas import CostInputs

Fetcher = Callable[[str], tuple[float, datetime]]
RateFetcher = Callable[[], tuple[float, datetime]]

SOFR = "SOFR"


class LiveQuote(BaseModel):
    """Outcome of one live source. ``value`` is already converted to the
    unit of the reference data; ``None`` means the static figure is used."""
    key: str                        # "Cu", "crude_oil", "SOFR"
    label: str
    value: float | None = None
    as_of: datetime | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.value is not None


class LiveDataProvider(StaticDataProvider):

    def __init__(self, fetch_quote: Fetcher = fetch_yahoo_quote,
                 fetch_rate: RateFetcher = fetch_sofr,
                 reference_dir: Path = _REFERENCE_DIR,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        super().__init__(reference_dir)
        self._fetch_quote = fetch_quote
        self._fetch_rate = fetch_rate
        self._now = now
        raw = json.loads((reference_dir / "live_sources.json").read_text())
        self._sources = {k: v for k, v in raw.items() if not k.startswith("_")}
        self.quotes: dict[str, LiveQuote] = {}
        self.fetched_at: datetime | None = None

    # --- fetching ------------------------------------------------------------

    def _fetch_one(self, key: str, source: dict) -> LiveQuote:
        label = source["label"]
        try:
            raw, as_of = self._fetch_quote(source["symbol"])
            value = round(raw * source.get("scale", 1.0)
                          + source.get("offset", 0.0), 2)
            max_age = timedelta(days=self._sources["max_quote_age_days"])
            if self._now() - as_of > max_age:
                raise ValueError(f"stale quote ({as_of:%Y-%m-%d})")
            if not source["min"] <= value <= source["max"]:
                raise ValueError(f"implausible value {value:,.2f}")
            return LiveQuote(key=key, label=label, value=value, as_of=as_of)
        except Exception as exc:                      # any failure -> static
            return LiveQuote(key=key, label=label,
                             error=f"{type(exc).__name__}: {exc}")

    def _fetch_sofr(self) -> LiveQuote:
        label = "SOFR, latest New York Fed fixing"
        try:
            value, as_of = self._fetch_rate()
            if not 0.0 <= value <= 25.0:
                raise ValueError(f"implausible value {value}")
            return LiveQuote(key=SOFR, label=label, value=value, as_of=as_of)
        except Exception as exc:
            return LiveQuote(key=SOFR, label=label,
                             error=f"{type(exc).__name__}: {exc}")

    def refresh(self) -> "LiveDataProvider":
        """Fetch every source once, in parallel. Never raises."""
        sources = {**self._sources["metals"], **self._sources["benchmarks"]}
        with ThreadPoolExecutor(max_workers=len(sources) + 1) as pool:
            jobs = {key: pool.submit(self._fetch_one, key, source)
                    for key, source in sources.items()}
            jobs[SOFR] = pool.submit(self._fetch_sofr)
            self.quotes = {key: job.result() for key, job in jobs.items()}
        self.fetched_at = self._now()
        return self

    def _live(self, key: str) -> float | None:
        if self.fetched_at is None:
            self.refresh()
        quote = self.quotes.get(key)
        return quote.value if quote is not None else None

    # --- status --------------------------------------------------------------

    @property
    def is_live(self) -> bool:
        """True when at least one source answered."""
        if self.fetched_at is None:
            self.refresh()
        return any(q.ok for q in self.quotes.values())

    def is_live_price(self, commodity: str) -> bool:
        """Whether the benchmark price of ``commodity`` rests on a live
        quote (for concentrates: on at least one live metal price)."""
        if self._live(commodity) is not None:
            return True
        return any(self._live(key) is not None
                   for key in super().get_metal_prices(commodity))

    @property
    def sofr(self) -> float | None:
        return self._live(SOFR)

    @property
    def data_note(self) -> str:
        if not self.is_live:
            return ("Live sources did not answer: " + super().data_note)
        live = [name for name, keys in (
            ("metal prices", self._sources["metals"]),
            ("crude and iron ore benchmarks", self._sources["benchmarks"]),
            ("SOFR", [SOFR]),
        ) if any(self._live(k) is not None for k in keys)]
        return (f"Live, delayed quotes for {', '.join(live)} "
                f"(fetched {self.fetched_at:%d %b %Y %H:%M} UTC). Freight, "
                "port fees, smelter terms and bauxite are static, indicative "
                f"figures as of {self.as_of}.")

    # --- overrides -----------------------------------------------------------

    def get_metal_prices(self, commodity: str) -> dict[str, float]:
        prices = super().get_metal_prices(commodity)
        return {key: self._live(key) if self._live(key) is not None else value
                for key, value in prices.items()}

    def get_benchmark_price(self, commodity: str) -> float:
        live = self._live(commodity)
        if live is not None:
            self._spec(commodity)            # same KeyError for unknown keys
            return live
        return super().get_benchmark_price(commodity)

    def financing_rate(self, static_rate_pct: float) -> float:
        """Static rate re-based on live SOFR, keeping its credit margin."""
        sofr = self.sofr
        if sofr is None:
            return static_rate_pct
        margin = static_rate_pct - self._sources["sofr_reference_pct"]
        return max(0.0, round(sofr + margin, 2))

    def get_default_cost_inputs(self, commodity: str, route_id: str,
                                price_basis: float | None = None,
                                quantity: float | None = None) -> CostInputs:
        inputs = super().get_default_cost_inputs(commodity, route_id,
                                                 price_basis, quantity)
        return inputs.model_copy(update={
            "financing_rate_annual_pct":
                self.financing_rate(inputs.financing_rate_annual_pct)})
