from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .knowledge_base import ROOT_CAUSE_KB
from .scoring import CauseScoreResult


@dataclass
class ExplanationResult:
    top_cause: str
    likelihood: float
    supporting_evidence: list[dict[str, Any]]
    contradicting_evidence: list[dict[str, Any]]
    contribution_summary: list[dict[str, Any]]
    explanation: str
    recommended_inspection: list[str]
    recommended_action: list[str]
    raw_score: float
    normalized_likelihood: float
    insufficient_evidence: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "top_cause": self.top_cause,
            "likelihood": self.likelihood,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "contribution_summary": self.contribution_summary,
            "explanation": self.explanation,
            "recommended_inspection": self.recommended_inspection,
            "recommended_action": self.recommended_action,
            "raw_score": self.raw_score,
            "normalized_likelihood": self.normalized_likelihood,
            "insufficient_evidence": self.insufficient_evidence,
        }


def _format_number(value: float) -> str:
    return f"{value:.1f}"


def _pretty_feature_name(raw_name: str) -> str:
    text = str(raw_name or "unknown").replace("_", " ")
    return " ".join(part.capitalize() for part in text.split())


def _summarize_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summarized = [
        {
            "feature_name": item.get("feature_name", "unknown"),
            "label": _pretty_feature_name(item.get("feature_name", "unknown")),
            "value": item.get("value"),
            "source": item.get("source", "unknown"),
            "reliability": float(item.get("reliability", 0.0)),
            "strength": float(item.get("strength", 0.0)),
            "contribution": float(item.get("contribution", 0.0)),
            "explanation": item.get("explanation", ""),
        }
        for item in items
    ]
    return sorted(summarized, key=lambda item: abs(float(item["contribution"])), reverse=True)


def build_explanation_for_cause(
    cause_id: str,
    score_result: CauseScoreResult,
    top_cause_id: str | None = None,
) -> ExplanationResult:
    definition = ROOT_CAUSE_KB.get(cause_id)
    support_items = _summarize_evidence(score_result.supporting_evidence)
    contradiction_items = _summarize_evidence(score_result.contradicting_evidence)
    likelihood = max(0.0, float(score_result.normalized_likelihood))
    raw_score = float(score_result.raw_score)

    if definition is None:
        recommended_inspection: list[str] = []
        recommended_action: list[str] = []
    else:
        recommended_inspection = list(definition.recommended_inspections)
        recommended_action = list(definition.recommended_actions)

    support_text = "; ".join(
        f"{item['label']} (+{_format_number(item['contribution'])})" for item in support_items
    ) or "No supporting evidence recorded."
    contradiction_text = "; ".join(
        f"{item['label']} ({_format_number(item['contribution'])})" for item in contradiction_items
    ) or "No contradicting evidence recorded."

    if not support_items and not contradiction_items:
        explanation = f"{definition.name if definition else cause_id.replace('_', ' ').title()} has no direct evidence recorded yet; the diagnosis remains provisional."
    else:
        explanation = (
            f"{definition.name if definition else cause_id.replace('_', ' ').title()} is currently ranked highest because "
            f"the evidence indicates {support_text}. "
            f"The strongest competing factors are {contradiction_text}."
        )

    if top_cause_id is None or cause_id != top_cause_id:
        explanation = explanation.replace("currently ranked highest", "is ranked as a candidate cause")

    contribution_summary = [
        {
            "feature_name": item["feature_name"],
            "label": item["label"],
            "contribution": item["contribution"],
            "direction": "supporting" if item["contribution"] >= 0 else "contradicting",
            "explanation": item["explanation"],
        }
        for item in support_items + contradiction_items
    ]

    return ExplanationResult(
        top_cause=definition.name if definition is not None else cause_id.replace("_", " ").title(),
        likelihood=likelihood,
        supporting_evidence=support_items,
        contradicting_evidence=contradiction_items,
        contribution_summary=contribution_summary,
        explanation=explanation,
        recommended_inspection=recommended_inspection,
        recommended_action=recommended_action,
        raw_score=raw_score,
        normalized_likelihood=likelihood,
        insufficient_evidence=score_result.insufficient_evidence,
    )


def explain_diagnosis(score_results: list[CauseScoreResult]) -> ExplanationResult | None:
    if not score_results:
        return None

    ranked = sorted(score_results, key=lambda item: item.raw_score, reverse=True)
    top = ranked[0]
    return build_explanation_for_cause(top.cause_id, top, top_cause_id=top.cause_id)
