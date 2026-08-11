"""PDF report generator \u2014 replicates the May 2026 report design.

Uses ReportLab to draw the same landscape layout as the PPTX version:
navy header bars with a green accent, KPI cards, embedded charts, and
tables. Page size matches the 16:9 slide proportions of the original PDF.

No external binaries required, so it works on Streamlit Cloud.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas


# ======================================================================
# Page geometry \u2014 13.333" x 7.5" (16:9), same as the PPTX slides
# ======================================================================
PAGE_W = 13.333 * 72   # 960 pt
PAGE_H = 7.5 * 72      # 540 pt
PAGE_SIZE = (PAGE_W, PAGE_H)


def _in(inches: float) -> float:
    """Inches \u2192 points."""
    return inches * 72


def _y(top_inches: float) -> float:
    """Convert a top-down inch coordinate to ReportLab's bottom-up points."""
    return PAGE_H - _in(top_inches)


# ======================================================================
# Colors \u2014 identical to the PPTX/chart palette
# ======================================================================
DARK_NAVY = HexColor("#1B3A5C")
MEDIUM_BLUE = HexColor("#5B9BD5")
GREEN = HexColor("#4CAF50")
RED = HexColor("#E74C3C")
LIGHT_GRAY = HexColor("#F5F6F8")
WHITE = HexColor("#FFFFFF")
TEXT_DARK = HexColor("#2C3E50")
TEXT_GRAY = HexColor("#7F8C8D")
BORDER_GRAY = HexColor("#E0E0E0")
SUBTITLE_GRAY = HexColor("#B0BEC5")

# Helvetica is a ReportLab built-in and metrically close to Calibri
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"


# ======================================================================
# Drawing primitives
# ======================================================================

def _rect(c, x_in, y_top_in, w_in, h_in, fill=None, stroke=None, line_w=0.5):
    """Draw a rectangle using top-down inch coordinates."""
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(line_w)
    c.rect(_in(x_in), _y(y_top_in + h_in), _in(w_in), _in(h_in),
           fill=1 if fill else 0, stroke=1 if stroke else 0)


def _text(c, x_in, y_top_in, text, size=10, bold=False, italic=False,
          color=TEXT_DARK, align="left", width_in=None):
    """Draw a single line of text at a top-down inch coordinate."""
    if not text:
        return
    font = FONT_BOLD if bold else (FONT_ITALIC if italic else FONT)
    c.setFont(font, size)
    c.setFillColor(color)
    x = _in(x_in)
    y = _y(y_top_in) - size * 0.85

    if align == "center" and width_in:
        c.drawCentredString(x + _in(width_in) / 2, y, str(text))
    elif align == "right" and width_in:
        c.drawRightString(x + _in(width_in), y, str(text))
    else:
        c.drawString(x, y, str(text))


def _text_in_box(c, x_in, y_top_in, w_in, h_in, text, size=10, bold=False,
                 italic=False, color=TEXT_DARK, align="center", pad_in=0.09):
    """Draw a line of text vertically centred inside a box.

    Cap height for Helvetica is ~0.7 * size, so the baseline sits
    0.35 * size below the vertical centre of the box.
    """
    if text is None or text == "":
        return
    font = FONT_BOLD if bold else (FONT_ITALIC if italic else FONT)
    c.setFont(font, size)
    c.setFillColor(color)
    baseline = _y(y_top_in + h_in / 2) - 0.35 * size

    if align == "center":
        c.drawCentredString(_in(x_in) + _in(w_in) / 2, baseline, str(text))
    elif align == "right":
        c.drawRightString(_in(x_in + w_in - pad_in), baseline, str(text))
    else:
        c.drawString(_in(x_in + pad_in), baseline, str(text))


