"""Trading-terminal visual identity, shared by every page.

Colour tokens, the injected CSS, the reference-price ticker strip and the
custom metric cards all live here so the pages stay pure orchestration.
The base palette (backgrounds, borders, text) is set in
``.streamlit/config.toml``; this module adds what the config cannot:
fonts, the ticker, cards, and chart styling tokens.
"""

import html

import streamlit as st

BG = "#0A0E17"
SURFACE = "#121826"
BORDER = "#232B3D"
TEXT = "#E8ECF1"
MUTED = "#7C879C"
AMBER = "#D4A24C"

# Chart semantics (unchanged from the light theme): green = increase/premium,
# red = decrease/penalty. Totals carry the terminal's amber accent.
CHART_GREEN = "#2E7D32"
CHART_RED = "#C62828"
CHART_TOTAL = AMBER
DELTA_GREEN = "#4CC38A"
DELTA_RED = "#E5484D"

SANS = "IBM Plex Sans, sans-serif"
MONO = "IBM Plex Mono, monospace"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

header[data-testid="stHeader"] {{
    background: transparent;
}}
.block-container {{
    padding-top: 2.6rem;
}}

h1 {{
    font-family: {SANS};
    font-size: 1.45rem !important;
    font-weight: 600;
    letter-spacing: 0.01em;
}}
h2, h3 {{
    font-family: {SANS};
    font-size: 0.82rem !important;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: {MUTED};
}}
hr {{
    margin: 0.9rem 0;
    border: none;
    border-top: 1px solid {BORDER};
}}

/* Every numeric input reads as a terminal field. */
[data-testid="stNumberInput"] input {{
    font-family: {MONO};
    font-size: 0.85rem;
}}

/* ---- Ticker strip -------------------------------------------------- */
.nb-ticker {{
    display: flex;
    flex-wrap: nowrap;
    overflow: hidden;
    gap: 1rem;
    align-items: baseline;
    background: #0D1424;
    border: 1px solid {BORDER};
    border-top: 1px solid {AMBER};
    border-radius: 0 0 4px 4px;
    padding: 0.32rem 0.9rem;
    margin-bottom: 1.1rem;
    font-family: {MONO};
    font-size: 0.7rem;
    letter-spacing: 0.03em;
    white-space: nowrap;
}}
.nb-ticker .nb-tick-tag {{
    color: {MUTED};
    font-weight: 600;
}}
.nb-ticker .nb-tick-label {{
    color: {MUTED};
}}
.nb-ticker .nb-tick-value {{
    color: {AMBER};
    font-weight: 500;
    padding-left: 0.45rem;
}}

/* ---- Metric cards -------------------------------------------------- */
.nb-cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin: 0.35rem 0 0.9rem 0;
}}
.nb-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 0.8rem 0.95rem 0.7rem;
    min-width: 0;
}}
.nb-card--accent {{
    border-color: rgba(212, 162, 76, 0.55);
}}
.nb-card--accent .nb-card-label {{
    color: {AMBER};
}}
.nb-card-label {{
    font-family: {SANS};
    font-size: 0.66rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: {MUTED};
    margin-bottom: 0.35rem;
}}
.nb-card-value {{
    font-family: {MONO};
    font-variant-numeric: tabular-nums;
    font-size: 1.32rem;
    font-weight: 500;
    line-height: 1.25;
    color: {TEXT};
    overflow-wrap: anywhere;
}}
.nb-card-unit {{
    font-size: 0.78rem;
    color: {MUTED};
    padding-left: 0.15rem;
}}
.nb-card-delta {{
    font-family: {MONO};
    font-variant-numeric: tabular-nums;
    font-size: 0.7rem;
    color: {MUTED};
    margin-top: 0.3rem;
}}
.nb-card-delta.nb-pos {{ color: {DELTA_GREEN}; }}
.nb-card-delta.nb-neg {{ color: {DELTA_RED}; }}

/* ---- Data table ----------------------------------------------------- */
table.nb-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
    margin: 0.2rem 0 0.4rem;
}}
table.nb-table th {{
    font-family: {SANS};
    font-size: 0.66rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {MUTED};
    text-align: left;
    padding: 0.35rem 0.75rem;
    border-bottom: 1px solid {BORDER};
}}
table.nb-table td {{
    padding: 0.32rem 0.75rem;
    border-bottom: 1px solid rgba(35, 43, 61, 0.55);
    color: {TEXT};
}}
table.nb-table th.nb-num, table.nb-table td.nb-num {{
    text-align: right;
    font-family: {MONO};
    font-variant-numeric: tabular-nums;
}}
table.nb-table tr:last-child td {{
    border-bottom: none;
    color: {AMBER};
    font-weight: 500;
}}

