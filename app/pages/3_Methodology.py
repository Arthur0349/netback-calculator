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

Both modes share the same cost legs; the **mode** decides their sign and the
**delivery term** (Incoterms 2020) decides which legs apply:

$$\text{FOB netback} = P_{del} - F - I - C_{fin} - C_{port} - C_{comm} + Q$$

$$\text{Landed cost} = P_{FOB} + F + I + C_{fin} + C_{port} + C_{comm} + Q$$

| Delivery term | Freight | Insurance | Discharge port fees |
|---|---|---|---|
| CFR | ✓ | buyer | buyer |
| CIF | ✓ | ✓ | buyer |
| DAP | ✓ | ✓ (seller carries transit risk) | buyer |
| DPU | ✓ | ✓ | ✓ |

**Load port fees** are a seller cost below FOB: they are deducted in netback
mode (the netback is the seller's realisation net of loading) and never added
in landed-cost mode (a FOB price already includes loading).

The quality adjustment $Q$ keeps its own sign in both directions: a premium
cargo has a higher netback *and* a higher delivered value.

## Freight

$$F = \text{freight rate (USD/unit)}$$

The rate itself comes from the data layer (static reference table today, a
live source such as the Baltic Exchange later). The engine only applies it:
Worldscale conversion or vessel-size adjustments belong in the data layer,
keeping the core auditable.

**Wet vs dry tonnes.** Dry bulk freight is fixed per *wet* tonne shipped
while ores are priced per *dry* tonne. For commodities flagged this way
(iron ore, bauxite) the engine converts with the cargo moisture $m$:

$$F_{dmt} = \frac{F_{wmt}}{1 - m/100}$$

## Insurance

Standard marine cargo convention (Institute Cargo Clauses): the insured value
is **110 % of the CIF value**.

$$I = V_{CIF} \times 1.10 \times \frac{r_{ins}}{100}$$

In landed-cost mode the CIF value is built up, $V_{CIF} = P_{FOB} + F$. In
netback mode the delivered price already *is* the CIF value
($V_{CIF} = P_{del}$, net of unloading under DPU): freight is not added a
second time.

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
- **Bauxite** (Guinea, linear): premium per 1 % Al₂O₃ both ways, penalty
  per 1 % reactive silica above benchmark.
- **Crude oil** (OSP-style escalators): premium per API degree above
  benchmark, penalty per 1 % sulfur above benchmark.
- **Spodumene** (config skeleton): linear Li₂O adjustment, reusing an
  already-registered formula — a new commodity is configuration, not code.

## Concentrates: payables, TC/RC, penalties

Concentrates have no flat index price. The delivered value of one dry tonne
is built from its assays under the smelter terms, then walked back to FOB
like any other price:

$$P_{CIF} = \sum_m \text{payable}_m \times \text{price}_m - TC - \sum_m RC_m \times \text{payable}_m - \sum_e \text{penalty}_e$$

- **Payable content**: the *lower* of a payable percentage of the assay and
  the assay minus a minimum deduction (copper: 96.5 %, min. 1 unit; gold:
  90 % after 1 g/dmt; silver: 90 % after 30 g/dmt).
- **Units**: base metals in % and USD/t, precious metals in g/dmt and USD/oz
  troy (31.1035 g). Copper RC in USD per payable lb (2,204.62 lb/t),
  precious RC in USD per payable oz.
- **TC/RC can be negative.** The 2026 annual copper benchmark settled at
  USD 0/dmt and 0 c/lb; spot traded around −USD 120/dmt by mid-2026, i.e.
  smelters paying miners for feed.
- **Penalties**: USD per step of a deleterious element above its free level
  (arsenic: USD 3 per 0.1 % above 0.2 %), pro rata.

The assays are fully priced in the valuation, so concentrates carry no
separate quality adjustment.

## Assumptions & limits

- Reference prices, freight rates and port fees are **static indicative
  figures** at realistic mid-2020s levels, chosen for internal consistency
  rather than day-accuracy. Live assessments are a planned extension behind
  the same `PriceDataProvider` interface.
- Concentrates: the quotational period (QP), provisional/final invoicing
  and price participation are not modelled; prices are the QP average.
- Demurrage/despatch, weather routing, bunker adjustment factors and FX are
  out of scope of this version.
- Insurance uses the market shortcut on the CIF value; the exact landed
  CIF, $(P_{FOB}+F)/(1-1.1\,r_{ins})$, differs by a few cents per tonne.
""")