def _arrow(c, x_center_in, y_center_in, up: bool, color, size=7):
    """Draw a small filled triangle (Helvetica has no arrow glyphs)."""
    half = size / 2.0
    cx = _in(x_center_in)
    cy = _y(y_center_in)
    c.setFillColor(color)
    path = c.beginPath()
    if up:
        path.moveTo(cx, cy + half)
        path.lineTo(cx - half, cy - half)
        path.lineTo(cx + half, cy - half)
    else:
        path.moveTo(cx, cy - half)
        path.lineTo(cx - half, cy + half)
        path.lineTo(cx + half, cy + half)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def _variation(c, x_in, y_top_in, w_in, h_in, variation, size=9):
    """Draw an arrow + percentage, centred inside a box."""
    if not variation or str(variation).strip() in ("", "-"):
        return
    txt = str(variation).replace("\u25b2", "").replace("\u25bc", "").strip()
    up = "\u25b2" in str(variation)
    color = GREEN if up else RED
    c.setFont(FONT_BOLD, size)
    text_w = c.stringWidth(txt, FONT_BOLD, size)
    gap = 4.0
    total_w = text_w + size * 0.7 + gap
    left = _in(x_in) + (_in(w_in) - total_w) / 2
    y_center = y_top_in + h_in / 2

    _arrow(c, (left + size * 0.35) / 72, y_center, up, color, size=size * 0.8)
    c.setFillColor(color)
    c.drawString(left + size * 0.7 + gap, _y(y_center) - 0.35 * size, txt)


def _image(c, img_source, x_in, y_top_in, w_in, h_in):
    """Draw an image, preserving aspect ratio inside the given box."""
    if not img_source:
        return
    try:
        if isinstance(img_source, (str, Path)):
            p = Path(img_source)
            if not p.exists():
                return
            reader = ImageReader(str(p))
        else:
            reader = ImageReader(io.BytesIO(img_source))

        iw, ih = reader.getSize()
        box_w, box_h = _in(w_in), _in(h_in)
        scale = min(box_w / iw, box_h / ih)
        dw, dh = iw * scale, ih * scale
        # Center inside the box
        dx = _in(x_in) + (box_w - dw) / 2
        dy = _y(y_top_in + h_in) + (box_h - dh) / 2
        c.drawImage(reader, dx, dy, dw, dh, mask="auto")
    except Exception:
        pass


# ======================================================================
# Page furniture
# ======================================================================

def _header_bar(c, title, period):
    """Navy header bar with green accent line."""
    _rect(c, 0, 0, 13.333, 0.65, fill=DARK_NAVY)
    _rect(c, 0, 0.65, 13.333, 0.04, fill=GREEN)
    _text(c, 0.5, 0.22, title, size=18, bold=True, color=WHITE)
    _text(c, 8.0, 0.25, f"Productividad del Contact Center \u00b7 {period}",
          size=10, color=SUBTITLE_GRAY, align="right", width_in=4.8)


def _footer(c, page_num, total_pages):
    _rect(c, 0.5, 6.9, 12.3, 0.01, fill=BORDER_GRAY)
    _text(c, 0.5, 7.05, "Hospital Alem\u00e1n \u00b7 Fuente: Tecnovoz", size=8, color=TEXT_GRAY)
    _text(c, 9.0, 7.05, f"P\u00e1gina {page_num} de {total_pages}",
          size=8, color=TEXT_GRAY, align="right", width_in=3.8)


def _section_title(c, text, y_top):
    _rect(c, 0.5, y_top, 0.06, 0.35, fill=DARK_NAVY)
    _text(c, 0.7, y_top + 0.05, text, size=14, bold=True, color=TEXT_DARK)


def _kpi_card(c, x, y, w, label, value, variation=None, accent=None,
              h=0.82, value_size=20, label_size=7):
    """Standard KPI card.

    The variation band is ALWAYS reserved, even when there is no variation,
    so that values stay aligned across every card in a row.
    """
    _rect(c, x, y, w, h, fill=WHITE, stroke=BORDER_GRAY)
    if accent:
        _rect(c, x, y, w, 0.045, fill=accent)

    label_top, label_h = y + 0.10, 0.22
    var_h = 0.22
    value_top = label_top + label_h
    value_h = h - (value_top - y) - var_h - 0.05

    _text_in_box(c, x, label_top, w, label_h, str(label).upper(),
                 size=label_size, color=TEXT_GRAY, align="left")
    _text_in_box(c, x, value_top, w, value_h, value,
                 size=value_size, bold=True, color=DARK_NAVY, align="center")
    _variation(c, x, y + h - var_h - 0.05, w, var_h, variation, size=9)


