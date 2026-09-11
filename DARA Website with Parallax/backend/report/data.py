"""Assemble ReportData from saved scan cases (SQLite history)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from backend import history
from backend.report.schemas import (
    Cause,
    ChartSlice,
    DetectionRow,
    QualitySubScore,
    ReportData,
)

ANSWER_LABELS = {
    "frequency": {
        "first_time": "first occurrence",
        "intermittent": "intermittent / occasional",
        "continuous": "continuous / every board",
        "after_change": "started after a recent change",
    },
    "recent_change": {
        "nozzle": "nozzle change",
        "material": "material / paste change",
        "parameters": "parameter change",
        "none": "no recent change reported",
        "unknown": "change status unknown",
    },
}


def _score_to_stars(score: float | int | None, invert: bool = False) -> int:
    if score is None:
        return 0
    value = float(score)
    if invert:
        value = 100 - value
    if value >= 90:
        return 5
    if value >= 75:
        return 4
    if value >= 60:
        return 3
    if value >= 40:
        return 2
    if value > 0:
        return 1
    return 0


def _as_pct(confidence: float | None) -> float:
    if confidence is None:
        return 0.0
    c = float(confidence)
    if c <= 1.0:
        c *= 100
    return max(0.0, min(100.0, c))


def _format_answers(answers: dict) -> str:
    if not answers:
        return "Operator follow-up answers were not recorded."
    parts: list[str] = []
    freq = answers.get("frequency")
    change = answers.get("recent_change")
    if freq:
        parts.append(
            f"frequency is {ANSWER_LABELS.get('frequency', {}).get(freq, freq)}"
        )
    if change:
        parts.append(
            f"recent change: {ANSWER_LABELS.get('recent_change', {}).get(change, change)}"
        )
    return "; ".join(parts) if parts else "Operator follow-up answers were not recorded."


def _box_area(det: dict) -> float | None:
    box = det.get("box") or {}
    if "width" in box and "height" in box:
        try:
            return float(box["width"]) * float(box["height"])
        except (TypeError, ValueError):
            return None
    if all(k in box for k in ("x1", "y1", "x2", "y2")):
        try:
            return abs(float(box["x2"]) - float(box["x1"])) * abs(
                float(box["y2"]) - float(box["y1"])
            )
        except (TypeError, ValueError):
            return None
    return None


def _detection_rows(case: dict) -> list[DetectionRow]:
    rows: list[DetectionRow] = []
    for i, det in enumerate(case.get("detections") or [], start=1):
        if not isinstance(det, dict):
            continue
        label = (
            det.get("display_label")
            or det.get("label")
            or case.get("defect_label")
            or "Unknown"
        )
        rows.append(
            DetectionRow(
                id=det.get("id", i),
                defect_class=str(label).replace("_", " "),
                confidence_pct=_as_pct(det.get("confidence")),
                area_px=_box_area(det),
            )
        )
    if not rows and (case.get("detection_count") or 0) > 0:
        rows.append(
            DetectionRow(
                id=1,
                defect_class=str(
                    case.get("defect_label") or case.get("defect_class") or "Defect"
                ),
                confidence_pct=_as_pct(case.get("confidence")),
                area_px=None,
            )
        )
    return rows


def _defect_distribution(rows: list[DetectionRow], case: dict) -> list[ChartSlice]:
    if rows:
        counts = Counter(r.defect_class for r in rows)
        return [ChartSlice(label=k, value=float(v)) for k, v in counts.most_common()]
    label = str(case.get("defect_label") or case.get("defect_class") or "Pass")
    count = float(case.get("detection_count") or 0)
    if count <= 0:
        return [ChartSlice(label="Pass / No Defect", value=1)]
    return [ChartSlice(label=label, value=count)]


def _build_problem_description(case: dict) -> str:
    label = case.get("defect_label") or case.get("defect_class") or "Unknown defect"
    filename = case.get("filename") or "uploaded image"
    detections = case.get("detection_count") or 0
    answers = case.get("answers") or {}
    return (
        f"Solder-paste inspection of '{filename}' flagged {label} "
        f"with {detections} detection(s). Operator context: {_format_answers(answers)}."
    )


def _generate_analysis_summary(
    case: dict,
    causes: list[Cause],
    rows: list[DetectionRow],
) -> tuple[str, str, str, list[str], list[str]]:
    """Return executive_summary, process_insight, deep_analysis, findings, maintenance."""
    total = len(rows) or int(case.get("detection_count") or 0)
    answers = case.get("answers") or {}
    freq = str(answers.get("frequency") or "")
    top = causes[0] if causes else None
    second = causes[1] if len(causes) > 1 else None
    conf_pct = _as_pct(case.get("confidence"))
    quality = case.get("quality_score")
    label = case.get("defect_label") or case.get("defect_class") or "defect"

    if total == 0:
        summary = (
            "Process operating within target specification limits. "
            "No actionable defects detected on this inspection frame."
        )
        insight = "Continue routine monitoring; no immediate maintenance action required."
        findings = [
            "Vision scan returned zero defect regions.",
            f"Overall quality score: {quality if quality is not None else 'n/a'}/100.",
            "Yield estimate for this frame is 100%.",
        ]
        maintenance = [
            "No corrective action required for this frame.",
            "Retain image in history for trend comparison on the next run.",
        ]
        deep = summary
        return summary, insight, deep, findings, maintenance

    severity = "HIGH" if total > 3 or conf_pct >= 90 else "MODERATE"
    if "continuous" in freq:
        pattern = "systematic process drift"
    elif "intermittent" in freq or "first" in freq:
        pattern = "intermittent fluid instability"
    else:
        pattern = "process variation requiring operator confirmation"

    top_name = top.name if top else "Unknown"
    top_score = top.score if top else 0

    summary = (
        f"INSPECTION ANALYSIS: Severity Assessment: {severity} "
        f"({total} defect region(s) identified). "
        f"Failure Mode: Primary issue mapped to '{top_name}' ({top_score}% likelihood). "
        f"Process Insight: Observed behavior indicates {pattern}. "
        f"Immediate nozzle tip inspection and syringe pressure calibration are recommended "
        f"before resuming the production run."
    )

    insight = (
        f"Observed behavior indicates {pattern}. Weighted inference combined YOLO confidence "
        f"({conf_pct:.0f}%) with shop-floor Q&A ({_format_answers(answers)}) to rank root causes."
    )

    findings = [
        f"Feature & area extraction identified {total} defect region(s) for {label}.",
        f"Vision confidence {conf_pct:.0f}% with overall quality score "
        f"{quality if quality is not None else 'n/a'}/100.",
    ]
    if top:
        gap = (top.score - second.score) if second else top.score
        if gap >= 15:
            findings.append(
                f"Cause ranking is decisive: {top.name} leads at {top.score}%"
                + (f", {gap} points ahead of {second.name}." if second else ".")
            )
        else:
            findings.append(
                f"Cause ranking is contested between {top.name} ({top.score}%)"
                + (f" and {second.name} ({second.score}%)." if second else ".")
            )
        findings.append(f"Primary reasoning: {top.explanation}")

    shape = case.get("shape_consistency")
    size = case.get("size_consistency")
    position = case.get("dispensing_position")
    risk = case.get("defect_risk")
    metric_bits = []
    if shape is not None:
        metric_bits.append(f"shape {float(shape):.0f}")
    if size is not None:
        metric_bits.append(f"size {float(size):.0f}")
    if position is not None:
        metric_bits.append(f"position {float(position):.0f}")
    if risk is not None:
        metric_bits.append(f"defect risk {float(risk):.0f}")
    if metric_bits:
        findings.append("Quality breakdown: " + "; ".join(metric_bits) + ".")

    maintenance = [
        f"Inspect / verify '{top_name}' as the leading root cause before broader teardown.",
        "Check syringe for trapped air and purge until a solid bead appears.",
        "Inspect the dispensing nozzle for partial blockage or misalignment.",
        "Verify pressure, on-time, and Z-gap against the last known-good recipe.",
    ]
    if answers.get("recent_change") == "nozzle":
        maintenance.insert(
            1, "Recent nozzle change reported - prioritize tip ID and seating checks."
        )
    if answers.get("recent_change") == "material":
        maintenance.insert(
            1, "Recent material change reported - verify paste warm-up and viscosity."
        )

    deep = " ".join(
        [
            f"Vision confidence for {label} is {conf_pct:.0f}% with an overall dispensing "
            f"quality score of {quality if quality is not None else 'n/a'}/100.",
            findings[2] if len(findings) > 2 else "",
            insight,
        ]
    ).strip()

    return summary, insight, deep, findings, maintenance


def _build_similar_note(case: dict) -> str | None:
    defect_class = case.get("defect_class")
    if not defect_class:
        return None
    total, top_cause_name, top_cause_count = history.count_similar_cases(
        defect_class,
        exclude_session_id=case.get("session_id"),
    )
    if total <= 0:
        return None
    if top_cause_name and top_cause_count:
        return (
            f"Similar {case.get('defect_label') or defect_class} cases occurred "
            f"{total} time(s) previously. In {top_cause_count} of those, "
            f"the leading ranked cause was {top_cause_name}."
        )
    return (
        f"Similar {case.get('defect_label') or defect_class} cases occurred "
        f"{total} time(s) previously in DARA history."
    )


def build_report_data(session_id: str) -> ReportData:
    case = history.get_case(session_id)
    if not case:
        raise LookupError(f"Session not found: {session_id}")

    raw_causes = case.get("causes") or []
    causes: list[Cause] = []
    for c in raw_causes:
        if not isinstance(c, dict):
            continue
        score = int(round(float(c.get("likelihood_pct") or c.get("score") or 0)))
        score = max(0, min(100, score))
        causes.append(
            Cause(
                name=str(c.get("name") or "Unknown"),
                score=score,
                explanation=str(c.get("reasoning") or c.get("explanation") or ""),
            )
        )
    causes.sort(key=lambda x: -x.score)

    action_plan: list[str] = []
    for step in case.get("action_plan") or []:
        if isinstance(step, dict):
            title = step.get("title") or f"Step {step.get('step', '')}"
            detail = step.get("detail") or ""
            action_plan.append(f"{title}: {detail}".strip(": ").strip())
        else:
            action_plan.append(str(step))

    rows = _detection_rows(case)
    detection_count = len(rows) or int(case.get("detection_count") or 0)
    conf_pct = _as_pct(case.get("confidence"))
    overall = int(case.get("quality_score") or 0)
    severity = "LOW" if detection_count == 0 else ("HIGH" if detection_count > 3 or conf_pct >= 90 else "MODERATE")
    yield_pct = max(0.0, min(100.0, float(overall)))

    quality_subscores = [
        QualitySubScore(
            label="Shape Consistency",
            stars=_score_to_stars(case.get("shape_consistency")),
            value=float(case["shape_consistency"])
            if case.get("shape_consistency") is not None
            else None,
        ),
        QualitySubScore(
            label="Size Consistency",
            stars=_score_to_stars(case.get("size_consistency")),
            value=float(case["size_consistency"])
            if case.get("size_consistency") is not None
            else None,
        ),
        QualitySubScore(
            label="Dispensing Position",
            stars=_score_to_stars(case.get("dispensing_position")),
            value=float(case["dispensing_position"])
            if case.get("dispensing_position") is not None
            else None,
        ),
        QualitySubScore(
            label="Defect Risk (inverted)",
            stars=_score_to_stars(case.get("defect_risk"), invert=True),
            value=float(case["defect_risk"]) if case.get("defect_risk") is not None else None,
        ),
    ]

    analysis_statistics = [
        ChartSlice(label=c.name, value=float(c.score)) for c in causes[:5]
    ]
    if not analysis_statistics:
        analysis_statistics = [
            ChartSlice(label=s.label, value=float(s.value or s.stars * 20))
            for s in quality_subscores
        ]

    summary, insight, deep, findings, maintenance = _generate_analysis_summary(
        case, causes, rows
    )

    answers = case.get("answers") or {}
    notes_parts = []
    if answers:
        notes_parts.append(f"Operator answers - {_format_answers(answers)}.")
    notes_parts.append(f"Case status: {case.get('status') or 'analyzed'}.")
    if case.get("filename"):
        notes_parts.append(f"Source file: {case['filename']}.")

    return ReportData(
        session_id=session_id,
        generated_at=datetime.now(timezone.utc),
        problem_description=_build_problem_description(case),
        defect=str(case.get("defect_label") or case.get("defect_class") or "Unknown"),
        defect_confidence_stars=_score_to_stars(conf_pct),
        defect_confidence_pct=conf_pct,
        severity=severity,
        yield_pct=yield_pct,
        detection_count=detection_count,
        causes=causes,
        quality_subscores=quality_subscores,
        overall_quality_score=overall,
        defect_distribution=_defect_distribution(rows, case),
        analysis_statistics=analysis_statistics,
        detections=rows,
        executive_summary=summary,
        process_insight=insight,
        diagnostic_findings=findings,
        maintenance_items=maintenance,
        action_plan=action_plan
        or [
            "Re-run cause analysis after answering both shop-floor follow-ups.",
            "Inspect the top-ranked cause from the diagnosis table.",
            "Capture corrective-action notes once the fix is confirmed.",
        ],
        engineer_notes=" ".join(notes_parts),
        similar_case_note=_build_similar_note(case),
        deep_analysis=deep,
    )
