import streamlit as st

import theme
from ui_helpers import setup_page

st.set_page_config(page_title="Methodology · Netback Calculator",
                   page_icon="🚢", layout="wide")
theme.inject()
setup_page("methodology")

st.title("Methodology")
theme.subtitle("Every formula the engine uses, with its assumptions. "
               "Each cost leg is a pure function with its own tests.")

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

The netback engine only applies the rate. Where the rate comes from is the
voyage estimate below; the reference table holds one indicative rate per
route.

**Wet vs dry tonnes.** Dry bulk freight is fixed per *wet* tonne shipped
while ores are priced per *dry* tonne. For commodities flagged this way
(iron ore, bauxite) the engine converts with the cargo moisture $m$:

$$F_{dmt} = \frac{F_{wmt}}{1 - m/100}$$

## Voyage estimate: where a freight rate comes from

A freight rate is the price at which a voyage covers the ship (Freight
page). With hire $H$ in USD/day, cargo intake $Q$ and address plus brokerage
commission $c$:

$$\text{days} = \frac{d_{laden}}{24\,v_{laden}}(1+s) + \frac{d_{ballast}}{24\,v_{ballast}}(1+s) + \text{port days} + \text{canal days}$$

$$\text{voyage costs} = \text{bunkers} \times P_{bunker} + \text{port costs} + \text{canal dues}$$

$$F = \frac{H \times \text{days} + \text{voyage costs}}{(1 - c)\,Q}$$

Read the other way, the **time-charter equivalent** of a quoted rate is what
the voyage pays the ship per day once the voyage costs are out:

$$TCE = \frac{F \times Q \times (1 - c) - \text{voyage costs}}{\text{days}}$$

- $s$ is the sea margin (weather, currents). Bunkers are sea days times sea
  consumption plus port and canal days times port consumption.
- The **ballast leg** is the empty distance charged to the voyage, as a
  share of the laden distance: 100 % is a round voyage back to the load
  port.
- **Bunker exposure.** At constant hire the rate moves by
  $\text{bunkers} / ((1-c)\,Q)$ per USD 1/t on the bunker price. On a voyage
  charter that risk is the owner's; it reaches the charterer through the
  next fixture.
- **Speed** follows the cube law: daily consumption scales with the cube of
  the speed. Slowing down saves fuel but keeps the ship longer, so slow
  steaming pays when bunkers are dear relative to hire.
- Transit days in the reference routes use the same convention (laden
  service speed of the vessel class, 5 % sea margin, one day per canal), so
  the Calculator's financing leg and the voyage estimate agree.

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

## Arbitrage matrix

The same cargo is netted back from every outlet, each with its own
destination pricing (a delivered price differential for index-priced
commodities, the destination smelter's TC/RCs for concentrates), its own
freight and port costs, and ranked on FOB netback.

- **Spread vs best**: netback gap to the best outlet, per unit and over the
  whole cargo.
- **Cushion**: how far the best outlet's netback can fall (freight up, price
  down, TC worse) before the runner-up wins:
  $\text{cushion} = NB_{1} - NB_{2}$. For a freight move on a wet-quoted
  route, the break-even freight rise is $\text{cushion} \times (1 - m/100)$
  USD/wmt.

## Sensitivity and breakeven

**Tornado.** Each driver is shocked one at a time, down and up, everything
else held: ±10 % on prices, freight, financing rate, transit time and port
fees; ±1 point on the main grade and on moisture; ±USD 50/dmt on the TC.
Bars are the change in the result, sorted by swing.

**Deal check.** With a FOB purchase cost $C$ (netback mode):

$$\text{margin} = NB - C \qquad \text{return on capital} = \frac{NB - C}{C} \times \frac{365}{\text{transit} + \text{payment days}}$$

**Breakevens.** The result is linear in freight and in price, so the
breakeven is solved exactly from two evaluations: the freight (or sale
price, or metal price) at which the margin is zero.

## Market data: live and static

With **Live market data** on, the figures that have a free public quote are
fetched (delayed, refreshed every 15 minutes) and replace the static ones:

| Figure | Live source | Conversion |
|---|---|---|
| Copper | COMEX front-month future | USD/lb × 2,204.62 = USD/t |
| Gold, silver | COMEX front-month futures | USD/oz |
| Crude benchmark | ICE Brent front month | proxy for the medium-sour delivered benchmark |
| Iron ore 65 % Fe | SGX 62 % Fe CFR China front month | + USD 13 indicative grade premium |
| Financing rate | SOFR, New York Fed | SOFR + the credit margin of the static rate |

A quote that fails, is more than ten days old or falls outside plausibility
bounds is dropped and the static figure is used in its place; the ticker
marks each live figure with a green dot. Freight, port fees, smelter terms,
bauxite and destination differentials have no free public quote and are
static in both modes. COMEX copper can trade away from the LME price that
concentrate contracts reference: overwrite the price to use your own.

## Shareable links

The Calculator's address bar always carries the case on screen as readable
query parameters (commodity, route, direction, every cost input, assays,
metal prices, smelter terms). Opening the link restores the same case
whatever the data source, since every input is in the link.

## Assumptions & limits

- Static reference prices, freight rates and port fees are **indicative
  figures** chosen for internal consistency rather than day-accuracy.
- Vessel figures in the voyage estimate are indicative for the class
  (modern eco tonnage, one fuel grade, no ECA fuel split).
- Destination differentials and non-benchmark TC/RCs in the reference
  data are illustrative, not assessments; they are editable in the app.
- Concentrates: the quotational period (QP), provisional/final invoicing
  and price participation are not modelled; prices are the QP average.
- Demurrage/despatch, weather routing and FX are out of scope of this
  version.
- Insurance uses the market shortcut on the CIF value; the exact landed
  CIF, $(P_{FOB}+F)/(1-1.1\,r_{ins})$, differs by a few cents per tonne.
""")
