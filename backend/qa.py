"""Gemini-backed Q&A over a solder-paste analysis result."""

from __future__ import annotations

from typing import Any

from backend.config import get_settings
from backend.vision import DISPLAY_LABELS


SYSTEM_PROMPT = """You are DARA, an industrial solder-paste / micro-dispensing quality assistant
for DARA. Answer the operator's question using the vision analysis context.
Be concise, technical, and actionable. If the context is insufficient, say what extra
info (photo angle, powder type, nozzle ID, pressure/time) would help. Do not invent
detections that were not provided.
"""


def _fallback_answer(question: str, analysis: dict[str, Any] | None) -> str:
    q = (question or "").strip().lower()
    if not analysis:
        return (
            "Upload and analyze a dispense photo first so I can ground the answer in detections. "
            "Once results are ready, ask about defect type, likely causes, or next checks."
        )

    label = analysis.get("defect_label") or DISPLAY_LABELS.get(
        analysis.get("defect_class", ""), "UNKNOWN"
    )
    conf = float(analysis.get("confidence") or 0)
    count = analysis.get("detection_count", len(analysis.get("detections") or []))
    quality = analysis.get("quality") or {}

    if any(k in q for k in ("score", "quality", "rating")):
        return (
            f"Overall quality is {quality.get('overall_quality_score', 'n/a')}/100 for "
            f"{label} ({conf:.0%} confidence, {count} detection(s)). "
            f"Shape {quality.get('shape_consistency')}/5, size {quality.get('size_consistency')}/5, "
            f"position {quality.get('dispensing_position')}/5, defect risk {quality.get('defect_risk')}/5. "
            "Add GEMINI_API_KEY to .env for richer root-cause coaching."
        )

    if any(k in q for k in ("cause", "why", "fix", "root")):
        tips = {
            "too_much": "Lower pressure/time, verify Z-gap, and confirm syringe is not over-pressurized.",
            "inconsistent_size": "Look for trapped air in the syringe, unstable pressure, or intermittent clog.",
            "missing_dot": "Inspect tip for full clog, empty syringe, or Z height too high to wet the pad.",
            "spreading": "Paste may be warm/low-viscosity, Z too low, or dwell time too long.",
            "air_bubble": "Degas material, store tip-down, and review retract/break-off settings.",
            "insufficient_volume": "Review dispense time, pressure, and material flow.",
            "missing_deposit": "Check for empty barrel, clogged nozzle, or extreme Z-height.",
            "excess_volume": "Lower pressure, reduce dispense time, or check for material warming.",
        }
        defect = analysis.get("defect_class", "no_defect_detected")
        return f"Primary finding: {label}. {tips.get(defect, 'Review process parameters against DARA guidance.')}"

    return (
        f"Vision flagged {label} at {conf:.0%} with {count} box(es). "
        "Ask about causes, quality score, or recommended checks. "
        "Set GEMINI_API_KEY in .env to enable full Gemini answers."
    )


def _build_context(analysis: dict[str, Any] | None) -> str:
    if not analysis:
        return "No analysis context yet."
    dets = analysis.get("detections") or []
    quality = analysis.get("quality") or {}
    lines = [
        f"Primary defect: {analysis.get('defect_label')} ({analysis.get('defect_class')})",
        f"Confidence: {analysis.get('confidence')}",
        f"Detections: {len(dets)}",
        f"Quality score: {quality.get('overall_quality_score')}/100",
        f"Shape: {quality.get('shape_consistency')}/5",
        f"Size: {quality.get('size_consistency')}/5",
        f"Position: {quality.get('dispensing_position')}/5",
        f"Defect risk: {quality.get('defect_risk')}/5",
        "Boxes:",
    ]
    for d in dets[:12]:
        box = d.get("box") or {}
        lines.append(
            f"- {d.get('display_label')} conf={d.get('confidence')} "
            f"xyxy=({box.get('x1')},{box.get('y1')},{box.get('x2')},{box.get('y2')})"
        )
    return "\n".join(lines)


def answer_question(
    question: str,
    analysis: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    api_key = (settings.gemini_api_key or "").strip()
    fallback = _fallback_answer(question, analysis)

    if not api_key:
        return {
            "answer": fallback,
            "provider": "fallback",
            "model": None,
            "gemini_configured": False,
        }

    try:
        import google.generativeai as genai
    except ImportError:
        return {
            "answer": fallback + " (Install google-generativeai to enable Gemini.)",
            "provider": "fallback",
            "model": None,
            "gemini_configured": True,
        }

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=SYSTEM_PROMPT,
        )
        parts: list[str] = [
            "Analysis context:\n" + _build_context(analysis),
            "",
        ]
        for turn in (history or [])[-8:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            parts.append(f"{role.upper()}: {content}")
        parts.append(f"USER: {question}")
        parts.append("ASSISTANT:")

        response = model.generate_content("\n".join(parts))
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            text = fallback
        return {
            "answer": text,
            "provider": "gemini",
            "model": settings.gemini_model,
            "gemini_configured": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "answer": f"{fallback}\n\n(Gemini error: {exc})",
            "provider": "fallback",
            "model": settings.gemini_model,
            "gemini_configured": True,
            "error": str(exc),
        }