/* ---- Text panels (Home) -------------------------------------------- */
.nb-panel {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 0.9rem 1.1rem;
    height: 100%;
}}
.nb-panel-title {{
    font-family: {SANS};
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: {AMBER};
    margin-bottom: 0.45rem;
}}
.nb-panel-body {{
    font-size: 0.86rem;
    line-height: 1.55;
    color: {TEXT};
}}
.nb-panel-body .nb-mono {{
    font-family: {MONO};
    font-size: 0.78rem;
    color: {MUTED};
}}
</style>
"""


def inject() -> None:
    """Load fonts and the terminal stylesheet. Call once per page, right
    after ``st.set_page_config``."""
    st.markdown(_CSS, unsafe_allow_html=True)


def ticker(provider) -> None:
    """Thin amber strip of static reference prices: every benchmark price
    the provider knows, then indicative freight per route."""
    items: list[tuple[str, str, str]] = []
    for commodity in provider.list_commodities():
        try:
            price = provider.get_benchmark_price(commodity)
        except KeyError:
            continue  # config skeleton, no reference price
        profile = provider.get_commodity_profile(commodity)
        short_name = " ".join(profile.name.split()[:2]).upper()
        items.append((short_name, f"{price:,.2f}/{profile.unit}",
                      f"{profile.name} benchmark, USD/{profile.unit}"))
        for route_id in provider.list_routes(commodity):
            route = provider.get_route(route_id)
            leg = (f"{route.load_port[:3]}→"
                   f"{route.discharge_port[:3]}").upper()
            rate = provider.get_freight_rate(route)
            items.append((leg, f"{rate:,.2f}",
                          f"Indicative freight {route.load_port} → "
                          f"{route.discharge_port} ({route.vessel_type}), "
                          f"USD/{profile.unit}"))

    spans = "".join(
        f'<span title="{html.escape(tooltip)}">'
        f'<span class="nb-tick-label">{html.escape(label)}</span>'
        f'<span class="nb-tick-value">{html.escape(value)}</span></span>'
        for label, value, tooltip in items
    )
    st.markdown(
        f'<div class="nb-ticker"><span class="nb-tick-tag">STATIC REF</span>'
        f"{spans}</div>",
        unsafe_allow_html=True,
    )


def metric_cards(cards: list[dict]) -> None:
    """Render metric cards on card surfaces with monospace values.

    Each card: ``label``, ``value`` (pre-formatted), optional ``unit``,
    ``delta`` text, ``delta_kind`` ("pos" | "neg" | anything else = muted)
    and ``accent`` (bool) for the headline card. Values wrap instead of
    truncating, so figures always display in full.
    """
    blocks = []
    for card in cards:
        unit = card.get("unit")
        unit_html = (f'<span class="nb-card-unit">/{html.escape(unit)}</span>'
                     if unit else "")
        delta_html = ""
        if card.get("delta"):
            kind = {"pos": " nb-pos", "neg": " nb-neg"}.get(
                card.get("delta_kind", ""), "")
            delta_html = (f'<div class="nb-card-delta{kind}">'
                          f'{html.escape(card["delta"])}</div>')
        accent = " nb-card--accent" if card.get("accent") else ""
        blocks.append(
            f'<div class="nb-card{accent}">'
            f'<div class="nb-card-label">{html.escape(card["label"])}</div>'
            f'<div class="nb-card-value">{html.escape(card["value"])}'
            f"{unit_html}</div>{delta_html}</div>"
        )
    st.markdown(f'<div class="nb-cards">{"".join(blocks)}</div>',
                unsafe_allow_html=True)


def data_table(headers: list[str], rows: list[list[str]],
               numeric_from: int = 1) -> None:
    """Hairline data table: text columns left, numeric columns (index
    ``numeric_from`` onward) right-aligned in monospace. The last row is
    treated as the result line and picks up the amber accent."""
    def cell(tag: str, i: int, value: str) -> str:
        cls = ' class="nb-num"' if i >= numeric_from else ""
        return f"<{tag}{cls}>{html.escape(value)}</{tag}>"

    head = "".join(cell("th", i, h) for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(cell("td", i, v) for i, v in enumerate(row)) + "</tr>"
        for row in rows
    )
    st.markdown(f'<table class="nb-table"><thead><tr>{head}</tr></thead>'
                f"<tbody>{body}</tbody></table>", unsafe_allow_html=True)


def panel(title: str, body_html: str) -> str:
    """A bordered text panel (Home page). ``body_html`` is trusted HTML
    written by us, not user input."""
    return (f'<div class="nb-panel">'
            f'<div class="nb-panel-title">{html.escape(title)}</div>'
            f'<div class="nb-panel-body">{body_html}</div></div>')
