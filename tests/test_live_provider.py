"""Live provider: quotes override the static figures, failures fall back.

No test touches the network: the fetchers are injected.
"""

from datetime import datetime, timedelta, timezone

import pytest

from netback.data.providers import (LiveDataProvider, PriceDataProvider,
                                    StaticDataProvider)
from netback.data.providers.quotes import parse_nyfed_sofr, parse_yahoo_chart

NOW = datetime(2026, 11, 12, 4, 0, tzinfo=timezone.utc)
QUOTES = {"HG=F": 6.40, "GC=F": 4200.0, "SI=F": 54.0, "BZ=F": 74.5, "TIO=F": 97.0}


def make(quotes=QUOTES, sofr=3.88, age=timedelta(minutes=20)):
    def fetch_quote(symbol):
        if symbol not in quotes:
            raise OSError("HTTP 429")
        return quotes[symbol], NOW - age

    def fetch_rate():
        if sofr is None:
            raise OSError("timeout")
        return sofr, NOW - timedelta(days=1)

    return LiveDataProvider(fetch_quote, fetch_rate, now=lambda: NOW).refresh()


def test_live_quotes_override_static():
    live, static = make(), StaticDataProvider()
    assert isinstance(live, PriceDataProvider) and live.is_live
    prices = live.get_metal_prices("copper_concentrate")
    assert prices["Cu"] == pytest.approx(6.40 * 2204.62262, abs=0.01)   # $/lb -> $/t
    assert (prices["Au"], prices["Ag"]) == (4200.0, 54.0)
    assert live.get_benchmark_price("crude_oil") == 74.5
    assert live.get_benchmark_price("iron_ore") == 97.0 + 13.0          # 62 % -> 65 % Fe
    # no public quote: static
    assert live.get_benchmark_price("bauxite") == static.get_benchmark_price("bauxite")
    assert live.is_live_price("copper_concentrate") and live.is_live_price("crude_oil")
    assert not live.is_live_price("bauxite")


def test_live_prices_flow_into_default_inputs():
    live, static = make(), StaticDataProvider()
    crude = live.get_default_cost_inputs("crude_oil", "ras_tanura_rotterdam")
    assert crude.price_basis == pytest.approx(74.5 - 1.2)       # + destination differential
    conc = live.get_default_cost_inputs("copper_concentrate", "lobito_qingdao")
    ref = static.get_default_cost_inputs("copper_concentrate", "lobito_qingdao")
    assert conc.price_basis > ref.price_basis                   # Cu 14,110 vs 13,800
    assert conc.freight_rate_per_unit == ref.freight_rate_per_unit


def test_financing_is_sofr_plus_the_static_margin():
    live = make(sofr=4.40)
    # static 6.5 % was set against SOFR 3.9 %: margin 2.6 pts
    assert live.get_default_cost_inputs(
        "iron_ore", "morebaya_qingdao").financing_rate_annual_pct == pytest.approx(7.0)
    assert live.get_default_cost_inputs(
        "crude_oil", "ras_tanura_ningbo").financing_rate_annual_pct == pytest.approx(6.5)


def test_each_source_falls_back_on_its_own():
    live, static = make(quotes={"GC=F": 4200.0}, sofr=None), StaticDataProvider()
    assert live.is_live                                         # gold answered
    prices = live.get_metal_prices("copper_concentrate")
    assert prices["Au"] == 4200.0
    assert prices["Cu"] == static.get_metal_prices("copper_concentrate")["Cu"]
    assert live.get_benchmark_price("crude_oil") == 78.0
    assert live.sofr is None
    assert live.get_default_cost_inputs(
        "iron_ore", "morebaya_qingdao").financing_rate_annual_pct == 6.5
    assert "HTTP 429" in live.quotes["Cu"].error


def test_everything_down_is_the_static_provider():
    live, static = make(quotes={}, sofr=None), StaticDataProvider()
    assert not live.is_live
    assert live.data_note.startswith("Live sources did not answer")
    for commodity in ("iron_ore", "crude_oil", "bauxite", "copper_concentrate"):
        assert (live.get_benchmark_price(commodity)
                == static.get_benchmark_price(commodity))
        for rid in live.list_routes(commodity):
            assert (live.get_default_cost_inputs(commodity, rid)
                    == static.get_default_cost_inputs(commodity, rid))


def test_implausible_and_stale_quotes_are_rejected():
    # copper at 0.064 $/lb (a unit slip) and a week-old... 30-day-old Brent
    live = make(quotes={**QUOTES, "HG=F": 0.064})
    assert live.get_metal_prices("copper_concentrate")["Cu"] == 13800.0
    assert "implausible" in live.quotes["Cu"].error
    stale = make(age=timedelta(days=30))
    assert not stale.is_live_price("crude_oil")
    assert "stale" in stale.quotes["crude_oil"].error
    assert stale.sofr == 3.88                                   # own timestamp


def test_data_note_says_what_is_live():
    note = make().data_note
    assert "metal prices" in note and "SOFR" in note and "12 Nov 2026 04:00" in note
    assert "Freight" in note and "static" in note


def test_unknown_keys_still_raise():
    with pytest.raises(KeyError, match="Unknown commodity"):
        make().get_benchmark_price("unobtainium")
    with pytest.raises(KeyError, match="skeleton"):
        make().get_benchmark_price("lithium_spodumene")


def test_payload_parsers():
    value, when = parse_yahoo_chart({"chart": {"result": [{"meta": {
        "regularMarketPrice": 6.4125, "regularMarketTime": 1794456000}}]}})
    assert value == 6.4125 and when.tzinfo is timezone.utc
    value, when = parse_nyfed_sofr({"refRates": [{
        "effectiveDate": "2026-11-09", "type": "SOFR", "percentRate": 3.88}]})
    assert value == 3.88 and (when.year, when.month, when.day) == (2026, 11, 9)
    with pytest.raises((KeyError, IndexError, TypeError)):
        parse_yahoo_chart({"chart": {"result": None, "error": "Not Found"}})