def _big_kpi_card(c, x, y, w, h, label, value, variation=None, accent=None):
    """Large KPI card for the main dashboard page (same fixed-band logic)."""
    _rect(c, x, y, w, h, fill=WHITE, stroke=BORDER_GRAY)
    if accent:
        _rect(c, x, y, w, 0.06, fill=accent)

    label_top, label_h = y + 0.22, 0.32
    var_h = 0.32
    value_top = label_top + label_h
    value_h = h - (value_top - y) - var_h - 0.10

    _text_in_box(c, x, label_top, w, label_h, str(label).upper(),
                 size=13, color=TEXT_GRAY, align="center")
    _text_in_box(c, x, value_top, w, value_h, value,
                 size=44, bold=True, color=DARK_NAVY, align="center")
    _variation(c, x, y + h - var_h - 0.10, w, var_h, variation, size=13)


def _time_card(c, x, y, w, label, value):
    h = 0.66
    _rect(c, x, y, w, h, fill=WHITE, stroke=BORDER_GRAY)
    _text_in_box(c, x, y + 0.08, w, 0.24, str(label).upper(),
                 size=8, color=TEXT_GRAY, align="left")
    _text_in_box(c, x, y + 0.32, w, h - 0.38, value,
                 size=22, bold=True, color=DARK_NAVY, align="center")


def _table(c, x, y, col_widths, headers, rows, header_size=8, row_size=8,
           row_h=0.26, align_first_left=True, bold_last_row=False):
    """Draw a table with a navy header and alternating row shading.

    Cell text is vertically centred inside its own row rectangle.
    """
    total_w = sum(col_widths)

    # Header row
    _rect(c, x, y, total_w, row_h, fill=DARK_NAVY)
    cx = x
    for w, h_text in zip(col_widths, headers):
        _text_in_box(c, cx, y, w, row_h, h_text, size=header_size,
                     bold=True, color=WHITE, align="center")
        cx += w

    # Data rows
    cy = y + row_h
    for i, row in enumerate(rows):
        is_last = bold_last_row and i == len(rows) - 1
        bg = LIGHT_GRAY if (i % 2 == 0 or is_last) else WHITE
        _rect(c, x, cy, total_w, row_h, fill=bg)
        cx = x
        for j, (w, val) in enumerate(zip(col_widths, row)):
            align = "left" if (j == 0 and align_first_left) else "right"
            _text_in_box(c, cx, cy, w, row_h, val, size=row_size,
                         bold=is_last,
                         color=DARK_NAVY if is_last else TEXT_DARK,
                         align=align)
            cx += w
        cy += row_h

    return cy


# ======================================================================
# Page builders
# ======================================================================

