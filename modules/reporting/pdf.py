"""Styled PDF export for BI chat results (RTL-aware, chart image, number formatting)."""

from __future__ import annotations

import base64
import os
import re
import tempfile
from typing import Any, Optional

from fpdf import FPDF

from modules.reporting.labels import column_label

RTL_SCRIPT_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)

# Brand palette (matches static/style.css)
ACCENT = (31, 111, 84)          # #1f6f54
ACCENT_STRONG = (21, 82, 62)    # #15523e
ACCENT_SOFT = (228, 240, 234)   # #e4f0ea
HEADER_BG = (31, 111, 84)
HEADER_FG = (255, 255, 255)
ROW_ALT = (244, 247, 245)
BORDER = (216, 211, 197)        # #d8d3c5
INK = (28, 32, 36)
MUTED = (91, 97, 104)

MAX_PDF_ROWS = 80


def is_rtl_text(text: str) -> bool:
    return bool(text and RTL_SCRIPT_RE.search(text))


def normalize_persian_pdf_text(text: Any) -> str:
    """Fix نیم‌فاصله for fpdf2+HarfBuzz (ZWNJ is dropped and letters join).

    Replace U+200C (ZWNJ) with U+2009 (thin space) so words like
    «داده‌ها» render separated instead of «دادهها».
    """
    if text is None:
        return ""
    s = str(text)
    # Zero-width non-joiner (نیم‌فاصله) → thin space (keeps a visible break)
    s = s.replace("\u200c", "\u2009")
    # Some keyboards emit Arabic tatweel or odd spaces around half-spaces
    s = s.replace("\u200d", "")  # ZWJ not useful in our reports
    return s


