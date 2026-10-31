"""
pdf_export.py – Generering av komplett PDF-rapport för arbetsbänk.
Inkluderar 3D-visualisering, inköpslista, sågplan, kapnota och kostnadsspecifikation.
"""
from __future__ import annotations
import io
import os
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String, Line

from visualization import build_figure


class NumberedCanvas(canvas.Canvas):
    """Tvåstegs canvas som beräknar totalt sidantal och ritar sidfot/sidhuvud."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        # Sidfot
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        footer_text = f"Sida {self._pageNumber} av {page_count}"
        self.drawRightString(595.27 - 36, 20, footer_text)
        self.drawString(36, 20, "🔨 Byggkalkylator – Arbetsbänk | Byggrapport & Inköpsunderlag (jem & fix sortiment)")

        # Tunn linje ovanför sidfoten
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(36, 30, 595.27 - 36, 30)
        self.restoreState()


def _get_pdf_cut_category(name: str):
    n = name.lower()
    if "ben" in n:
        return "Ben", colors.HexColor("#d97706")   # Amber/Wood
    elif "sarg" in n:
        return "Sarg", colors.HexColor("#16a34a")  # Green
    elif "tvärslå" in n or "tvarsla" in n:
        return "Tvärslå", colors.HexColor("#0284c7")  # Blue
    return "Del", colors.HexColor("#6366f1")


def _create_board_pdf_drawing(b, usable_width: float, kerf_mm: int = 5) -> Drawing:
    h = 30
    d = Drawing(usable_width, h)
    stock_len = b.stock_length
    if stock_len <= 0:
        return d
    scale = usable_width / float(stock_len)

    # Balk-ram
    d.add(Rect(0, 1, usable_width, h - 2, fillColor=colors.HexColor("#f8fafc"), strokeColor=colors.HexColor("#94a3b8"), strokeWidth=0.8, rx=3, ry=3))

    cur_x = 0.0
    for idx, (name, length) in enumerate(b.cuts):
        seg_w = length * scale
        cat, col = _get_pdf_cut_category(name)

        # Bit rektangel
        d.add(Rect(cur_x, 1, seg_w, h - 2, fillColor=col, strokeColor=colors.white, strokeWidth=0.8, rx=2, ry=2))

        # Text i rektangeln
        short_name = name
        for prefix in ["Vänster gavel – ", "Höger gavel – ", "Mellanpar 1 – ", "Mellanpar 2 – ", "Mellanpar 3 – "]:
            short_name = short_name.replace(prefix, "")
        short_name = short_name.replace("övre ", "Ö. ").replace("nedre ", "N. ")

        if seg_w >= 75:
            d.add(String(cur_x + seg_w / 2.0, 17.0, short_name, fontName="Helvetica-Bold", fontSize=8, fillColor=colors.white, textAnchor="middle"))
            d.add(String(cur_x + seg_w / 2.0, 7.0, f"{length:,} mm", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.white, textAnchor="middle"))
        elif seg_w >= 45:
            d.add(String(cur_x + seg_w / 2.0, 16.5, short_name[:11], fontName="Helvetica-Bold", fontSize=7, fillColor=colors.white, textAnchor="middle"))
            d.add(String(cur_x + seg_w / 2.0, 7.0, f"{length:,}", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.white, textAnchor="middle"))
        elif seg_w >= 26:
            d.add(String(cur_x + seg_w / 2.0, 11.0, f"{length:,}", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.white, textAnchor="middle"))
        elif seg_w >= 16:
            d.add(String(cur_x + seg_w / 2.0, 11.0, f"{length}", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.white, textAnchor="middle"))

        # Röd sågsnittslinje
        cut_x = cur_x + seg_w
        d.add(Line(cut_x, 0, cut_x, h, strokeColor=colors.HexColor("#dc2626"), strokeWidth=2))
        cur_x += seg_w + (kerf_mm * scale)

    # Restbit / spill
    rem_w = usable_width - cur_x
    if rem_w > 1:
        d.add(Rect(cur_x, 1, rem_w, h - 2, fillColor=colors.HexColor("#e2e8f0"), strokeColor=colors.HexColor("#cbd5e1"), strokeWidth=0.8, rx=2, ry=2))
        pct = (b.remaining / b.stock_length * 100.0) if b.stock_length > 0 else 0.0
        if rem_w >= 50:
            d.add(String(cur_x + rem_w / 2.0, 17.0, "Spill", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor("#475569"), textAnchor="middle"))
            d.add(String(cur_x + rem_w / 2.0, 7.0, f"{b.remaining:,} mm", fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#475569"), textAnchor="middle"))
        elif rem_w >= 28:
            d.add(String(cur_x + rem_w / 2.0, 11.0, f"Spill {b.remaining}", fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor("#475569"), textAnchor="middle"))
        elif rem_w >= 16:
            d.add(String(cur_x + rem_w / 2.0, 11.0, f"{b.remaining}", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#475569"), textAnchor="middle"))

    return d


def _ensure_browser_for_kaleido():
    """
    Säkerställer att Kaleido hittar Chrome eller Chromium (särskilt på Streamlit Community Cloud / Linux).
    Konfigurerar Chromium-flaggor för säker körning i headless container-miljö.
    """
    if not os.environ.get("BROWSER_PATH"):
        candidates = [
            "chromium",
            "chromium-browser",
            "google-chrome",
            "google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/lib/chromium/chromium",
        ]
        for c in candidates:
            p = shutil.which(c) or (c if os.path.isfile(c) and os.access(c, os.X_OK) else None)
            if p:
                os.environ["BROWSER_PATH"] = p
                break

    if not os.environ.get("BROWSER_PATH"):
        try:
            import kaleido
            if hasattr(kaleido, "get_chrome_sync"):
                kaleido.get_chrome_sync()
        except Exception:
            pass

    try:
        import plotly.io as pio
        if hasattr(pio, "kaleido") and hasattr(pio.kaleido, "scope"):
            args = list(getattr(pio.kaleido.scope, "chromium_args", []))
            for req in ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]:
                if req not in args:
                    args.append(req)
            pio.kaleido.scope.chromium_args = tuple(args)
    except Exception:
        pass


def generate_pdf_report(
    geo: Any,
    purchase_plan: Dict[str, Any],
    costs: Dict[str, Any],
    chosen_top_plan: Dict[str, Any],
    shopping_items: List[Dict[str, Any]],
) -> bytes:
    """
    Genererar en komplett PDF-rapport med 3D-bild och tabeller.
    Returnerar PDF-dokumentet som bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=42,
    )
    usable_width = 595.27 - 72  # 523.27 pt

    # ---- Stilar ----
    base_styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )

    section_style = ParagraphStyle(
        "SectionHeading",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )

    body_bold = ParagraphStyle(
        "BodyDarkBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell_style,
        fontName="Helvetica-Bold",
    )

    table_cell_right = ParagraphStyle(
        "TableCellRight",
        parent=table_cell_style,
        alignment=2,
    )

    table_cell_right_bold = ParagraphStyle(
        "TableCellRightBold",
        parent=table_cell_bold,
        alignment=2,
    )

    board_title_style = ParagraphStyle(
        "BoardTitle",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )

    cut_guide_style = ParagraphStyle(
        "CutGuide",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    # =========================================================================
    # SIDA 1: DOKUMENTHUVUD & SPECIFIKATION
    # =========================================================================
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    header_data = [
        [
            Paragraph("🔨 <b>Byggkalkylator – Arbetsbänk</b>", title_style),
            Paragraph(f"<b>Utskrift:</b> {now_str}<br/><b>Butik:</b> jem & fix sortiment", ParagraphStyle("RightMeta", parent=subtitle_style, alignment=2)),
        ],
        [
            Paragraph(
                f"<b>Ram:</b> {geo.L} × {geo.B} mm · <b>Höjd:</b> {geo.H} mm · "
                f"<b>Bänkskiva:</b> {geo.tabletop_L} × {geo.tabletop_B} mm ({chosen_top_plan.get('material', 'Trä')})",
                subtitle_style
            ),
            Paragraph(f"<b>Konstruktion:</b> {geo.n_pairs} benpar ({2*geo.n_pairs} ben · 4 sarger · {2*geo.n_pairs} tvärslåar)", ParagraphStyle("RightMeta2", parent=subtitle_style, alignment=2)),
        ]
    ]
    header_table = Table(header_data, colWidths=[usable_width * 0.65, usable_width * 0.35])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=8))

    # =========================================================================
    # KPI-ÖVERSIKT (4 rutor)
    # =========================================================================
    tot_waste_cost = costs.get("total_waste", 0.0)
    tot_bought_cost = costs.get("total_bought", 0.0)
    tot_used_cost = costs.get("total_used", 0.0)
    waste_pct = (tot_waste_cost / tot_bought_cost * 100.0) if tot_bought_cost > 0 else 0.0
    tot_lpm = purchase_plan.get("total_lpm", 0.0)
    used_lpm = purchase_plan.get("total_used_lpm", 0.0)

    kpi_card_style = lambda label, val, sub, val_col="#0f172a": [
        Paragraph(f"<font size='6.5' color='#64748b'><b>{label.upper()}</b></font>", ParagraphStyle("KL", alignment=1)),
        Spacer(1, 1),
        Paragraph(f"<font size='13' color='{val_col}'><b>{val}</b></font>", ParagraphStyle("KV", alignment=1)),
        Spacer(1, 1),
        Paragraph(f"<font size='6.5' color='#64748b'>{sub}</font>", ParagraphStyle("KS", alignment=1)),
    ]

    col_w = usable_width / 4.0
    kpi_data = [[
        kpi_card_style("Inköpt material", f"{tot_bought_cost:,.0f} kr", "att betala i butik"),
        kpi_card_style("Faktiskt använt", f"{tot_used_cost:,.0f} kr", "material i bänken", "#16a34a"),
        kpi_card_style("Spillkostnad", f"{tot_waste_cost:,.0f} kr", f"{waste_pct:.1f}% totalt spill", "#dc2626" if waste_pct > 20 else "#d97706"),
        kpi_card_style("Virkesbehov", f"{tot_lpm:.1f} lpm", f"varav {used_lpm:.1f} lpm i bänk", "#0284c7"),
    ]]

    kpi_table = Table(kpi_data, colWidths=[col_w] * 4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6))

    # =========================================================================
    # 3D-VISUALISERING (På sida 1)
    # =========================================================================
    story.append(Paragraph("🎯 <b>3D-Konstruktionsmodell & Mått</b>", section_style))

    try:
        _ensure_browser_for_kaleido()
        fig = build_figure(geo, dark_theme=False, show_dimensions=True)
        img_bytes = fig.to_image(format="png", width=950, height=450, scale=1.3)
        img_io = io.BytesIO(img_bytes)
        img_w = usable_width
        img_h = usable_width * (450 / 950)
        img_flow = Image(img_io, width=img_w, height=img_h)
        story.append(img_flow)
    except Exception as e:
        story.append(Paragraph(f"<i>(3D-bild kunde inte renderas: {e})</i>", body_style))

    legend_text = (
        "<b>Färgkodning:</b> &nbsp; "
        "<font color='#C88A38'>■</font> Ben &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#72A852'>■</font> Sarger &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#5090BB'>■</font> Tvärslåar &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#C8A46A'>■</font> Bänkskiva &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#0284c7'>■</font> Benavstånd på golv"
    )
    legend_table = Table([[Paragraph(legend_text, ParagraphStyle("Leg", parent=body_style, alignment=1))]], colWidths=[usable_width])
    legend_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(Spacer(1, 3))
    story.append(legend_table)
    story.append(Spacer(1, 6))

    # =========================================================================
    # 1. INKÖPSLISTA (Placeras på Sida 1 för fullständig överblick!)
    # =========================================================================
    story.append(Paragraph("🛒 <b>1. Inköpslista till bygghandeln (jem & fix)</b>", section_style))

    shop_cols = [75, 175, 95, 45, 65, 68]
    shop_rows = [[
        Paragraph("Komponent", table_header_style),
        Paragraph("Artikel (jem & fix)", table_header_style),
        Paragraph("Dimension / Längd", table_header_style),
        Paragraph("Antal", ParagraphStyle("THC", parent=table_header_style, alignment=1)),
        Paragraph("Styckpris", ParagraphStyle("THR", parent=table_header_style, alignment=2)),
        Paragraph("Delsumma", ParagraphStyle("THR2", parent=table_header_style, alignment=2)),
    ]]

    for item in shopping_items:
        shop_rows.append([
            Paragraph(str(item.get("Komponent", "")), table_cell_bold),
            Paragraph(str(item.get("Artikel (jem & fix)", "")), table_cell_style),
            Paragraph(str(item.get("Längd", item.get("Dimension", ""))), table_cell_style),
            Paragraph(str(item.get("Antal", "")), ParagraphStyle("TCC", parent=table_cell_style, alignment=1)),
            Paragraph(f"{item.get('Styckpris', 0):.2f} kr" if isinstance(item.get("Styckpris"), (int, float)) else str(item.get("Styckpris", "")), table_cell_right),
            Paragraph(f"{item.get('Delsumma', 0):.2f} kr" if isinstance(item.get("Delsumma"), (int, float)) else str(item.get("Delsumma", "")), table_cell_right_bold),
        ])

    # Totalsumma-rad
    shop_rows.append([
        Paragraph("<b>TOTALT ATT BETALA I BUTIK</b>", table_cell_bold),
        Paragraph("", table_cell_style),
        Paragraph("", table_cell_style),
        Paragraph("", table_cell_style),
        Paragraph("", table_cell_style),
        Paragraph(f"<b>{tot_bought_cost:,.2f} kr</b>", table_cell_right_bold),
    ])

    shop_table = Table(shop_rows, colWidths=shop_cols)
    shop_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.HexColor("#0f172a")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(shop_table)

    # Sidbrytning till Sida 2: Verkstads- & Kapunderlag
    story.append(PageBreak())

    # =========================================================================
    # SIDA 2: 2. SÅGPLAN
    # =========================================================================
    story.append(Paragraph("🪚 <b>2. Sågplan (Hur reglarna ska kapas i verkstaden)</b>", section_style))
    summary_str = purchase_plan.get("timber_board_summary_str", "")
    if summary_str:
        story.append(Paragraph(f"<b>Optimal virkeskombination:</b> {summary_str} &nbsp;(totalt spill: <b>{purchase_plan.get('timber_waste_pct', 0.0):.1f}%</b>)", body_style))
    story.append(Spacer(1, 4))

    all_bins = []
    if purchase_plan.get("is_combined"):
        all_bins = purchase_plan.get("timber_bins", [])
    else:
        all_bins = purchase_plan.get("leg_bins", []) + purchase_plan.get("frame_bins", [])

    # Färgförklaring
    legend_saw_text = (
        "<b>Färgkodning:</b> &nbsp; "
        "<font color='#d97706'>■</font> <b>Ben</b> &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#16a34a'>■</font> <b>Sarger</b> &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#0284c7'>■</font> <b>Tvärslåar</b> &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#dc2626'><b>|</b></font> <b>Sågsnitt (5 mm)</b> &nbsp;&nbsp;•&nbsp;&nbsp; "
        "<font color='#94a3b8'>■</font> <b>Spill / Restbit</b>"
    )
    legend_saw_table = Table([[Paragraph(legend_saw_text, ParagraphStyle("LegSaw", parent=body_style, fontSize=7, leading=9, alignment=1))]], colWidths=[usable_width])
    legend_saw_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(legend_saw_table)
    story.append(Spacer(1, 6))

    for i, b in enumerate(all_bins, 1):
        pct = (b.remaining / b.stock_length * 100.0) if b.stock_length > 0 else 0.0
        kerf = getattr(b, "saw_kerf", 5)

        board_drawing = _create_board_pdf_drawing(b, usable_width, kerf_mm=kerf)

        # Detaljerad verkstadstabell för denna regel
        mini_cols = [45, 175, 75, 75, 153]
        mini_rows = [[
            Paragraph("Snitt #", table_header_style),
            Paragraph("Delnamn / Placering", table_header_style),
            Paragraph("Kategori", table_header_style),
            Paragraph("Kaplängd", ParagraphStyle("THRC", parent=table_header_style, alignment=2)),
            Paragraph("Kapa vid (från regelns start)", ParagraphStyle("THRC2", parent=table_header_style, alignment=2)),
        ]]

        cum = 0
        for idx, (name, length) in enumerate(b.cuts, 1):
            if idx > 1:
                cum += kerf
            cum += length
            cat, col = _get_pdf_cut_category(name)
            mini_rows.append([
                Paragraph(f"<b>#{idx}</b>", ParagraphStyle("C1", parent=table_cell_style, alignment=1)),
                Paragraph(name, table_cell_bold),
                Paragraph(f"<font color='{col.hexval()}'>■</font> {cat}", table_cell_style),
                Paragraph(f"<b>{length:,} mm</b>", table_cell_right),
                Paragraph(f"<font color='#0284c7'><b>{cum:,} mm</b></font>", table_cell_right),
            ])

        mini_rows.append([
            Paragraph("<b>Rest</b>", ParagraphStyle("CR1", parent=table_cell_style, alignment=1)),
            Paragraph("Kvarvarande restbit / spill", ParagraphStyle("CR2", parent=table_cell_style, textColor=colors.HexColor("#64748b"))),
            Paragraph("Spill", ParagraphStyle("CR3", parent=table_cell_style, textColor=colors.HexColor("#64748b"))),
            Paragraph(f"<b>{b.remaining:,} mm</b>", ParagraphStyle("CR4", parent=table_cell_right, textColor=colors.HexColor("#64748b"))),
            Paragraph(f"<i>({pct:.1f}% spill)</i>", ParagraphStyle("CR5", parent=table_cell_right, textColor=colors.HexColor("#64748b"))),
        ])

        mini_table = Table(mini_rows, colWidths=mini_cols)
        mini_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        board_elements = [
            Paragraph(f"<b>Regel #{i}: {b.stock_length:,} mm Byggregel</b> &nbsp;·&nbsp; {len(b.cuts)} kapade delar &nbsp;•&nbsp; Spill: <b>{b.remaining:,} mm ({pct:.1f}%)</b>", board_title_style),
            Spacer(1, 2),
            board_drawing,
            Spacer(1, 2),
            mini_table,
            Spacer(1, 8),
        ]
        story.append(KeepTogether(board_elements))

    # Ren sidbrytning till Kapnota och Kostnadsspecifikation
    story.append(PageBreak())

    # =========================================================================
    # 3. KOMPLETT KAPNOTA
    # =========================================================================
    story.append(Paragraph("📋 <b>3. Komplett Kapnota (Alla ingående delar)</b>", section_style))

    cut_cols = [200, 75, 95, 75, 78]
    cut_rows = [[
        Paragraph("Delnamn", table_header_style),
        Paragraph("Kategori", table_header_style),
        Paragraph("Profil / Material", table_header_style),
        Paragraph("Längd (mm)", ParagraphStyle("THR_C", parent=table_header_style, alignment=2)),
        Paragraph("Antal", ParagraphStyle("THC_C", parent=table_header_style, alignment=1)),
    ]]

    for cut in geo.cuts:
        cut_rows.append([
            Paragraph(cut.name, table_cell_bold),
            Paragraph(cut.category, table_cell_style),
            Paragraph(cut.profile, table_cell_style),
            Paragraph(f"{cut.length_mm} mm", table_cell_right),
            Paragraph(f"{cut.quantity} st", ParagraphStyle("TC_C2", parent=table_cell_style, alignment=1)),
        ])

    cut_table = Table(cut_rows, colWidths=cut_cols)
    cut_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
    ]))
    story.append(cut_table)
    story.append(Spacer(1, 10))

    # =========================================================================
    # 4. KOSTNADSSPECIFIKATION & SPILL
    # =========================================================================
    story.append(Paragraph("💰 <b>4. Kostnadsspecifikation & Spillanalys</b>", section_style))

    cost_items = costs.get("items", [])
    cost_cols = [223, 100, 100, 100]
    cost_rows = [[
        Paragraph("Post / Komponent", table_header_style),
        Paragraph("Inköpt material (kr)", ParagraphStyle("THR_CS", parent=table_header_style, alignment=2)),
        Paragraph("Faktiskt använt (kr)", ParagraphStyle("THR_CS2", parent=table_header_style, alignment=2)),
        Paragraph("Spillkostnad (kr)", ParagraphStyle("THR_CS3", parent=table_header_style, alignment=2)),
    ]]

    for it in cost_items:
        cost_rows.append([
            Paragraph(str(it.get("Post", "")), table_cell_bold),
            Paragraph(f"{it.get('Inköpt material (kr)', 0):.2f} kr", table_cell_right),
            Paragraph(f"{it.get('Faktiskt använt (kr)', 0):.2f} kr", table_cell_right),
            Paragraph(f"{it.get('Spillkostnad (kr)', 0):.2f} kr", table_cell_right),
        ])

    cost_rows.append([
        Paragraph("<b>TOTALT</b>", table_cell_bold),
        Paragraph(f"<b>{tot_bought_cost:,.2f} kr</b>", table_cell_right_bold),
        Paragraph(f"<b>{tot_used_cost:,.2f} kr</b>", table_cell_right_bold),
        Paragraph(f"<b>{tot_waste_cost:,.2f} kr</b>", table_cell_right_bold),
    ])

    cost_table = Table(cost_rows, colWidths=cost_cols)
    cost_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.HexColor("#0f172a")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(cost_table)

    # Bygg PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()
