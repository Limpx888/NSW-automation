from __future__ import annotations

import base64
import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.report.charts import render_analysis_bars, render_defect_donut
from backend.report.schemas import ReportData

TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def render_report_html(data: ReportData) -> str:
    """Shared by the PDF renderer and the static HTML preview endpoint."""
    template = _env.get_template("report.html")
    return template.render(
        data=data,
        defect_donut_b64=base64.b64encode(render_defect_donut(data)).decode(),
        analysis_bars_b64=base64.b64encode(render_analysis_bars(data)).decode(),
    )


def render_pdf(data: ReportData) -> bytes:
    html_str = render_report_html(data)
    try:
        from weasyprint import HTML

        return HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf()
    except Exception:
        pass

    try:
        return _render_pdf_fallback(data)
    except Exception:
        return _render_pdf_reportlab(data)


def _safe(text: str) -> str:
    return (
        (text or "")
        .replace("—", "-")
        .replace("–", "-")
        .replace("•", "-")
        .replace("★", "*")
        .replace("☆", "-")
        .replace("·", "|")
        .replace("'", "'")
        .replace("'", "'")
        .replace(""", '"')
        .replace(""", '"')
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def _render_pdf_fallback(data: ReportData) -> bytes:
    from fpdf import FPDF

    donut = render_defect_donut(data)
    bars = render_analysis_bars(data)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)

    def heading(title: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(27, 58, 95)
        pdf.cell(0, 8, _safe(title), ln=True)
        pdf.set_draw_color(221, 227, 232)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(27, 33, 38)

    def body(text: str, size: int = 10) -> None:
        pdf.set_font("Helvetica", "", size)
        pdf.multi_cell(0, 5, _safe(text))
        pdf.ln(1)

    # Page 1
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(27, 58, 95)
    pdf.cell(0, 6, _safe(data.title), ln=True)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 9, _safe(data.subtitle), ln=True)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(139, 150, 165)
    pdf.multi_cell(
        0,
        4,
        _safe(
            f"Session {data.session_id} | Generated {data.generated_at:%Y-%m-%d %H:%M UTC} | {data.brand}"
        ),
    )
    pdf.ln(2)

    heading("Output Summary")
    body(data.methodology_note, 9)
    body(data.executive_summary, 9)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(27, 58, 95)
    pdf.cell(
        0,
        6,
        _safe(
            f"Severity {data.severity}  |  Quality {data.overall_quality_score}%  |  "
            f"Regions {data.detection_count}  |  Confidence {data.defect_confidence_pct:.0f}%"
        ),
        ln=True,
    )
    pdf.ln(2)
    pdf.image(io.BytesIO(donut), x=12, w=85)
    pdf.image(io.BytesIO(bars), x=105, y=pdf.get_y() - 55, w=95)
    pdf.ln(58)

    heading("Cause Analysis")
    body(data.process_insight, 9)
    for cause in sorted(data.causes, key=lambda c: -c.score):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(27, 58, 95)
        pdf.cell(0, 5, _safe(f"{cause.name} - {cause.score}%"), ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(58, 70, 82)
        pdf.multi_cell(0, 4.5, _safe(cause.explanation))
        pdf.ln(1)

    pdf.set_y(-18)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(139, 150, 165)
    pdf.cell(0, 5, _safe(f"{data.footer}                                                              1"), ln=True)

    # Page 2
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(27, 58, 95)
    pdf.cell(0, 6, _safe(data.title), ln=True)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 9, "MAINTENANCE INSIGHTS", ln=True)
    pdf.ln(2)

    heading("Maintenance Items")
    for item in data.maintenance_items:
        body(f"- {item}", 9)

    heading("Diagnostic Findings")
    for item in data.diagnostic_findings:
        body(f"- {item}", 9)

    if data.similar_case_note:
        body(data.similar_case_note, 9)

    heading("Recommended Troubleshooting Sequence")
    for i, step in enumerate(data.action_plan, 1):
        body(f"{i}. {step}", 9)

    heading("Geometric Feature Extraction")
    if data.detections:
        for d in data.detections:
            area = f"{d.area_px:.0f}" if d.area_px is not None else "-"
            body(
                f"#{d.id} {d.defect_class} | conf {d.confidence_pct:.1f}% | area {area} px2",
                9,
            )
    else:
        body("No geometric detections recorded.", 9)

    heading("Engineer Notes")
    body(data.engineer_notes or "-", 9)

    pdf.set_y(-18)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(139, 150, 165)
    pdf.cell(0, 5, _safe(f"{data.footer}                                                              2"), ln=True)

    out = io.BytesIO()
    pdf.output(out)
    return out.getvalue()


