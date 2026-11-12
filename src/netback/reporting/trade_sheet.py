"""One-page PDF trade sheet: the calculation a trader would attach to a deal
recap. Headline figures, assumptions, the waterfall and the sensitivities,
print-friendly (light background), drawn with fpdf2 only (no browser, no
image export), so it runs anywhere the app does.
"""

from datetime import date

from fpdf import FPDF

from netback.core.sensitivity import SensitivityRow
from netback.models.schemas import (CommodityProfile, CostInputs,
                                    NetbackResult, Route)

NAVY = (13, 20, 36)
AMBER = (196, 142, 48)
GREEN = (46, 125, 50)
RED = (198, 40, 40)
INK = (28, 34, 48)
MUTED = (110, 120, 138)
RULE = (214, 219, 228)

_MODE = {"netback": "FOB netback", "landed_cost": "Landed cost"}
_ASCII = str.maketrans({"→": "to", "−": "-", "±": "+/-", "·": "-", "₂": "2",
                        "₃": "3", "—": "-", "–": "-", "’": "'"})


def _t(text: str) -> str:
    """Core PDF fonts are Latin-1: fold the few symbols the app uses."""
    return str(text).translate(_ASCII).encode("latin-1", "replace").decode("latin-1")


def waterfall_steps(result: NetbackResult) -> list[tuple[str, float, str]]:
    """(label, value, kind) with kind in {"total", "delta"}; concentrates
    start from the payables and show the net invoice value as a subtotal."""
    legs = [(label, value, "delta") for label, value in result.breakdown[1:-1]
            if value != 0]
    end = [(result.breakdown[-1][0], result.result_price, "total")]
    if result.price_build_up:
        build = [(label, value) for label, value in result.price_build_up
                 if value or label.startswith("Payable")]
        start = ([(build[0][0], build[0][1], "total")]
                 + [(label, value, "delta") for label, value in build[1:]]
                 + [("Net invoice value", result.base_price, "total")])
    else:
        start = [("Base price", result.base_price, "total")]
    return start + legs + end


def _draw_waterfall(pdf: FPDF, steps, x: float, y: float, w: float, h: float) -> None:
    running, spans = 0.0, []
    for _label, value, kind in steps:
        if kind == "total":
            spans.append((None, value))
            running = value
        else:
            spans.append((running, running + value))
            running += value
    levels = [v for span in spans for v in span if v is not None]
    lo, hi = min(levels), max(levels)
    pad = (hi - lo) * 0.25 or hi * 0.05
    axis_lo = max(0.0, lo - pad) if lo >= 0 else lo - pad
    axis_hi = hi + pad * 0.6
    scale = h / (axis_hi - axis_lo)
    to_y = lambda v: y + h - (v - axis_lo) * scale

    slot = w / len(steps)
    bar = slot * 0.62
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    pdf.line(x, y + h, x + w, y + h)
    for i, ((label, value, kind), (start, end)) in enumerate(zip(steps, spans)):
        bx = x + i * slot + (slot - bar) / 2
        if kind == "total":
            top, bottom = to_y(end), y + h
            pdf.set_fill_color(*AMBER)
            text = f"{value:,.2f}"
        else:
            top, bottom = to_y(max(start, end)), to_y(min(start, end))
            pdf.set_fill_color(*(GREEN if value > 0 else RED))
            text = f"{value:+,.2f}"
        pdf.rect(bx, top, bar, max(bottom - top, 0.3), style="F")
        pdf.set_font("Courier", "", 6.5)
        pdf.set_text_color(*INK)
        pdf.set_xy(x + i * slot, top - 3.6)
        pdf.cell(slot, 3, text, align="C")
        pdf.set_font("Helvetica", "", 6.2)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(x + i * slot, y + h + 1)
        pdf.multi_cell(slot, 2.6, _t(label), align="C")


def _section(pdf: FPDF, title: str, y: float | None = None) -> None:
    if y is not None:
        pdf.set_y(y)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*AMBER)
    pdf.cell(0, 5, _t(title.upper()), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*RULE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)


def _pairs(pdf: FPDF, pairs: list[tuple[str, str]], x: float, y: float, w: float) -> float:
    for label, value in pairs:
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(w * 0.56, 4.3, _t(label))
        pdf.set_font("Courier", "", 7.5)
        pdf.set_text_color(*INK)
        pdf.cell(w * 0.44, 4.3, _t(value), align="R")
        y += 4.3
    return y


