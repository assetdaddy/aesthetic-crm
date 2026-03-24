from __future__ import annotations

"""PDF generation helpers for consent forms."""

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONT_READY = False


def build_consent_pdf(consent: dict, signature_path: Path | None) -> bytes:
    """Create a branded PDF document for a saved electronic consent."""

    _register_fonts()

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=32 * mm,
        bottomMargin=18 * mm,
        title=f"{consent['customer_name']} 전자 동의서",
    )

    styles = _build_styles()
    story = [
        Paragraph("Cheongdam Atelier Electronic Consent", styles["brand"]),
        Spacer(1, 6 * mm),
        Paragraph("전자 동의서", styles["title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            "청담동 럭셔리 에스테틱 상담 플로우에 맞춰 저장된 고객 전자 동의서입니다.",
            styles["body"],
        ),
        Spacer(1, 7 * mm),
        _build_info_table(consent, styles),
        Spacer(1, 6 * mm),
        Paragraph("동의 항목", styles["section"]),
        Spacer(1, 2 * mm),
    ]

    for item in consent["agreement_items"]:
        story.append(Paragraph(f"• {item}", styles["bullet"]))
        story.append(Spacer(1, 1.5 * mm))

    if consent.get("notes"):
        story.extend(
            [
                Spacer(1, 4 * mm),
                Paragraph("특이사항 메모", styles["section"]),
                Spacer(1, 2 * mm),
                Paragraph(consent["notes"].replace("\n", "<br/>"), styles["body"]),
            ]
        )

    if signature_path is not None and signature_path.exists():
        story.extend(
            [
                Spacer(1, 8 * mm),
                Paragraph("고객 서명", styles["section"]),
                Spacer(1, 3 * mm),
                Image(
                    str(signature_path),
                    width=64 * mm,
                    height=28 * mm,
                    hAlign="LEFT",
                ),
            ]
        )

    document.build(story, onFirstPage=_draw_page_chrome, onLaterPages=_draw_page_chrome)
    return buffer.getvalue()


def _register_fonts() -> None:
    global _FONT_READY
    if _FONT_READY:
        return

    # ReportLab ships CJK CID fonts that work well for Korean text without
    # bundling a separate TTF asset into the project.
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    _FONT_READY = True


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand",
            parent=base["Normal"],
            fontName="HYGothic-Medium",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#C6A46A"),
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="HYSMyeongJo-Medium",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#5B2B3F"),
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading2"],
            fontName="HYGothic-Medium",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#6A334B"),
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="HYGothic-Medium",
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#4A3841"),
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontName="HYGothic-Medium",
            fontSize=10.5,
            leading=16,
            leftIndent=2 * mm,
            textColor=colors.HexColor("#4A3841"),
        ),
    }


def _build_info_table(consent: dict, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["고객명", consent["customer_name"]],
        ["연락처", consent["phone"]],
        ["시술명", consent["treatment_name"]],
        ["서명 일시", consent["signed_at"]],
    ]
    table = Table(rows, colWidths=[28 * mm, 126 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "HYGothic-Medium"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 14),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6A334B")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#4A3841")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#FFF3F5")),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E8D3DA")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E8D3DA")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _draw_page_chrome(canvas, document) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#5B2B3F"))
    canvas.rect(0, height - 22 * mm, width, 22 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#EAD7B8"))
    canvas.rect(0, height - 24 * mm, width, 2.2 * mm, stroke=0, fill=1)
    canvas.setFont("HYSMyeongJo-Medium", 16)
    canvas.setFillColor(colors.white)
    canvas.drawString(18 * mm, height - 14 * mm, "Cheongdam Atelier")
    canvas.setFont("HYGothic-Medium", 9)
    canvas.setFillColor(colors.HexColor("#A88B99"))
    canvas.drawRightString(width - 18 * mm, 12 * mm, f"Page {document.page}")
    canvas.restoreState()
