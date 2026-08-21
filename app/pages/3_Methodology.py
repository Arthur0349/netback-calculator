import streamlit as st

import theme
from ui_helpers import get_provider

st.set_page_config(page_title="Methodology — Netback Calculator",
                   page_icon="📖", layout="wide")
theme.inject()
theme.ticker(get_provider())

st.title("Methodology")
st.caption("Every formula the engine uses, with its assumptions. "
           "No black box: each cost leg is a pure function with its own tests.")

st.markdown(r"""
All monetary figures are expressed **per unit** of the commodity (USD/dmt,
USD/bbl…), on the same basis as the input price. Percentage inputs are in
percent, not fractions (`0.35` means 0.35 %).

## Netback vs landed cost

Both modes share the same cost legs; only the sign flips:

$$\text{FOB netback} = P_{CIF} - F - I - C_{fin} - C_{port} - C_{comm} + Q$$

$$\text{Landed cost} = P_{FOB} + F + I + C_{fin} + C_{port} + C_{comm} + Q$$

The quality adjustment $Q$ keeps its own sign in both directions: a premium
cargo has a higher netback *and* a higher delivered value.

## Freight

$$F = \text{freight rate (USD/unit)}$$

The rate itself comes from the data layer (static reference table today, a
live source such as the Baltic Exchange later). The engine only applies it —
Worldscale conversion or vessel-size adjustments belong in the data layer,
keeping the core auditable.

## Insurance

Standard marine cargo convention (Institute Cargo Clauses): the insured value
is **110 % of the CIF value**.

$$I = (P + F) \times 1.10 \times \frac{r_{ins}}{100}$$

## Financing

Cost of the capital tied up during transit plus the buyer/supplier credit
period:

$$C_{fin} = P \times \frac{r_{annual}}{100 \times 365} \times (\text{transit days} + \text{payment terms days})$$

## Port fees

$$C_{port} = \text{load port fee} + \text{discharge port fee} \quad \text{(USD/unit)}$$

## Commission

$$C_{comm} = P \times \frac{r_{comm}}{100}$$

## Quality adjustment

The only commodity-specific logic in the engine, isolated in a **registry of
pluggable formulas**. Each commodity profile names its formula and parameters
in configuration; every formula shares the signature
`(actual, benchmark, params) -> USD/unit`.

Examples shipped:

- **Iron ore** (linear per-unit deviations, Platts/CRU index pattern):
  premium per 1 % Fe above benchmark, penalties per 1 % silica and moisture
  above benchmark.
- **Crude oil** (OSP-style escalators): premium per API degree above
  benchmark, penalty per 1 % sulfur above benchmark.
- **Spodumene** (config skeleton): linear Li₂O adjustment, reusing an
  already-registered formula — a new commodity is configuration, not code.

## Assumptions & limits

- Reference prices, freight rates and port fees are **static indicative
  figures** at realistic mid-2020s levels, chosen for internal consistency
  rather than day-accuracy. Live assessments are a planned extension behind
  the same `PriceDataProvider` interface.
- Demurrage/despatch, weather routing, bunker adjustment factors and FX are
  out of scope of this version.
""")