def format_number(value: Any, sep: str = ",") -> str:
    """Format numbers with a thousands separator every 3 digits."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}".replace(",", sep)
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        if value == int(value):
            return f"{int(value):,}".replace(",", sep)
        whole, frac = f"{value:,.2f}".split(".")
        return f"{whole.replace(',', sep)}.{frac}"

    s = str(value).strip()
    # Already formatted or non-numeric text
    cleaned = s.replace(",", "").replace(";", "").replace(" ", "").replace("\u066c", "")
    try:
        if "." in cleaned:
            return format_number(float(cleaned), sep=sep)
        return format_number(int(cleaned), sep=sep)
    except (TypeError, ValueError):
        return s


def _cell_align(text: str, force_rtl: bool = False) -> str:
    return "R" if force_rtl or is_rtl_text(text) else "L"


def _resolve_unicode_font(pdf: FPDF) -> str:
    possible_fonts = [
        "static/fonts/Vazirmatn-Regular.ttf",
        "static/fonts/Vazir.ttf",
        r"C:/Windows/Fonts/tahoma.ttf",
        r"C:/Windows/Fonts/segoeui.ttf",
        r"C:/Windows/Fonts/arial.ttf",
        "static/fonts/NotoSansArabic-Regular.ttf",
    ]
    for path in possible_fonts:
        if os.path.exists(path):
            base_name = os.path.splitext(os.path.basename(path))[0]
            pdf.add_font(family=base_name, fname=path)
            return base_name
    raise RuntimeError(
        "Unicode TrueType font not found. Place Vazir.ttf (or similar) in static/fonts/."
    )


def _decode_chart_image(chart_image: Optional[str]) -> Optional[str]:
    """Decode a data-URL or raw base64 PNG/JPEG into a temporary file path."""
    if not chart_image:
        return None
    raw = chart_image.strip()
    if "," in raw and raw.startswith("data:"):
        header, b64 = raw.split(",", 1)
        ext = ".png" if "png" in header else ".jpg"
    else:
        b64 = raw
        ext = ".png"
    try:
        data = base64.b64decode(b64)
    except Exception:
        return None
    fd, path = tempfile.mkstemp(suffix=ext, prefix="bichart_")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(data)
    return path


class PDFGenerator(FPDF):
    def __init__(self, font_name: str, force_rtl: bool = False):
        super().__init__()
        self.font_name = font_name
        self.force_rtl = force_rtl
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        # Accent bar
        self.set_fill_color(*ACCENT)
        self.rect(0, 0, self.w, 8, "F")
        self.set_y(12)
        self.set_font(self.font_name, size=9)
        self.set_text_color(*MUTED)
        label = normalize_persian_pdf_text(
            "خروجی گزارش هوش تجاری" if self.force_rtl else "BI Report Export"
        )
        self.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_draw_color(*BORDER)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(6)
        self.set_text_color(*INK)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*BORDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font(self.font_name, size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"{self.page_no()}", align="C")
        self.set_text_color(*INK)

    def section_title(self, text: str):
        # Draw a solid band with rect (more reliable than cell fill + shaping).
        y = self.get_y()
        h = 9
        self.set_fill_color(*ACCENT_SOFT)
        self.set_draw_color(*ACCENT)
        self.rect(self.l_margin, y, self.epw, h, style="FD")
        self.set_text_color(*ACCENT_STRONG)
        self.set_font(self.font_name, size=12)
        self.set_xy(self.l_margin, y)
        self.cell(
            self.epw,
            h,
            normalize_persian_pdf_text(f"  {text}  "),
            align=_cell_align(text, self.force_rtl),
        )
        self.set_xy(self.l_margin, y + h)
        self.set_text_color(*INK)
        self.ln(3)


def generate_llm_pdf(
    output_path: str,
    title: str,
    explanation: str,
    data: Optional[list] = None,
    analysis: Optional[str] = None,
    chart_image: Optional[str] = None,
    number_sep: str = ";",
) -> str:
    # number_sep: thousands separator every 3 digits (default ";")
    sample = " ".join(str(p) for p in (title, explanation, analysis or "") if p)
    force_rtl = is_rtl_text(sample)

    pdf = PDFGenerator(font_name="Helvetica", force_rtl=force_rtl)
    font_name = _resolve_unicode_font(pdf)
    pdf.font_name = font_name
    pdf.set_text_shaping(True)

    chart_path = _decode_chart_image(chart_image)
    try:
        pdf.add_page()

        # Title band
        y = pdf.get_y()
        pdf.set_fill_color(*ACCENT)
        pdf.rect(pdf.l_margin, y, pdf.epw, 12, style="F")
        pdf.set_text_color(*HEADER_FG)
        pdf.set_font(font_name, size=16)
        pdf.set_xy(pdf.l_margin, y)
        pdf.cell(
            pdf.epw,
            12,
            normalize_persian_pdf_text(title or ("گزارش" if force_rtl else "Report")),
            align="C",
        )
        pdf.set_xy(pdf.l_margin, y + 12)
        pdf.set_text_color(*INK)
        pdf.ln(6)

        # Explanation
        pdf.section_title(normalize_persian_pdf_text("توضیح" if force_rtl else "Explanation"))
        pdf.set_font(font_name, size=11)
        body = normalize_persian_pdf_text(explanation or "")
        pdf.multi_cell(0, 7, body, align=_cell_align(body, force_rtl))
        pdf.ln(4)

        # Chart image
        if chart_path and os.path.exists(chart_path):
            pdf.section_title(normalize_persian_pdf_text("نمودار" if force_rtl else "Chart"))
            max_w = pdf.epw
            try:
                # Ensure room for the chart; add a page if needed
                if pdf.get_y() > pdf.h - 80:
                    pdf.add_page()
                    pdf.section_title(normalize_persian_pdf_text("نمودار" if force_rtl else "Chart"))
                pdf.image(chart_path, w=max_w * 0.95, x=pdf.l_margin + pdf.epw * 0.025)
                pdf.ln(6)
            except Exception as img_err:
                pdf.set_font(font_name, size=9)
                pdf.set_text_color(*MUTED)
                msg = f"Chart embed failed: {img_err}"
                pdf.multi_cell(0, 6, msg)
                pdf.set_text_color(*INK)
                pdf.ln(2)

        # Data table
        rows = data or []
        pdf.section_title(normalize_persian_pdf_text("نتایج داده" if force_rtl else "Data Results"))
        if not rows:
            empty = normalize_persian_pdf_text(
                "داده‌ای موجود نیست." if force_rtl else "No data available."
            )
            pdf.set_font(font_name, size=11)
            pdf.cell(0, 8, empty, new_x="LMARGIN", new_y="NEXT", align=_cell_align(empty, force_rtl))
        else:
            columns = list(rows[0].keys())
            draw_cols = list(reversed(columns)) if force_rtl else columns
            n_cols = len(draw_cols)
            row_h = 8
            HEADER_SIZE = 9
            ROW_SIZE = 8
            MIN_FONT_SIZE = 5.5
            MIN_COL_WIDTH = 16.0

            def fit_text(text, max_width, base_size):
                # Shrink the font until the text fits its column; only as a last
                # resort (base_size already down to MIN_FONT_SIZE) truncate with
                # an ellipsis, so cells never spill past their border.
                size = base_size
                pdf.set_font(font_name, size=size)
                while pdf.get_string_width(text) > max_width and size > MIN_FONT_SIZE:
                    size -= 0.5
                    pdf.set_font(font_name, size=size)
                if pdf.get_string_width(text) > max_width:
                    ell = "…"
                    while text and pdf.get_string_width(text + ell) > max_width:
                        text = text[:-1]
                    text = f"{text}{ell}" if text else ell
                return text, size

            # Size each column from its actual content (header + a sample of
            # rows) instead of splitting the page evenly, so long category
            # names and formatted amounts don't overflow into neighboring
            # cells.
            sample_rows = rows[: min(len(rows), 30)]
            pad = pdf.c_margin * 2 + 1.5
            natural_width = {}
            for col in columns:
                pdf.set_font(font_name, size=HEADER_SIZE)
                w = pdf.get_string_width(normalize_persian_pdf_text(column_label(col)))
                pdf.set_font(font_name, size=ROW_SIZE)
                for r in sample_rows:
                    cell_text = normalize_persian_pdf_text(format_number(r.get(col, ""), sep=number_sep))
                    w = max(w, pdf.get_string_width(cell_text))
                natural_width[col] = w + pad

            total_natural = sum(natural_width.values()) or 1
            scale = pdf.epw / total_natural
            col_widths = {col: max(MIN_COL_WIDTH, natural_width[col] * scale) for col in columns}
            overflow = sum(col_widths.values()) - pdf.epw
            if overflow > 0.01:
                flex_cols = [c for c in columns if col_widths[c] > MIN_COL_WIDTH + 0.01]
                flex_total = sum(col_widths[c] for c in flex_cols)
                if flex_total > 0:
                    shrink = max(0.0, (flex_total - overflow) / flex_total)
                    for c in flex_cols:
                        col_widths[c] *= shrink
                else:
                    col_widths = {c: pdf.epw / n_cols for c in columns}

            def draw_header():
                pdf.set_fill_color(*HEADER_BG)
                pdf.set_text_color(*HEADER_FG)
                pdf.set_draw_color(*ACCENT_STRONG)
                for col in draw_cols:
                    label_text = normalize_persian_pdf_text(column_label(col))
                    fitted, size = fit_text(label_text, col_widths[col] - pad, HEADER_SIZE)
                    pdf.set_font(font_name, size=size)
                    pdf.cell(
                        col_widths[col],
                        row_h,
                        fitted,
                        border=1,
                        fill=True,
                        align="C",
                    )
                pdf.ln()
                pdf.set_text_color(*INK)

            draw_header()
            pdf.set_font(font_name, size=ROW_SIZE)
            shown = rows[:MAX_PDF_ROWS]
            for i, row in enumerate(shown):
                # Page break: leave room + redraw header
                if pdf.get_y() + row_h > pdf.page_break_trigger:
                    pdf.add_page()
                    draw_header()
                    pdf.set_font(font_name, size=ROW_SIZE)

                if i % 2 == 1:
                    pdf.set_fill_color(*ROW_ALT)
                    fill = True
                else:
                    fill = False
                pdf.set_draw_color(*BORDER)
                for col in draw_cols:
                    raw = row.get(col, "")
                    cell_text = normalize_persian_pdf_text(format_number(raw, sep=number_sep))
                    fitted, size = fit_text(cell_text, col_widths[col] - pad, ROW_SIZE)
                    pdf.set_font(font_name, size=size)
                    pdf.cell(
                        col_widths[col],
                        row_h,
                        fitted,
                        border=1,
                        fill=fill,
                        align=_cell_align(cell_text, force_rtl),
                    )
                pdf.ln()

            if len(rows) > MAX_PDF_ROWS:
                pdf.ln(2)
                pdf.set_font(font_name, size=9)
                pdf.set_text_color(*MUTED)
                note = normalize_persian_pdf_text(
                    f"نمایش {MAX_PDF_ROWS} ردیف از {len(rows)} — برای همه ردیف‌ها خروجی Excel بگیرید."
                    if force_rtl
                    else f"Showing {MAX_PDF_ROWS} of {len(rows)} rows — export Excel for the full dataset."
                )
                pdf.multi_cell(0, 6, note, align=_cell_align(note, force_rtl))
                pdf.set_text_color(*INK)

        pdf.ln(4)

        # Analysis
        if analysis:
            pdf.section_title(normalize_persian_pdf_text("تحلیل" if force_rtl else "Analysis"))
            pdf.set_font(font_name, size=11)
            pdf.set_fill_color(255, 255, 255)
            analysis_text = normalize_persian_pdf_text(analysis)
            pdf.multi_cell(0, 7, analysis_text, align=_cell_align(analysis_text, force_rtl))

        pdf.output(output_path)
        return output_path
    finally:
        if chart_path and os.path.exists(chart_path):
            try:
                os.remove(chart_path)
            except OSError:
                pass
