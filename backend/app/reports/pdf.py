import os
import socket
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0B3D5C")
TEAL = colors.HexColor("#1F7A8C")
LIGHT = colors.HexColor("#F4F7FA")


def get_local_ip() -> str:
    """Detect LAN IP address of this machine for mobile device access."""
    env_ip = os.getenv("HOST_IP") or os.getenv("FRONTEND_HOST")
    if env_ip:
        return env_ip
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_feedback_url(session_id: str) -> str:
    """Generate mobile-accessible feedback URL."""
    base = os.getenv("FRONTEND_URL")
    if not base:
        ip = get_local_ip()
        port = os.getenv("FRONTEND_PORT", "5173")
        base = f"http://{ip}:{port}"
    return f"{base.rstrip('/')}/quick-feedback?session_id={session_id}"


def build_qr_image(url: str) -> Image:
    """Build a sharp QR code image for ReportLab PDF."""
    qr = qrcode.QRCode(box_size=3, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=26 * mm, height=26 * mm)


def build_pdf(session: dict, dest: Path | None = None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Dispensing Troubleshooting Report",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleNSW",
        parent=styles["Title"],
        textColor=NAVY,
        fontSize=16,
        spaceAfter=4,
        alignment=0,
    )
    h = ParagraphStyle("HNSW", parent=styles["Heading2"], textColor=TEAL, fontSize=12, spaceBefore=10)
    body = ParagraphStyle("BodyNSW", parent=styles["BodyText"], leading=14, fontSize=10)
    small = ParagraphStyle("SmallNSW", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)
    qr_caption = ParagraphStyle("QRCaption", parent=small, fontSize=7, leading=9, alignment=TA_CENTER, textColor=TEAL)

    session_id = session.get("session_id") or "live-demo"
    feedback_url = get_feedback_url(session_id)
    print(f"[PDF Generator] Embedded Mobile Feedback QR Code -> {feedback_url}")

    # Header with Title and QR Code
    header_left = [
        Paragraph("AI Dispensing Defect Detective", title),
        Paragraph("NSW Automation · Interactive Maintenance Sheet", small),
        Paragraph(f"Session ID: <b>{session_id[:16]}...</b> &nbsp;|&nbsp; Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", small),
    ]
    header_right = [
        build_qr_image(feedback_url),
        Spacer(1, 2),
        Paragraph("<b>Scan on Mobile</b><br/>Confirm Resolution", qr_caption),
    ]

    header_table = Table(
        [[header_left, header_right]],
        colWidths=[134 * mm, 40 * mm],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )

    defect = session.get("defect_class", "").replace("_", " ")
    material = session.get("material", "").replace("_", " ")
    pattern = session.get("pattern", "").replace("_", " ")
    vision = session.get("vision") or {}
    quality = session.get("quality") or {}
    similar = session.get("similar") or {}

    story = [
        header_table,
        Spacer(1, 8),
        Paragraph("1. Problem description", h),
        Paragraph(
            session.get("problem_description")
            or f"Operator reported a {pattern} dispense issue in {material}.",
            body,
        ),
        Paragraph("2. Defect detected", h),
        Paragraph(
            f"<b>{session.get('pattern_specific_name', defect)}</b> "
            f"(class: {defect}). Vision confidence: "
            f"{(vision.get('confidence') or session.get('vision_confidence') or 0):.0%} "
            f"via {vision.get('method', 'n/a')}.",
            body,
        ),
        Paragraph(
            f"Material: <b>{material}</b> &nbsp;&nbsp; Pattern: <b>{pattern}</b> "
            f"&nbsp;&nbsp; Quality score: <b>{quality.get('overall_quality_score', 'n/a')}</b>/100",
            body,
        ),
        Paragraph("3. AI analysis (WHY)", h),
        Paragraph((session.get("reasoning_chain") or session.get("explanation") or "").replace("\n", "<br/>"), body),
        Paragraph(similar.get("summary", ""), body),
    ]

    rheology = session.get("rheology")
    if rheology:
        story.append(Paragraph("3b. Physical Rheology & Thermal Drift Offset", h))
        rheo_text = (
            f"<b>Ambient Temperature:</b> {rheology.get('ambient_temp_c', 23.0)}°C "
            f"(ΔT: {rheology.get('delta_t_c', 0.0):+0.1f}°C vs 23°C baseline) &nbsp;|&nbsp; "
            f"<b>Viscosity Drift:</b> <b>{rheology.get('viscosity_drift_pct', 0.0):+0.1f}%</b> "
            f"({str(rheology.get('risk_level', 'OPTIMAL')).replace('_', ' ')})<br/>"
            f"<b>Compensatory Action:</b> {rheology.get('alert_message', '')}<br/>"
            f"<b>Recommended Machine Offsets:</b> "
            f"Dispense Pressure: <b>{rheology.get('pressure_offset_mpa', 0.0):+0.04f} MPa ({rheology.get('pressure_offset_pct', 0.0):+0.1f}%)</b> &nbsp;|&nbsp; "
            f"Tip Heater: <b>{rheology.get('heater_offset_c', 0.0):+0.1f}°C</b>"
        )
        if rheology.get("thixotropic_alert"):
            rheo_text += f"<br/><b>Thixotropic Alert:</b> {rheology['thixotropic_alert']}"
        story.append(Paragraph(rheo_text, body))
        story.append(Spacer(1, 4))

    story.append(Paragraph("4. Ranked causes", h))

    rows = [["#", "Cause", "Likelihood", "Family"]]
    for i, cause in enumerate(session.get("ranked_causes") or [], start=1):
        rows.append(
            [
                str(i),
                cause.get("name", cause.get("id")),
                f"{cause.get('likelihood_pct', 0):.1f}%",
                cause.get("family_label", cause.get("category", "")),
            ]
        )
    table = Table(rows, colWidths=[15 * mm, 95 * mm, 30 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C5D0DA")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)

    # Section 4b: Differential Diagnosis & Elimination Audit Trail
    elimination = session.get("elimination_pathway")
    if not elimination and session.get("elimination_pathway_json"):
        import json
        try:
            elimination = json.loads(session["elimination_pathway_json"])
        except Exception:
            elimination = None

    if elimination and isinstance(elimination, list) and len(elimination) > 0:
        story.append(Paragraph("4b. Differential Diagnosis & Counter-Test Audit Trail", h))
        diff_rows = [["#", "Hypothesis", "Action Test Executed", "Result", "Status"]]
        for idx, step in enumerate(elimination, start=1):
            diff_rows.append([
                str(idx),
                str(step.get("target_cause_name") or step.get("target_cause_id", "N/A")),
                str(step.get("test_title", "N/A")),
                str(step.get("feedback", "N/A")).title(),
                str(step.get("status", "N/A")),
            ])
        diff_table = Table(diff_rows, colWidths=[12 * mm, 48 * mm, 65 * mm, 25 * mm, 25 * mm])
        diff_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C5D0DA")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(diff_table)

    story.append(Paragraph("5. Recommended troubleshooting sequence", h))
    for step in session.get("action_plan") or []:
        story.append(
            Paragraph(
                f"<b>Step {step.get('step')}.</b> {step.get('instruction')}",
                body,
            )
        )
    if session.get("downstream_warnings"):
        story.append(Paragraph("6. Downstream risk", h))
        story.append(
            Paragraph(
                "If unfixed, this pattern can lead to: "
                + ", ".join(session["downstream_warnings"])
                + ".",
                body,
            )
        )

    confirmed_str = session.get("confirmed_cause") or "________________________________"
    if confirmed_str != "________________________________":
        confirmed_str = confirmed_str.replace("_", " ").title()

    story += [
        Paragraph("7. Engineer notes & resolution sign-off", h),
        Paragraph(f"Confirmed root cause: <b>{confirmed_str}</b>", body),
        Paragraph("Actions taken: _________________________________", body),
        Paragraph("Sign / date: ___________________________________", body),
        Spacer(1, 10),
        Paragraph(
            "Ranking is deterministic from NSW/AIM process rules. "
            "Differential counter-testing confirms physical root cause.",
            small,
        ),
    ]
    doc.build(story)
    data = buf.getvalue()
    if dest:
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(data)
    return data