def _page_cover(c, period):
    _rect(c, 0, 0, 13.333, 0.35, fill=DARK_NAVY)
    _rect(c, 0, 0.35, 13.333, 0.04, fill=GREEN)

    # Embedded logo
    logo_bytes = None
    try:
        from app.report_generator.logo_data import LOGO_HA_APAISADO_B64
        logo_bytes = base64.b64decode(LOGO_HA_APAISADO_B64)
    except Exception:
        pass

    if logo_bytes:
        _image(c, logo_bytes, (13.333 - 7.0) / 2, 1.3, 7.0, 7.0 / 4.95)
    else:
        _text(c, 0, 2.4, "Hospital Alem\u00e1n", size=44, bold=True,
              color=DARK_NAVY, align="center", width_in=13.333)

    _rect(c, 0.8, 3.6, 0.06, 0.5, fill=GREEN)
    _text(c, 1.0, 3.75, "Productividad del Contact Center", size=28, bold=True, color=DARK_NAVY)
    _text(c, 1.0, 4.35, "An\u00e1lisis de Campa\u00f1as", size=16, color=TEXT_DARK)
    _text(c, 1.0, 4.75, "Volumen de llamadas, nivel de atenci\u00f3n y tiempos operativos",
          size=11, color=TEXT_GRAY)

    _rect(c, 1.0, 5.3, 3.5, 0.7, fill=LIGHT_GRAY, stroke=BORDER_GRAY)
    _text_in_box(c, 1.0, 5.36, 3.5, 0.24, "PER\u00cdODO ANALIZADO",
                 size=8, color=TEXT_GRAY, align="left", pad_in=0.15)
    _text_in_box(c, 1.0, 5.60, 3.5, 0.34, period,
                 size=14, bold=True, color=DARK_NAVY, align="left", pad_in=0.15)

    _text_in_box(c, 9.5, 5.36, 3.0, 0.24, "FUENTE",
                 size=8, color=TEXT_GRAY, align="right")
    _text_in_box(c, 9.5, 5.60, 3.0, 0.34, "Tecnovoz",
                 size=14, bold=True, color=DARK_NAVY, align="right")

    _rect(c, 0, 7.1, 13.333, 0.04, fill=GREEN)
    _rect(c, 0, 7.14, 13.333, 0.36, fill=DARK_NAVY)


def _page_general_data(c, period, kpis, variations, page_num, total_pages):
    _header_bar(c, "Datos Generales", period)
    _footer(c, page_num, total_pages)
    _section_title(c, "Indicadores principales del mes", 0.9)
    _text(c, 0.7, 1.45, "Variaciones calculadas respecto al mes anterior.",
          size=10, italic=True, color=TEXT_GRAY)

    # Row 1 \u2014 two large cards
    card_w, gap, h1 = 5.5, 0.4, 2.4
    x0 = (13.333 - (card_w * 2 + gap)) / 2
    _big_kpi_card(c, x0, 1.85, card_w, h1, "Recibidas",
                  kpis.get("recibidas", "\u2014"), variations.get("recibidas"), DARK_NAVY)
    _big_kpi_card(c, x0 + card_w + gap, 1.85, card_w, h1, "Atendidas",
                  kpis.get("atendidas", "\u2014"), variations.get("atendidas"), MEDIUM_BLUE)

    # Row 2 \u2014 three cards
    cw2, gap2, h2 = 3.9, 0.3, 2.2
    x1 = (13.333 - (cw2 * 3 + gap2 * 2)) / 2
    _big_kpi_card(c, x1, 4.45, cw2, h2, "Prom. Diario Recibidas",
                  kpis.get("promedio_recibidas", "\u2014"), None, TEXT_GRAY)
    _big_kpi_card(c, x1 + cw2 + gap2, 4.45, cw2, h2, "Prom. Diario Atendidas",
                  kpis.get("promedio_atendidas", "\u2014"), None, TEXT_GRAY)
    _big_kpi_card(c, x1 + (cw2 + gap2) * 2, 4.45, cw2, h2, "Nivel de Atenci\u00f3n",
                  kpis.get("nivel_atencion", "\u2014"), variations.get("nivel_atencion"), GREEN)


