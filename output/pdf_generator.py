"""
Counterplay PDF Report Generator
Produces a clean, professional competitive landscape brief as a downloadable PDF.
"""

import io
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    HRFlowable,
)


# ── Brand colors ──────────────────────────────────────────────────────

DARK = HexColor("#1a1a2e")
ACCENT = HexColor("#e94560")
MID = HexColor("#16213e")
LIGHT_BG = HexColor("#f5f5f7")
TEXT = HexColor("#2d2d2d")
SUBTLE = HexColor("#6b7280")
WHITE = HexColor("#ffffff")


def _get_styles():
    """Create custom paragraph styles for the report."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=32,
        textColor=DARK,
        spaceAfter=6,
        fontName="Helvetica-Bold",
        leading=38,
    ))

    styles.add(ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontSize=14,
        textColor=SUBTLE,
        spaceAfter=4,
        fontName="Helvetica",
        leading=20,
    ))

    styles.add(ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontSize=10,
        textColor=SUBTLE,
        spaceBefore=20,
        fontName="Helvetica",
    ))

    styles.add(ParagraphStyle(
        "SectionHead",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=DARK,
        spaceBefore=24,
        spaceAfter=10,
        fontName="Helvetica-Bold",
        leading=22,
    ))

    styles.add(ParagraphStyle(
        "SubHead",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=ACCENT,
        spaceBefore=16,
        spaceAfter=6,
        fontName="Helvetica-Bold",
        leading=16,
    ))

    styles.add(ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        textColor=TEXT,
        spaceAfter=8,
        fontName="Helvetica",
        leading=14,
        alignment=TA_JUSTIFY,
    ))

    styles.add(ParagraphStyle(
        "BoldBody",
        parent=styles["Normal"],
        fontSize=10,
        textColor=TEXT,
        spaceAfter=8,
        fontName="Helvetica-Bold",
        leading=14,
    ))

    styles.add(ParagraphStyle(
        "BrandName",
        parent=styles["Heading2"],
        fontSize=15,
        textColor=ACCENT,
        spaceBefore=20,
        spaceAfter=8,
        fontName="Helvetica-Bold",
        leading=18,
    ))

    styles.add(ParagraphStyle(
        "FooterText",
        parent=styles["Normal"],
        fontSize=8,
        textColor=SUBTLE,
        fontName="Helvetica",
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        "StatNumber",
        parent=styles["Normal"],
        fontSize=24,
        textColor=ACCENT,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        leading=28,
    ))

    styles.add(ParagraphStyle(
        "StatLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=SUBTLE,
        fontName="Helvetica",
        alignment=TA_CENTER,
        leading=12,
    ))

    return styles


def _markdown_to_paragraphs(text: str, styles) -> list:
    """Convert markdown-ish text to ReportLab flowables."""
    elements = []
    lines = text.split("\n")
    current_para = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if current_para:
                para_text = " ".join(current_para)
                para_text = _convert_inline_markdown(para_text)
                elements.append(Paragraph(para_text, styles["Body"]))
                current_para = []
            continue

        # H2 headers
        if stripped.startswith("## "):
            if current_para:
                para_text = " ".join(current_para)
                para_text = _convert_inline_markdown(para_text)
                elements.append(Paragraph(para_text, styles["Body"]))
                current_para = []
            header_text = stripped[3:].strip()
            elements.append(Paragraph(header_text, styles["SectionHead"]))
            elements.append(HRFlowable(
                width="100%", thickness=1, color=ACCENT,
                spaceAfter=10, spaceBefore=2,
            ))
            continue

        # H3 headers
        if stripped.startswith("### "):
            if current_para:
                para_text = " ".join(current_para)
                para_text = _convert_inline_markdown(para_text)
                elements.append(Paragraph(para_text, styles["Body"]))
                current_para = []
            header_text = stripped[4:].strip()
            elements.append(Paragraph(header_text, styles["SubHead"]))
            continue

        # Bullet points
        if stripped.startswith("- ") or stripped.startswith("* "):
            if current_para:
                para_text = " ".join(current_para)
                para_text = _convert_inline_markdown(para_text)
                elements.append(Paragraph(para_text, styles["Body"]))
                current_para = []
            bullet_text = stripped[2:]
            bullet_text = _convert_inline_markdown(bullet_text)
            elements.append(Paragraph(
                f"\u2022  {bullet_text}", styles["Body"]
            ))
            continue

        current_para.append(stripped)

    if current_para:
        para_text = " ".join(current_para)
        para_text = _convert_inline_markdown(para_text)
        elements.append(Paragraph(para_text, styles["Body"]))

    return elements


def _convert_inline_markdown(text: str) -> str:
    """Convert inline markdown bold/italic to ReportLab XML tags."""
    # Bold: **text** -> <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Italic: *text* -> <i>text</i>
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


def _build_stats_row(brand_data: dict, styles) -> list:
    """Build a stats summary row for the overview section."""
    elements = []

    table_data = [["Brand", "Active Ads", "Dominant Format", "Offer Rate", "Avg Age"]]

    for brand, data in brand_data.items():
        ads = data.get("ads", [])
        clfs = data.get("classifications", [])
        total = len(ads)

        # Dominant format
        media = {}
        for ad in ads:
            mt = ad.get("media_type", "unknown")
            media[mt] = media.get(mt, 0) + 1
        dominant = max(media, key=media.get) if media else "N/A"

        # Offer rate
        offer_count = sum(1 for c in clfs if c.get("has_offer"))
        offer_rate = f"{offer_count/len(clfs)*100:.0f}%" if clfs else "N/A"

        # Avg age
        from datetime import timezone
        now = datetime.now(timezone.utc)
        ages = []
        for ad in ads:
            start = ad.get("start_date", "")
            if start:
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    ages.append((now - start_dt).days)
                except (ValueError, TypeError):
                    pass
        avg_age = f"{sum(ages)/len(ages):.0f}d" if ages else "N/A"

        table_data.append([brand, str(total), dominant, offer_rate, avg_age])

    table = Table(table_data, colWidths=[120, 70, 100, 70, 70])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, SUBTLE),
    ]))
    elements.append(table)
    return elements


def generate_pdf(analysis: dict) -> bytes:
    """
    Generate a complete Counterplay landscape PDF from analysis results.
    Returns PDF as bytes.
    """
    buffer = io.BytesIO()
    styles = _get_styles()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=25 * mm,
        bottomMargin=20 * mm,
    )

    story = []

    # ── Cover page ────────────────────────────────────────────────────
    story.append(Spacer(1, 80))
    story.append(Paragraph("COUNTERPLAY", styles["CoverTitle"]))
    story.append(HRFlowable(
        width="40%", thickness=3, color=ACCENT,
        spaceAfter=16, spaceBefore=4,
    ))

    brands_str = " vs ".join(analysis["brands"])
    story.append(Paragraph(
        f"Competitive Creative Landscape",
        styles["CoverSubtitle"],
    ))
    story.append(Paragraph(
        f"{brands_str}",
        styles["CoverSubtitle"],
    ))
    story.append(Paragraph(
        f'{analysis["category"]} \u2022 {analysis["market"]}',
        styles["CoverSubtitle"],
    ))

    gen_date = datetime.fromisoformat(analysis["generated_at"]).strftime("%B %d, %Y")
    story.append(Paragraph(
        f"Generated {gen_date}",
        styles["CoverMeta"],
    ))
    story.append(Paragraph(
        "Powered by Counterplay \u2022 AI-driven competitive creative intelligence",
        styles["CoverMeta"],
    ))

    story.append(PageBreak())

    # ── Overview stats ────────────────────────────────────────────────
    story.append(Paragraph("SNAPSHOT", styles["SectionHead"]))
    story.append(HRFlowable(
        width="100%", thickness=1, color=ACCENT,
        spaceAfter=12, spaceBefore=2,
    ))
    story.extend(_build_stats_row(analysis["brand_data"], styles))
    story.append(Spacer(1, 16))

    # ── Individual brand profiles ─────────────────────────────────────
    story.append(Paragraph("BRAND PROFILES", styles["SectionHead"]))
    story.append(HRFlowable(
        width="100%", thickness=1, color=ACCENT,
        spaceAfter=10, spaceBefore=2,
    ))

    for brand, profile in analysis["brand_profiles"].items():
        story.append(Paragraph(brand.upper(), styles["BrandName"]))
        # Add quant summary
        quant = analysis["brand_data"].get(brand, {}).get("quant_summary", "")
        if quant:
            story.append(Paragraph(
                _convert_inline_markdown(quant.replace("\n", "<br/>")),
                styles["Body"],
            ))
            story.append(Spacer(1, 6))
        story.extend(_markdown_to_paragraphs(profile, styles))
        story.append(Spacer(1, 12))

    story.append(PageBreak())

    # ── Landscape brief ───────────────────────────────────────────────
    story.extend(_markdown_to_paragraphs(analysis["landscape_brief"], styles))

    # ── Footer ────────────────────────────────────────────────────────
    story.append(Spacer(1, 30))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=SUBTLE,
        spaceAfter=8, spaceBefore=8,
    ))
    story.append(Paragraph(
        "COUNTERPLAY \u2022 Competitive Creative Intelligence \u2022 Built by Anshul Sinha",
        styles["FooterText"],
    ))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
