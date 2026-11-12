# Netback Calculator

[![tests](https://github.com/Arthur0349/netback-calculator/actions/workflows/tests.yml/badge.svg)](https://github.com/Arthur0349/netback-calculator/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Where does a physical cargo earn the most, and what does that answer hang
on?** A netback and landed-cost engine for physical commodity trades, wrapped
in a dark trading-terminal Streamlit app.

From a delivered sale price (CFR/CIF/DAP/DPU) it works backward to the FOB
netback at the load port, deducting freight, insurance, financing, port fees
and quality adjustments leg by leg; or forward from a FOB price to the
delivered cost. Concentrates are valued from their assays: payable metals,
TC/RC, penalties.

## What it does

| | |
|---|---|
| **Calculator** | One voyage end to end: waterfall from price (or payable metals) to FOB netback, cost structure, tornado sensitivity, deal margin with breakeven freight and price, one-page PDF trade sheet |
| **Arbitrage matrix** | One cargo, every outlet, each with its own price or smelter terms, freight and port costs; ranked on FOB netback with the lead over the runner-up and the freight headroom before the ranking flips. Every cell editable |
| **Methodology** | Every formula and convention, no black box |

**Home**
![Home page](docs/screenshots/home.png)

**Calculator: copper concentrate, from payable metals to FOB netback**
![Calculator: headline cards, waterfall, cost structure](docs/screenshots/calculator.png)
![Calculator: sensitivity, deal check, valuation detail](docs/screenshots/calculator2.png)

**Arbitrage matrix**
![Arbitrage page](docs/screenshots/arbitrage.png)

**Trade sheet (PDF export)**

<img src="docs/screenshots/tradesheet.png" alt="One-page PDF trade sheet" width="520">

## Trading conventions built in

- **Incoterms decide the legs.** Insurance applies from CIF up, discharge
  handling only under DPU; load port fees are a seller cost below FOB.
- **Insurance on 110 % of CIF**, without double counting freight when the
  starting price is already delivered.
- **Wet vs dry tonnes.** Dry bulk freight is quoted per wet tonne, ore is
  priced per dry tonne: the engine converts with the cargo moisture.
- **Concentrates.** Payable content is the lower of a payable percentage and
  the assay minus a minimum deduction; RC per payable lb (base) or oz
  (precious); pro rata penalties; negative TC/RC supported (2026 benchmark:
  USD 0/dmt and 0 c/lb, spot well below zero).
- **Sensitivity and breakeven.** One driver shocked at a time; breakevens
  solved exactly (the result is linear in freight and price).

## Coverage

| Commodity | Pricing | Routes |
|---|---|---|
| Copper concentrate | Assays: payable Cu/Au/Ag, TC/RC, As penalty | Lobito → Qingdao, Lobito → Huelva, Dar es Salaam → Fangchenggang |
| Iron ore fines | 65 % Fe index, Fe/SiO2/moisture escalators, CFR | Morebaya → Qingdao, Rotterdam |
| Bauxite (Guinea) | CIF index, Al2O3/SiO2 escalators | Kamsar → Yantai, Khalifa Port |
| Crude oil | Medium-sour benchmark, API/sulfur escalators | Ras Tanura → Ningbo, Rotterdam, Sikka |
| Spodumene concentrate | Config-only skeleton | manual inputs |

The engine knows nothing about any specific commodity: each one is a
**configuration profile** (unit, benchmark spec, quality formula or
concentrate terms) in
[`commodity_specs.json`](src/netback/data/reference/commodity_specs.json).
Spodumene is the proof: a JSON edit, no code change.

**About the numbers.** Prices, freight and port fees are static, indicative
figures (as of Nov 2026), chosen for internal consistency. Destination price
differentials and non-benchmark TC/RCs are illustrative assumptions. Every
input is editable in the app; a live source plugs in behind the
`PriceDataProvider` interface without touching the engine or the UI.

## Architecture

```
src/netback/
├── core/        # pure functions, no I/O: cost legs, concentrate valuation,
│                # netback orchestrator, arbitrage ranking, sensitivity
├── models/      # pydantic schemas
├── data/
│   ├── providers/   # PriceDataProvider ABC, static impl, live stub
│   └── reference/   # JSON tables: ports, routes, freight, specs
└── reporting/   # PDF trade sheet (fpdf2)
app/             # Streamlit UI: orchestration only, no business logic
tests/           # pytest, hand-computed reference cases per module
```

Strict separation of calculation / data / presentation: `core/` makes no
network calls and never imports Streamlit. Original design brief in
[`docs/architecture.md`](docs/architecture.md).

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
| UI | Streamlit multipage app, Plotly charts, responsive down to phone width |
| Export | fpdf2, no browser or image backend needed |
| Quality | pytest (70 tests, hand-computed reference cases), GitHub Actions on every push |

## Roadmap

- [x] Core cost engine, Incoterm-aware legs, wet-to-dry freight
- [x] Concentrate valuation: payables, TC/RC, penalties
- [x] Arbitrage matrix with per-destination pricing
- [x] Sensitivity, breakeven, deal check, PDF trade sheet
- [ ] Live data (metal prices, crude, SOFR) behind the provider interface
- [ ] Quotational period and provisional/final invoicing for concentrates
- [ ] Demurrage and laytime

## License

MIT, see [LICENSE](LICENSE).
