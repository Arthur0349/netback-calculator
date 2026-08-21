# Netback Calculator

[![tests](https://github.com/Arthur0349/netback-calculator/actions/workflows/tests.yml/badge.svg)](https://github.com/Arthur0349/netback-calculator/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Netback and landed-cost engine for physical commodity trades**, wrapped in a
dark trading-terminal Streamlit app. From a delivered sale price (CIF/DES/DAP)
it works backward to the FOB netback at the load port — freight, insurance,
financing, port fees and quality adjustments deducted leg by leg — or forward
from a FOB price to the delivered cost for a buyer. One engine, two directions:
only the sign of the cost legs flips.

This is the calculation a physical trader runs to compare outlets, and a buyer
runs to compare origins. The waterfall on the Calculator page is the natural
picture of a netback; the Scenario comparison page is the arbitrage view.

> **Screenshots** — _coming soon: Calculator waterfall, scenario comparison,
> ticker strip._

## Config-driven by construction

The engine knows nothing about any specific commodity. Each commodity is a
**configuration profile** — unit, benchmark spec, quality-adjustment formula
name and parameters — injected into the engine at run time:

- **Iron ore fines** (Guinea → China/Europe, Capesize) and **crude oil**
  (Arabian Gulf → Asia/Europe, VLCC/Suezmax) ship fully built: routes,
  indicative freight, port fees, benchmark prices, quality escalators.
- **Spodumene concentrate** ships as a config-only skeleton: a valid profile
  reusing an already-registered adjustment formula, with no routes or defaults
  yet. Adding it took a JSON edit, not a code change — that is the
  extensibility story in one file
  ([`commodity_specs.json`](src/netback/data/reference/commodity_specs.json)).

The same boundary applies to market data: the app reads every price, freight
rate and port fee through an abstract `PriceDataProvider`. Today that is a
static reference-table implementation with realistic mid-2020s levels; a live
implementation (Platts, Baltic Exchange…) plugs in behind the same interface
without touching the engine or the UI.

## Architecture

```
src/netback/
├── core/        # pure functions, one cost leg per module, no I/O
├── models/      # pydantic schemas (CommodityProfile, CostInputs, …)
└── data/
    ├── providers/   # PriceDataProvider ABC, static impl, live stub
    └── reference/   # JSON tables: ports, routes, freight, specs
app/             # Streamlit UI: orchestration only, no business logic
tests/           # pytest, hand-computed reference cases per module
```

Strict separation of calculation / data / presentation: `core/` makes no
network calls and never imports Streamlit; the app only wires widgets to the
engine. Full design brief in [`docs/architecture.md`](docs/architecture.md).

## Quickstart

```bash
git clone https://github.com/Arthur0349/netback-calculator.git
cd netback-calculator
pip install -e .
streamlit run app/Home.py
```

Run the tests:

```bash
pip install -e ".[dev]"
pytest
```

## Tech stack

| Layer | Choice |
|---|---|
| Engine | Python 3.10+, pure functions, pydantic v2 models |
| Data | JSON reference tables behind a `PriceDataProvider` ABC |
| UI | Streamlit multipage app, Plotly (`go.Waterfall`) charts |
| Quality | pytest (35 tests, hand-computed reference cases), GitHub Actions on every push |

## Roadmap

- [x] Core cost engine + tests (freight, insurance, financing, port fees, quality adjustment)
- [x] Static data layer (iron ore, crude oil; spodumene config skeleton)
- [x] Streamlit app: calculator, scenario comparison, methodology
- [x] GitHub Actions CI (pytest on push)
- [ ] Deploy to Streamlit Community Cloud
- [ ] Live data integration (Platts / Baltic Exchange) — interface stubbed, not built

## License

MIT — see [LICENSE](LICENSE).