def _render_pdf_reportlab(data: ReportData) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Image as RLImage,
        Table,
        TableStyle,
        PageBreak,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1B3A5F'),
    )
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1B3A5F'),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#3A4652'),
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#8B96A5'),
    )

    story = []
    # Page 1
    story.append(Paragraph(data.title.upper(), meta_style))
    story.append(Paragraph(data.subtitle, title_style))
    story.append(Paragraph(f"Session {data.session_id} | Generated {data.generated_at:%Y-%m-%d %H:%M UTC} | {data.brand}", meta_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("OUTPUT SUMMARY", h2_style))
    story.append(Paragraph(data.methodology_note, body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(data.executive_summary, body_style))
    story.append(Spacer(1, 8))

    kpi_data = [
        ["SEVERITY", "QUALITY / YIELD", "DEFECT REGIONS", "CONFIDENCE"],
        [data.severity, f"{data.overall_quality_score}%", str(data.detection_count), f"{data.defect_confidence_pct:.0f}%"]
    ]
    t = Table(kpi_data, colWidths=[130, 130, 130, 130])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F4F7FA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#8B96A5')),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#1B3A5F')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, 1), 13),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E4E9EF')),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#E4E9EF')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    donut_bytes = render_defect_donut(data)
    bars_bytes = render_analysis_bars(data)
    img_donut = RLImage(io.BytesIO(donut_bytes), width=230, height=140)
    img_bars = RLImage(io.BytesIO(bars_bytes), width=280, height=140)
    chart_table = Table([[img_donut, img_bars]], colWidths=[240, 290])
    chart_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(chart_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("CAUSE ANALYSIS", h2_style))
    story.append(Paragraph(data.process_insight, body_style))
    story.append(Spacer(1, 4))
    for c in sorted(data.causes, key=lambda x: -x.score):
        story.append(Paragraph(f"<b>{c.name}</b> ({c.score}%): {c.explanation}", body_style))
        story.append(Spacer(1, 2))

    # Page 2
    story.append(PageBreak())
    story.append(Paragraph(data.title.upper(), meta_style))
    story.append(Paragraph("MAINTENANCE INSIGHTS", title_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("MAINTENANCE ITEMS", h2_style))
    for item in data.maintenance_items:
        story.append(Paragraph(f"• {item}", body_style))
        story.append(Spacer(1, 2))

    story.append(Paragraph("DIAGNOSTIC FINDINGS", h2_style))
    for item in data.diagnostic_findings:
        story.append(Paragraph(f"• {item}", body_style))
        story.append(Spacer(1, 2))

    if data.similar_case_note:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<i>{data.similar_case_note}</i>", body_style))

    story.append(Paragraph("RECOMMENDED TROUBLESHOOTING SEQUENCE", h2_style))
    for i, step in enumerate(data.action_plan, 1):
        story.append(Paragraph(f"{i}. {step}", body_style))
        story.append(Spacer(1, 3))

    story.append(Paragraph("GEOMETRIC FEATURE EXTRACTION", h2_style))
    if data.detections:
        for d in data.detections:
            area_str = f"{d.area_px:.0f} px²" if d.area_px is not None else "—"
            story.append(Paragraph(f"Region #{d.id}: <b>{d.defect_class}</b> (Conf: {d.confidence_pct:.1f}%, Area: {area_str})", body_style))
    else:
        story.append(Paragraph("No geometric bounding boxes recorded (qualitative assessment).", body_style))

    story.append(Paragraph("ENGINEER NOTES", h2_style))
    story.append(Paragraph(data.engineer_notes or "—", body_style))

    doc.build(story)
    return buf.getvalue()
