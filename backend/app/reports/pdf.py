"""PDF troubleshooting report (Bonus 4)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0B3D5C")
TEAL = colors.HexColor("#1F7A8C")
LIGHT = colors.HexColor("#F4F7FA")


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
        spaceAfter=6,
    )
    h = ParagraphStyle("HNSW", parent=styles["Heading2"], textColor=TEAL, fontSize=12, spaceBefore=10)
    body = ParagraphStyle("BodyNSW", parent=styles["BodyText"], leading=14, fontSize=10)
    small = ParagraphStyle("SmallNSW", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)

    defect = session.get("defect_class", "").replace("_", " ")
    material = session.get("material", "").replace("_", " ")
    pattern = session.get("pattern", "").replace("_", " ")
    vision = session.get("vision") or {}
    quality = session.get("quality") or {}
    similar = session.get("similar") or {}

    story = [
        Paragraph("AI Dispensing Defect Detective", title),
        Paragraph("NSW Automation — troubleshooting report (preliminary, not a process sign-off)", small),
        Spacer(1, 6),
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
        Paragraph("4. Ranked causes", h),
    ]

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
    story += [table, Paragraph("5. Recommended troubleshooting sequence", h)]
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
    story += [
        Paragraph("7. Engineer notes", h),
        Paragraph("Confirmed cause: ________________________________", body),
        Paragraph("Actions taken: _________________________________", body),
        Paragraph("Sign / date: ___________________________________", body),
        Spacer(1, 10),
        Paragraph(
            "Ranking is deterministic from NSW/AIM process rules. "
            "The language model, if used, only explains fired rules.",
            small,
        ),
    ]
    doc.build(story)
    data = buf.getvalue()
    if dest:
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(data)
    return data
