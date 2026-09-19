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

    PAGE_W = 210  # A4 width mm
    MARGIN = 12
    USABLE_W = PAGE_W - 2 * MARGIN

    class ReportPDF(FPDF):
        def footer(self):
            # Formal footer
            self.set_y(-18)
            self.set_draw_color(228, 233, 239)
            self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
            self.ln(2)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(122, 139, 153)
            self.cell(USABLE_W / 2, 5, _safe(f"{data.brand} | Session {data.session_id}"), ln=False)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(27, 58, 95)
            self.cell(USABLE_W / 2, 5, f"Page {self.page_no()}", ln=True, align="R")

    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    def heading(title: str, size: int = 12) -> None:
        pdf.set_font("Helvetica", "B", size)
        pdf.set_text_color(27, 58, 95)
        pdf.cell(0, 8, _safe(title), ln=True)
        pdf.set_draw_color(27, 58, 95)
        # Thicker line for formal header
        pdf.set_line_width(0.5)
        pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
        pdf.set_line_width(0.2)
        pdf.ln(3)

    def body(text: str, size: int = 9) -> None:
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(74, 85, 104)
        pdf.multi_cell(0, 5, _safe(text))
        pdf.ln(1)
        
    def table_header(*cols):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(27, 58, 95)
        pdf.set_text_color(255, 255, 255)
        for w, text in cols:
            pdf.cell(w, 7, _safe(text), border=1, fill=True)
        pdf.ln()

    # ── Page 1 ──────────────────────────────────────────
    pdf.add_page()
    
    # Cover block
    pdf.set_fill_color(244, 247, 250)
    pdf.rect(MARGIN, MARGIN, USABLE_W, 25, style="F")
    pdf.set_fill_color(27, 58, 95)
    pdf.rect(MARGIN, MARGIN, 2, 25, style="F")
    
    pdf.set_xy(MARGIN + 5, MARGIN + 4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(74, 85, 104)
    pdf.cell(0, 5, _safe(data.title), ln=True)
    
    pdf.set_x(MARGIN + 5)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(27, 58, 95)
    pdf.cell(0, 8, _safe(data.subtitle), ln=True)
    
    pdf.set_x(MARGIN + 5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(113, 128, 150)
    pdf.cell(0, 5, _safe(f"GENERATED: {data.generated_at:%Y-%m-%d %H:%M UTC}"), ln=True)
    
    pdf.set_xy(MARGIN, MARGIN + 28)
    
    heading("Executive Overview")
    body(data.methodology_note, 9)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(27, 58, 95)
    pdf.multi_cell(0, 5, _safe(data.executive_summary))
    pdf.ln(2)

    # KPI Table
    kpi_w = USABLE_W / 4
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(113, 128, 150)
    y_before = pdf.get_y()
    pdf.cell(kpi_w, 4, "SEVERITY", align="C")
    pdf.cell(kpi_w, 4, "QUALITY / YIELD", align="C")
    pdf.cell(kpi_w, 4, "DEFECT REGIONS", align="C")
    pdf.cell(kpi_w, 4, "VISION CONF.", align="C", ln=True)
    
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(27, 58, 95)
    pdf.cell(kpi_w, 7, _safe(data.severity), align="C")
    pdf.cell(kpi_w, 7, f"{data.overall_quality_score}%", align="C")
    pdf.cell(kpi_w, 7, str(data.detection_count), align="C")
    pdf.cell(kpi_w, 7, f"{data.defect_confidence_pct:.0f}%", align="C", ln=True)
    
    # Draw simple borders for KPIs
    pdf.set_draw_color(226, 232, 240)
    pdf.line(MARGIN, y_before - 2, PAGE_W - MARGIN, y_before - 2)
    pdf.line(MARGIN, pdf.get_y() + 2, PAGE_W - MARGIN, pdf.get_y() + 2)
    pdf.ln(6)

    # Charts — restored to larger sizes. Aspect ratio for donut is 1.0, bars is ~0.77
    heading("Statistical Distribution")
    chart_y = pdf.get_y()
    chart_w_left = USABLE_W * 0.45
    chart_w_right = USABLE_W * 0.55
    chart_h_left = chart_w_left
    chart_h_right = chart_w_right * (3.4 / 4.4)
    chart_h = max(chart_h_left, chart_h_right)
    
    pdf.image(io.BytesIO(donut), x=MARGIN, y=chart_y, w=chart_w_left)
    pdf.image(io.BytesIO(bars), x=MARGIN + chart_w_left, y=chart_y, w=chart_w_right)
    pdf.set_y(chart_y + chart_h + 5)

    heading("Cause Analysis Details")
    body(data.process_insight, 9)
    
    table_header((USABLE_W * 0.4, "Defect / Cause"), (USABLE_W * 0.15, "Prob."), (USABLE_W * 0.45, "Engineering Reasoning"))
    for i, cause in enumerate(sorted(data.causes, key=lambda c: -c.score)):
        fill = i % 2 == 0
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(45, 55, 72)
        
        # Calculate heights for multi-cell
        pdf.set_font("Helvetica", "", 8)
        lines = len(pdf.multi_cell(USABLE_W * 0.45, 5, _safe(cause.explanation), split_only=True))
        h = max(6, lines * 5 + 2)
        
        y = pdf.get_y()
        # Check page break
        if y + h > 270:
            pdf.add_page()
            y = pdf.get_y()
            table_header((USABLE_W * 0.4, "Defect / Cause"), (USABLE_W * 0.15, "Prob."), (USABLE_W * 0.45, "Engineering Reasoning"))
            
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(27, 58, 95)
        pdf.cell(USABLE_W * 0.4, h, _safe(cause.name), border=1, fill=fill)
        pdf.cell(USABLE_W * 0.15, h, f"{cause.score}%", border=1, fill=fill, align="C")
        
        pdf.set_xy(MARGIN + USABLE_W * 0.55, y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(74, 85, 104)
        pdf.multi_cell(USABLE_W * 0.45, 5, _safe(cause.explanation), border=1, fill=fill)
        pdf.set_y(y + h)

    pdf.ln(4)

    # ── Page 2 ──────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(27, 58, 95)
    pdf.cell(0, 10, "MAINTENANCE INSIGHTS", ln=True)
    pdf.set_line_width(0.8)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(5)

    heading("Actionable Findings")
    table_header((USABLE_W * 0.5, "Maintenance Items"), (USABLE_W * 0.5, "Diagnostic Observations"))
    max_items = max(len(data.maintenance_items), len(data.diagnostic_findings))
    for i in range(max_items):
        m_item = data.maintenance_items[i] if i < len(data.maintenance_items) else ""
        d_item = data.diagnostic_findings[i] if i < len(data.diagnostic_findings) else ""
        
        fill = i % 2 == 0
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(74, 85, 104)
        
        lines_m = len(pdf.multi_cell(USABLE_W * 0.5, 5, _safe(f"- {m_item}" if m_item else ""), split_only=True))
        lines_d = len(pdf.multi_cell(USABLE_W * 0.5, 5, _safe(f"- {d_item}" if d_item else ""), split_only=True))
        h = max(6, max(lines_m, lines_d) * 5 + 2)
        
        y = pdf.get_y()
        pdf.multi_cell(USABLE_W * 0.5, 5, _safe(f"- {m_item}" if m_item else ""), border=1, fill=fill)
        pdf.set_xy(MARGIN + USABLE_W * 0.5, y)
        pdf.multi_cell(USABLE_W * 0.5, 5, _safe(f"- {d_item}" if d_item else ""), border=1, fill=fill)
        pdf.set_y(y + h)

    pdf.ln(4)
    if data.similar_case_note:
        pdf.set_fill_color(235, 248, 255)
        pdf.set_text_color(43, 108, 176)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, _safe(data.similar_case_note), fill=True, border=0)
        pdf.ln(4)

    heading("Recommended Troubleshooting Sequence")
    table_header((USABLE_W * 0.15, "Step"), (USABLE_W * 0.85, "Action Required"))
    for i, step in enumerate(data.action_plan, 1):
        fill = i % 2 == 1
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(27, 58, 95)
        
        lines = len(pdf.multi_cell(USABLE_W * 0.85, 5, _safe(step), split_only=True))
        h = max(6, lines * 5 + 2)
        y = pdf.get_y()
        
        if y + h > 270:
            pdf.add_page()
            y = pdf.get_y()
            table_header((USABLE_W * 0.15, "Step"), (USABLE_W * 0.85, "Action Required"))
            
        pdf.cell(USABLE_W * 0.15, h, f"Step {i}", border=1, fill=fill, align="C")
        pdf.set_xy(MARGIN + USABLE_W * 0.15, y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(74, 85, 104)
        pdf.multi_cell(USABLE_W * 0.85, 5, _safe(step), border=1, fill=fill)
        pdf.set_y(y + h)

    pdf.ln(4)

    heading("Geometric Feature Extraction")
    table_header((USABLE_W * 0.15, "Region ID"), (USABLE_W * 0.4, "Detected Class"), (USABLE_W * 0.2, "Confidence"), (USABLE_W * 0.25, "Area (px2)"))
    if data.detections:
        for i, d in enumerate(data.detections):
            fill = i % 2 == 0
            pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
            y = pdf.get_y()
            if y + 6 > 270:
                pdf.add_page()
                table_header((USABLE_W * 0.15, "Region ID"), (USABLE_W * 0.4, "Detected Class"), (USABLE_W * 0.2, "Confidence"), (USABLE_W * 0.25, "Area (px2)"))
            
            pdf.set_font("Courier", "B", 8)
            pdf.set_text_color(113, 128, 150)
            pdf.cell(USABLE_W * 0.15, 6, f"#{d.id}", border=1, fill=fill, align="C")
            
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(45, 55, 72)
            pdf.cell(USABLE_W * 0.4, 6, _safe(d.defect_class), border=1, fill=fill)
            
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(43, 108, 176)
            pdf.cell(USABLE_W * 0.2, 6, f"{d.confidence_pct:.1f}%", border=1, fill=fill, align="C")
            
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(74, 85, 104)
            area = f"{d.area_px:.0f}" if d.area_px is not None else "-"
            pdf.cell(USABLE_W * 0.25, 6, area, border=1, fill=fill, align="C")
            pdf.ln()
    else:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(160, 174, 192)
        pdf.cell(0, 8, "No geometric detections recorded for this session.", border=1, align="C", ln=True)

    pdf.ln(4)
    heading("Engineer Notes & Remarks")
    pdf.set_fill_color(248, 250, 252)
    pdf.set_text_color(74, 85, 104)
    pdf.set_font("Helvetica", "I", 9)
    # Just a simple dashed-looking box is hard in FPDF, we'll use a normal border
    pdf.multi_cell(0, 6, _safe(data.engineer_notes or "No manual notes were added by the engineer."), border=1, fill=True)

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
    # letter usable = 540pt (612 - 2*36); keep table within bounds
    t = Table(kpi_data, colWidths=[125, 125, 125, 125])
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
    img_donut = RLImage(io.BytesIO(donut_bytes), width=220, height=135)
    img_bars = RLImage(io.BytesIO(bars_bytes), width=260, height=135)
    chart_table = Table([[img_donut, img_bars]], colWidths=[250, 280])
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
