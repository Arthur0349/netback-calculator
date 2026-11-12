"""Public market quotes over plain HTTPS, standard library only.

Two sources, neither needs an API key:

- Yahoo Finance chart endpoint: last price of a futures contract (delayed).
- New York Fed markets API: the latest published SOFR fixing.

Each function returns ``(value, timestamp)`` or raises; the live provider
treats any exception as "no quote" and falls back to the static figure.
"""

import json
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "application/json",
}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d"
NYFED_SOFR = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json"


def _get_json(url: str, timeout: float) -> dict:
    with urlopen(Request(url, headers=_HEADERS), timeout=timeout) as response:
        return json.load(response)


def parse_yahoo_chart(payload: dict) -> tuple[float, datetime]:
    meta = payload["chart"]["result"][0]["meta"]
    return (float(meta["regularMarketPrice"]),
            datetime.fromtimestamp(int(meta["regularMarketTime"]), tz=timezone.utc))


def parse_nyfed_sofr(payload: dict) -> tuple[float, datetime]:
    rate = payload["refRates"][0]
    day = datetime.strptime(rate["effectiveDate"], "%Y-%m-%d")
    return float(rate["percentRate"]), day.replace(tzinfo=timezone.utc)


def fetch_yahoo_quote(symbol: str, timeout: float = 4.0) -> tuple[float, datetime]:
    """Last traded price of ``symbol`` in the contract's own unit."""
    return parse_yahoo_chart(
        _get_json(YAHOO_CHART.format(symbol=quote(symbol, safe="")), timeout))


def fetch_sofr(timeout: float = 4.0) -> tuple[float, datetime]:
    """Latest SOFR fixing, in percent, with its effective date."""
    return parse_nyfed_sofr(_get_json(NYFED_SOFR, timeout))
