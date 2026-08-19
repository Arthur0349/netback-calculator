# Netback Calculator

> Freight rate netback / landed cost calculator for bulk and tanker commodity trades — iron ore (Guinea) and crude oil (Gulf) as fully-built reference profiles, with a config-driven engine so new commodities and routes are a data edit, not a rewrite.

![screenshot placeholder](docs/screenshot.png)

## What this does

Computes **netback** (CIF → FOB, backward) or **landed cost** (FOB → CIF, forward) for a given commodity, route, and quantity, breaking the result down by freight, insurance, financing cost, port fees, and quality adjustment. Built as a portfolio piece demonstrating the trade-flow economics used in physical commodity origination and structuring.

**Live app:** _coming soon (Streamlit Community Cloud)_

## Quickstart

```bash
git clone https://github.com/<your-username>/netback-calculator.git
cd netback-calculator
pip install -e .
streamlit run app/Home.py
```

## Architecture

Three layers — data, calculation engine, app — connected through interfaces rather than hardcoded values, so nothing about a specific commodity or country lives in the core logic. Full design doc: [`docs/architecture.md`](docs/architecture.md).

## Roadmap

- [x] Architecture & repo scaffolding
- [ ] Core cost modules + tests (freight, insurance, financing, port fees, quality adjustment)
- [ ] Data layer (iron ore/Guinea, crude/Gulf reference tables, lithium config skeleton)
- [ ] Streamlit app (calculator, scenario comparison, methodology page)
- [ ] Deploy to Streamlit Community Cloud + GitHub Actions CI (pytest on push)
- [ ] Live data integration (Platts / Baltic Exchange) — interface stubbed, not built

## License

MIT — see [LICENSE](LICENSE).
