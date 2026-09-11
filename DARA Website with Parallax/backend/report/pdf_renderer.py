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
        return _render_pdf_fallback(data)


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