def _page_campaign(c, name, kpis, variations, chart_path, period, page_num, total_pages,
                   is_all=False):
    title = name if is_all else f"Campa\u00f1a: {name}"
    _header_bar(c, title, period)
    _footer(c, page_num, total_pages)
    _section_title(c, "Indicadores y distribuci\u00f3n diaria", 0.85)

    cw, gap = 2.3, 0.15
    cards = [
        ("Recibidas", kpis.get("recibidas", "-"), variations.get("recibidas"), DARK_NAVY),
        ("Atendidas", kpis.get("atendidas", "-"), variations.get("atendidas"), MEDIUM_BLUE),
        ("Prom. Recibidas", kpis.get("promedio_recibidas", "-"), None, None),
        ("Prom. Atendidas", kpis.get("promedio_atendidas", "-"), None, None),
        ("Nivel de Atenci\u00f3n", kpis.get("nivel_atencion", "-"),
         variations.get("nivel_atencion"), GREEN),
    ]
    for i, (lbl, val, var, acc) in enumerate(cards):
        _kpi_card(c, 0.5 + i * (cw + gap), 1.28, cw, lbl, val, var, acc)

    tw = 3.8
    _time_card(c, 0.5, 2.22, tw, "Conversaci\u00f3n", kpis.get("tiempo_conversacion", "-"))
    _time_card(c, 0.5 + tw + gap, 2.22, tw, "Demora", kpis.get("tiempo_demora", "-"))
    _time_card(c, 0.5 + (tw + gap) * 2, 2.22, tw, "Abandono", kpis.get("tiempo_abandono", "-"))

    _image(c, chart_path, 0.35, 3.05, 12.6, 3.75)


def _page_chart(c, title, section, chart_path, period, page_num, total_pages,
                footnote=None):
    _header_bar(c, title, period)
    _footer(c, page_num, total_pages)
    _section_title(c, section, 0.9)
    _image(c, chart_path, 0.3, 1.4, 12.5, 5.2)
    if footnote:
        _rect(c, 0.5, 6.25, 12.3, 0.5, fill=LIGHT_GRAY)
        _text(c, 0.7, 6.5, footnote, size=9, italic=True, color=TEXT_GRAY)


def _page_dual_chart(c, title, section, left, right, period, page_num, total_pages,
                     footnote=None):
    _header_bar(c, title, period)
    _footer(c, page_num, total_pages)
    _section_title(c, section, 0.9)
    _image(c, left, 0.2, 1.4, 6.5, 4.8)
    _image(c, right, 6.8, 1.4, 6.0, 4.8)
    if footnote:
        _rect(c, 0.5, 6.25, 12.3, 0.5, fill=LIGHT_GRAY)
        _text(c, 0.7, 6.5, footnote, size=9, italic=True, color=TEXT_GRAY)


def _page_skill_table(c, skill_table, period, page_num, total_pages):
    _header_bar(c, "An\u00e1lisis de Habilidades", period)
    _footer(c, page_num, total_pages)
    _section_title(c, "Detalle por habilidad \u2014 volumen, atenci\u00f3n y tiempos promedio", 0.9)

    headers = ["Habilidad", "Recibidas", "Atendidas", "NA",
               "Conversaci\u00f3n", "Demora", "Abandono"]
    widths = [2.5, 1.4, 1.4, 1.2, 1.5, 1.5, 1.5]
    rows = [[s["name"], s["recibidas"], s["atendidas"], s["na"],
             s["conversacion"], s["demora"], s["abandono"]] for s in skill_table]
    _table(c, 0.5, 1.4, widths, headers, rows, row_h=0.24, row_size=7)


def _page_monthly_trend(c, trend, chart_path, period, page_num, total_pages):
    _header_bar(c, "Evoluci\u00f3n Mensual", period)
    _footer(c, page_num, total_pages)
    _section_title(c, "Tendencia mensual del a\u00f1o", 0.9)

    if not trend:
        _text(c, 0.7, 1.8, "Sin datos hist\u00f3ricos disponibles",
              size=12, italic=True, color=TEXT_GRAY)
        return

    n = len(trend)
    label_w = 1.6
    col_w = min(1.9, (12.0 - label_w) / n)
    widths = [label_w] + [col_w] * n
    total_w = sum(widths)
    x = (13.333 - total_w) / 2

    headers = [""] + [r["month_name"] for r in trend]
    rows = [
        ["Recibidas"] + [f"{r['recibidas']:,}".replace(",", ".") for r in trend],
        ["Atendidas"] + [f"{r['atendidas']:,}".replace(",", ".") for r in trend],
        ["Nivel de Atenci\u00f3n"] + [f"{r['nivel_atencion']:.1f}%".replace(".", ",") for r in trend],
    ]
    _table(c, x, 1.35, widths, headers, rows, row_h=0.3, row_size=9, header_size=9)
    _image(c, chart_path, 0.5, 3.0, 12.3, 3.7)