def build_trade_sheet(result: NetbackResult, inputs: CostInputs, route: Route,
                      profile: CommodityProfile,
                      metal_prices: dict[str, float] | None = None,
                      sensitivities: list[SensitivityRow] | None = None,
                      as_of: str = "", today: date | None = None,
                      live: bool = False) -> bytes:
    """Render the trade sheet and return the PDF bytes (always one page)."""
    unit = profile.unit
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(14, 12, 14)
    pdf.add_page()
    width = pdf.w - 28

    # header band
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 27, style="F")
    pdf.set_fill_color(*AMBER)
    pdf.rect(0, 27, pdf.w, 0.8, style="F")
    pdf.set_xy(14, 7)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, _t(f"{profile.name} - {_MODE[result.mode]}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(200, 208, 222)
    pdf.cell(0, 5, _t(f"{inputs.delivery_term} {route.discharge_port}  |  "
                      f"{route.load_port} to {route.discharge_port}  |  "
                      f"{route.vessel_type}, {route.transit_days:g} days  |  "
                      f"{inputs.quantity:,.0f} {unit}"))
    pdf.set_xy(14, 7)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(width, 5, _t(f"Trade sheet  |  {(today or date.today()):%d %b %Y}"),
             align="R")

    # headline figures
    costs = (result.freight_cost + result.insurance_cost + result.financing_cost
             + result.port_fees_total + result.commission_cost)
    headline = [
        ("Net invoice value" if result.price_build_up else "Base price",
         f"{result.base_price:,.2f}"),
        ("Voyage costs", f"{costs:,.2f}"),
        (_MODE[result.mode], f"{result.result_price:,.2f}"),
        ("Cargo value", f"{result.result_price * inputs.quantity / 1e6:,.2f}M"),
    ]
    box_w = (width - 9) / 4
    for i, (label, value) in enumerate(headline):
        bx = 14 + i * (box_w + 3)
        accent = i == 2
        pdf.set_draw_color(*(AMBER if accent else RULE))
        pdf.set_line_width(0.4 if accent else 0.2)
        pdf.rect(bx, 33, box_w, 16)
        pdf.set_xy(bx + 2.5, 35)
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(*(AMBER if accent else MUTED))
        pdf.cell(box_w - 5, 3.5, _t(label.upper()))
        pdf.set_xy(bx + 2.5, 40)
        pdf.set_font("Courier", "B", 13)
        pdf.set_text_color(*INK)
        pdf.cell(box_w - 5, 6, value)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(bx + 2.5, 40)
        pdf.cell(box_w - 5, 6, "USD" if i == 3 else f"USD/{unit}", align="R")

    # waterfall
    _section(pdf, f"Waterfall, USD/{unit}", y=54)
    _draw_waterfall(pdf, waterfall_steps(result), 14, 70, width, 52)

    # assumptions (left) and breakdown (right)
    _section(pdf, "Assumptions and breakdown", y=134)
    top = pdf.get_y()
    col = (width - 8) / 2
    freight_unit = "wmt" if profile.freight_moisture_key else unit
    left = [
        ("Delivery term", inputs.delivery_term),
        ("Quantity", f"{inputs.quantity:,.0f} {unit}"),
        ("Freight rate", f"{inputs.freight_rate_per_unit:,.2f} USD/{freight_unit}"),
        ("Insurance rate", f"{inputs.insurance_rate_pct:.2f} % of 110 % CIF"),
        ("Financing", f"{inputs.financing_rate_annual_pct:.2f} % p.a., "
                      f"{route.transit_days + inputs.payment_terms_days:g} days"),
        ("Load / discharge fee", f"{inputs.load_port_fee_per_unit:,.2f} / "
                                 f"{inputs.discharge_port_fee_per_unit:,.2f}"),
        ("Commission", f"{inputs.commission_pct:.2f} %"),
    ]
    quality_label = "Assay" if profile.concentrate_terms else "Quality"
    left += [(f"{quality_label} {key}", f"{value:g} (bench. "
              f"{profile.benchmark_spec.get(key, value):g})")
             for key, value in inputs.actual_quality.items()]
    if profile.concentrate_terms:
        terms = profile.concentrate_terms
        left += [(f"{key} price", f"{price:,.2f}")
                 for key, price in (metal_prices or {}).items()]
        left.append(("TC", f"{terms.treatment_charge:,.2f} USD/{unit}"))
    end_left = _pairs(pdf, left[:17], 14, top, col)

    lines = (result.price_build_up + result.breakdown[1:]
             if result.price_build_up else result.breakdown)
    right = [(label, f"{value:,.2f}") for label, value in lines
             if value != 0 or label in ("Base price",)]
    end_right = _pairs(pdf, right, 14 + col + 8, top, col)

    # sensitivities
    y = max(end_left, end_right) + 4
    if sensitivities and y < 250:
        _section(pdf, f"Sensitivity of the result, USD/{unit}", y=y)
        y = pdf.get_y()
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(60, 4, "DRIVER (SHOCK)")
        pdf.cell(40, 4, "DRIVER DOWN", align="R")
        pdf.cell(40, 4, "DRIVER UP", align="R")
        y += 4.5
        for row in sensitivities[:max(0, min(6, int((262 - y) // 4.3)))]:
            pdf.set_xy(14, y)
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(*MUTED)
            pdf.cell(60, 4.3, _t(f"{row.driver} ({row.shock})"))
            pdf.set_font("Courier", "", 7.5)
            pdf.set_text_color(*INK)
            pdf.cell(40, 4.3, f"{row.delta_low:+,.2f}", align="R")
            pdf.cell(40, 4.3, f"{row.delta_high:+,.2f}", align="R")
            y += 4.3

    # footer
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    pdf.line(14, 278, pdf.w - 14, 278)
    pdf.set_xy(14, 279.5)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    stamp = f" Reference data as of {as_of}." if as_of else ""
    pdf.multi_cell(width, 3, _t(
        "Indicative calculation on "
        + ("delayed public quotes, " if live else "")
        + "static reference figures and user inputs; "
        "not a quote or an assessment." + stamp + " "
        "Netback Calculator, "
        "github.com/Arthur0349/netback-calculator"))
    return bytes(pdf.output())
