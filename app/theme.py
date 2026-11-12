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
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 1280px;
}}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{
    border-color: {BORDER};
    background: transparent;
}}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {{
    font-size: 0.74rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {MUTED};
}}
[data-testid="stSidebar"] label p {{
    font-size: 0.8rem;
}}
[data-testid="stCaptionContainer"] p {{
    line-height: 1.5;
}}
.nb-sub {{
    font-family: {MONO};
    font-size: 0.78rem;
    color: {MUTED};
    margin: -0.5rem 0 0.9rem;
    letter-spacing: 0.01em;
}}
.nb-sub b {{
    color: {AMBER};
    font-weight: 500;
}}

/* One chart per viewport (waterfall, route map): wide or narrow variant. */
[class*="st-key-nb_wide"] {{ display: block; }}
[class*="st-key-nb_narrow"] {{ display: none; }}
@media (max-width: 700px) {{
    [class*="st-key-nb_wide"] {{ display: none; }}
    [class*="st-key-nb_narrow"] {{ display: block; }}
    .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
    table.nb-table {{ font-size: 0.72rem; }}
    table.nb-table th, table.nb-table td {{ padding: 0.3rem 0.4rem; }}
}}
.nb-table-wrap {{
    overflow-x: auto;
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
    overflow-x: auto;
    scrollbar-width: none;
    gap: 1.4rem;
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
.nb-ticker::-webkit-scrollbar {{ display: none; }}
.nb-ticker .nb-tick-tag {{
    color: {MUTED};
    font-weight: 600;
}}
.nb-ticker .nb-tick-live {{
    color: {DELTA_GREEN};
}}
.nb-ticker .nb-tick-dot {{
    display: inline-block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: {DELTA_GREEN};
    margin-right: 0.35rem;
    vertical-align: middle;
}}
.nb-ticker .nb-tick-unit {{
    color: {MUTED};
    padding-left: 0.3rem;
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
}}
table.nb-table tr.nb-hl td {{
    color: {AMBER};
    font-weight: 500;
}}
table.nb-table td.nb-pos {{ color: {DELTA_GREEN}; }}
table.nb-table td.nb-neg {{ color: {DELTA_RED}; }}

/* ---- Map legend ------------------------------------------------------ */
.nb-legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 1.3rem;
    font-size: 0.72rem;
    color: {MUTED};
    margin: -0.4rem 0 0.9rem;
}}
.nb-legend-line {{
    display: inline-block;
    width: 18px;
    height: 2px;
    margin-right: 0.45rem;
    vertical-align: middle;
}}

/* ---- Text panels (Home) -------------------------------------------- */
.nb-panels {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 0.75rem;
    margin: 0.35rem 0 0.9rem 0;
}}
a.nb-panel {{
    display: block;
    text-decoration: none !important;
    transition: border-color 0.15s ease;
}}
a.nb-panel span {{
    display: block;
}}
a.nb-panel:hover {{
    border-color: rgba(212, 162, 76, 0.6);
}}
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
    """Thin amber strip of the reference prices with their unit. Static
    source: the date of the reference set. Live source: fetch time, a green
    dot on every figure that rests on a live quote, and SOFR. Scrolls
    sideways on narrow screens."""
    live = bool(getattr(provider, "is_live", False))
    spans = []

    def item(label: str, value: str, unit: str, title: str, dot: bool) -> None:
        mark = '<span class="nb-tick-dot"></span>' if dot else ""
        spans.append(
            f'<span title="{html.escape(title)}">'
            f'<span class="nb-tick-label">{html.escape(label)}</span>'
            f'<span class="nb-tick-value">{mark}{html.escape(value)}</span>'
            f'<span class="nb-tick-unit">{html.escape(unit)}</span></span>')

    for commodity in provider.list_commodities():
        try:
            price = provider.get_benchmark_price(commodity)
        except KeyError:
            continue  # config skeleton, no reference price
        profile = provider.get_commodity_profile(commodity)
        is_live = live and provider.is_live_price(commodity)
        item(profile.name.upper(), f"{price:,.2f}", f"USD/{profile.unit}",
             f"{profile.name}: " + ("live delayed quote" if is_live
                                    else "static reference price"), is_live)
    if live and provider.sofr is not None:
        item("SOFR", f"{provider.sofr:.2f}", "%",
             "SOFR, latest New York Fed fixing", True)

    as_of = getattr(provider, "as_of", "")
    if live:
        tag = f"LIVE · {provider.fetched_at:%d %b %H:%M} UTC".upper()
        tag_class = "nb-tick-tag nb-tick-live"
    else:
        tag = "STATIC REF" + (f" · {as_of.upper()}" if as_of else "")
        if hasattr(provider, "quotes"):       # live requested, no source answered
            tag += " · LIVE SOURCES UNAVAILABLE"
        tag_class = "nb-tick-tag"
    st.markdown(
        f'<div class="nb-ticker"><span class="{tag_class}">{html.escape(tag)}</span>'
        f'{"".join(spans)}</div>',
        unsafe_allow_html=True,
    )


def subtitle(text_html: str) -> None:
    """Monospace context line under a page title (trusted HTML)."""
    st.markdown(f'<div class="nb-sub">{text_html}</div>', unsafe_allow_html=True)


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
               numeric_from: int = 1, highlight: int | None = -1,
               signed_cols: tuple[int, ...] = ()) -> None:
    """Hairline data table: text columns left, numeric columns (index
    ``numeric_from`` onward) right-aligned in monospace. ``highlight`` is the
    row index that picks up the amber accent (default: the last row, the
    result line; ``None`` for no accent). Cells in ``signed_cols`` are
    coloured green/red by their leading sign."""
    def cell(tag: str, i: int, value: str) -> str:
        classes = ["nb-num"] if i >= numeric_from else []
        if tag == "td" and i in signed_cols:
            if value.startswith("+") and value.strip("+0.,") != "":
                classes.append("nb-pos")
            elif value.startswith(("-", "−")):
                classes.append("nb-neg")
        cls = f' class="{" ".join(classes)}"' if classes else ""
        return f"<{tag}{cls}>{html.escape(value)}</{tag}>"

    hl = highlight % len(rows) if rows and highlight is not None else None
    head = "".join(cell("th", i, h) for i, h in enumerate(headers))
    body = "".join(
        f'<tr{" class=nb-hl" if r == hl else ""}>'
        + "".join(cell("td", i, v) for i, v in enumerate(row)) + "</tr>"
        for r, row in enumerate(rows)
    )
    st.markdown(f'<div class="nb-table-wrap"><table class="nb-table"><thead>'
                f"<tr>{head}</tr></thead><tbody>{body}</tbody></table></div>",
                unsafe_allow_html=True)


def panel(title: str, body_html: str, href: str | None = None) -> str:
    """A bordered text panel (Home page). ``body_html`` is trusted HTML
    written by us, not user input. With ``href`` the whole panel links."""
    if href:
        return (f'<a class="nb-panel" href="{html.escape(href)}" target="_self">'
                f'<span class="nb-panel-title">{html.escape(title)}</span>'
                f'<span class="nb-panel-body">{body_html}</span></a>')
    return (f'<div class="nb-panel">'
            f'<div class="nb-panel-title">{html.escape(title)}</div>'
            f'<div class="nb-panel-body">{body_html}</div></div>')