def _page_outbound(c, outbound, chart_images, period, page_num, total_pages):
    _header_bar(c, "Llamadas Salientes", period)
    _footer(c, page_num, total_pages)
    _section_title(c, "Resumen de gesti\u00f3n de llamadas salientes", 0.9)

    total = outbound.get("total", 0)
    total_str = f"{int(total):,}".replace(",", ".")

    _kpi_card(c, 0.5, 1.4, 3.8, "Total Llamadas Salientes", total_str, None, DARK_NAVY)
    _kpi_card(c, 4.6, 1.4, 3.8, "Rotaciones AM", "", None, MEDIUM_BLUE)
    _kpi_card(c, 8.7, 1.4, 3.8, "Solo Operadores AM", "", None, GREEN)
    _text(c, 4.6, 2.62, "Completar manualmente \u2014 fuente: registro de cancelaciones de supervisores",
          size=8, italic=True, color=TEXT_GRAY, align="center", width_in=7.9)

    _image(c, chart_images.get("outbound_result"), 0.3, 2.8, 6.2, 3.9)
    _image(c, chart_images.get("outbound_daily"), 6.7, 2.8, 6.3, 3.9)


def _page_annex_daily(c, campaign_name, daily_rows, period, page_num, total_pages):
    _header_bar(c, f"Anexo \u2014 {campaign_name}", period)
    _footer(c, page_num, total_pages)
    _section_title(c, f"Productividad diaria \u2014 {campaign_name}", 0.9)

    if not daily_rows:
        _text(c, 0.7, 1.8, "Sin datos disponibles", size=12, italic=True, color=TEXT_GRAY)
        return

    headers = ["Fecha", "Recib.", "Atend.", "NA"]

    total_rec = total_att = 0
    for r in daily_rows:
        try:
            total_rec += int(str(r["recibidas"]).replace(".", "").replace(",", ""))
            total_att += int(str(r["atendidas"]).replace(".", "").replace(",", ""))
        except ValueError:
            pass
    na_total = (total_att / total_rec * 100) if total_rec else 0
    total_row = ["Total general",
                 f"{total_rec:,}".replace(",", "."),
                 f"{total_att:,}".replace(",", "."),
                 f"{na_total:.2f}%".replace(".", ",")]

    data = [[r["fecha"], r["recibidas"], r["atendidas"], r["na"]] for r in daily_rows]

    if len(data) <= 16:
        widths = [1.75] * 4
        x = (13.333 - sum(widths)) / 2
        _table(c, x, 1.4, widths, headers, data + [total_row],
               row_h=0.28, bold_last_row=True, align_first_left=False)
    else:
        mid = (len(data) + 1) // 2
        left, right = data[:mid], data[mid:] + [total_row]
        widths = [1.4] * 4
        tw = sum(widths)
        gap = 0.5
        x0 = (13.333 - tw * 2 - gap) / 2
        _table(c, x0, 1.4, widths, headers, left, row_h=0.26, align_first_left=False)
        _table(c, x0 + tw + gap, 1.4, widths, headers, right,
               row_h=0.26, bold_last_row=True, align_first_left=False)


def _page_skills_reference(c, skills_reference, period, page_num, total_pages):
    _header_bar(c, "Anexo \u2014 Referencia de Habilidades", period)
    _footer(c, page_num, total_pages)
    _section_title(c, "Habilidades por campa\u00f1a", 0.9)

    if not skills_reference:
        _text(c, 0.7, 1.8, "Sin datos disponibles", size=12, italic=True, color=TEXT_GRAY)
        return

    rows = [[s["skill"], s["campaign"]] for s in skills_reference]
    headers = ["Habilidad", "Campa\u00f1a"]
    n = len(rows)
    n_cols = 1 if n <= 14 else (2 if n <= 28 else 3)
    per_col = -(-n // n_cols)
    chunks = [rows[i * per_col:(i + 1) * per_col] for i in range(n_cols)]
    chunks = [ch for ch in chunks if ch]

    tw = 3.9 if n_cols == 3 else (5.6 if n_cols == 2 else 6.5)
    widths = [tw * 0.55, tw * 0.45]
    gap = 0.35
    total_w = tw * len(chunks) + gap * (len(chunks) - 1)
    x0 = (13.333 - total_w) / 2

    for idx, chunk in enumerate(chunks):
        _table(c, x0 + idx * (tw + gap), 1.4, widths, headers, chunk,
               row_h=0.26, row_size=8, align_first_left=True)


# ======================================================================
# Main entry point
# ======================================================================

def generate_pdf_report(
    period: str,
    global_kpis: dict[str, str],
    global_variations: dict[str, str],
    campaign_data: list[dict[str, Any]],
    skill_table: list[dict[str, str]],
    chart_images: dict[str, Any],
    annexes: list[dict[str, Any]] | None = None,
    outbound: dict[str, Any] | None = None,
    monthly_trend: list[dict[str, Any]] | None = None,
    donut_footnote: str | None = None,
    skills_reference: list[dict[str, str]] | None = None,
) -> bytes:
    """Generate the report as a PDF, mirroring the PPTX layout.

    Returns the PDF file content as bytes.
    """
    annexes = annexes or []
    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    c.setTitle(f"Productividad del Contact Center \u00b7 {period}")
    c.setAuthor("Hospital Alem\u00e1n")

    # Count pages upfront so footers are accurate
    total = 4 + len(campaign_data) + 1 + len(annexes)
    if monthly_trend:
        total += 1
    if outbound:
        total += 1
    if chart_images.get("skill_volume_top10"):
        total += 1
    if skills_reference:
        total += 1

    page = 1

    _page_cover(c, period)
    c.showPage()
    page += 1

    _page_general_data(c, period, global_kpis, global_variations, page, total)
    c.showPage()
    page += 1

    _page_chart(c, "Distribuci\u00f3n por D\u00eda de Semana",
                "Comportamiento por d\u00eda \u2014 todas las campa\u00f1as",
                chart_images.get("weekday_distribution"), period, page, total)
    c.showPage()
    page += 1

    _page_dual_chart(c, "An\u00e1lisis de Campa\u00f1as", "Volumen y participaci\u00f3n por campa\u00f1a",
                     chart_images.get("campaign_volume"),
                     chart_images.get("campaign_share"),
                     period, page, total, footnote=donut_footnote)
    c.showPage()
    page += 1

    for camp in campaign_data:
        _page_campaign(c, camp["name"], camp["kpis"], camp.get("variations", {}),
                       camp.get("chart_path"), period, page, total,
                       is_all=camp.get("is_all", False))
        c.showPage()
        page += 1

    if monthly_trend:
        _page_monthly_trend(c, monthly_trend, chart_images.get("monthly_evolution"),
                            period, page, total)
        c.showPage()
        page += 1

    if outbound:
        _page_outbound(c, outbound, chart_images, period, page, total)
        c.showPage()
        page += 1

    if chart_images.get("skill_volume_top10"):
        _page_chart(c, "An\u00e1lisis de Habilidades \u2014 Top 10",
                    "Top 10 habilidades por volumen de llamadas",
                    chart_images["skill_volume_top10"], period, page, total)
        c.showPage()
        page += 1

    _page_skill_table(c, skill_table, period, page, total)
    c.showPage()
    page += 1

    for annex in annexes:
        _page_annex_daily(c, annex["campaign_name"], annex["daily_rows"],
                          period, page, total)
        c.showPage()
        page += 1

    if skills_reference:
        _page_skills_reference(c, skills_reference, period, page, total)
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
