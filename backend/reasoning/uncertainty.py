from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .scoring import CauseScoreResult, compute_entropy

DEFAULT_UNCERTAINTY_CONFIG = {
    "min_top1_likelihood": 0.65,
    "min_top2_margin": 0.15,
    "max_entropy": 1.0,
    "min_evidence_count": 2,
}


@dataclass
class UncertaintyResult:
    is_uncertain: bool
    top_cause: str | None
    top_likelihood: float
    top2_margin: float
    entropy: float
    explanation: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    next_best_question: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_uncertain": self.is_uncertain,
            "top_cause": self.top_cause,
            "top_likelihood": self.top_likelihood,
            "top2_margin": self.top2_margin,
            "entropy": self.entropy,
            "explanation": self.explanation,
            "candidates": self.candidates,
            "next_best_question": self.next_best_question,
        }


def _candidate_scores(score_results: list[CauseScoreResult]) -> list[dict[str, Any]]:
    ordered = sorted(score_results, key=lambda item: item.normalized_likelihood, reverse=True)
    return [
        {
            "cause_id": item.cause_id,
            "name": item.name,
            "likelihood": float(item.normalized_likelihood),
            "raw_score": float(item.raw_score),
        }
        for item in ordered
    ]


def evaluate_uncertainty(
    score_results: list[CauseScoreResult],
    config: dict[str, float] | None = None,
    next_best_question: str | None = None,
) -> UncertaintyResult:
    """Deterministic uncertainty layer using top-1 likelihood, margin, and entropy."""
    settings = {**DEFAULT_UNCERTAINTY_CONFIG, **(config or {})}

    if not score_results:
        return UncertaintyResult(
            is_uncertain=True,
            top_cause=None,
            top_likelihood=0.0,
            top2_margin=0.0,
            entropy=0.0,
            explanation="No evidence was supplied, so a diagnosis would be speculative.",
            candidates=[],
            next_best_question=next_best_question or "Collect an image or answer a few process questions before diagnosing.",
        )

    ordered = sorted(score_results, key=lambda item: item.normalized_likelihood, reverse=True)
    top = ordered[0]
    top_likelihood = float(top.normalized_likelihood)
    second = ordered[1] if len(ordered) > 1 else top
    top2_margin = max(0.0, top_likelihood - float(second.normalized_likelihood))

    probabilities = [max(0.0, float(item.normalized_likelihood)) for item in ordered]
    entropy = compute_entropy(probabilities)

    has_enough_evidence = len(ordered) >= int(settings.get("min_evidence_count", 2))
    is_uncertain = (
        top_likelihood < float(settings.get("min_top1_likelihood", 0.65))
        or top2_margin < float(settings.get("min_top2_margin", 0.15))
        or entropy > float(settings.get("max_entropy", 1.0))
        or not has_enough_evidence
    )

    if is_uncertain:
        explanation_bits = [
            f"Top cause likelihood is {top_likelihood:.2f}.",
            f"Top-1 vs top-2 margin is {top2_margin:.2f}.",
            f"Entropy is {entropy:.2f}.",
        ]
        explanation = " ".join(explanation_bits) + " Insufficient evidence for a reliable diagnosis."
        return UncertaintyResult(
            is_uncertain=True,
            top_cause=top.name,
            top_likelihood=top_likelihood,
            top2_margin=top2_margin,
            entropy=entropy,
            explanation=explanation,
            candidates=_candidate_scores(score_results),
            next_best_question=next_best_question or "Ask about whether the defect is continuous or intermittent, and whether there was a recent material or nozzle change.",
        )

    return UncertaintyResult(
        is_uncertain=False,
        top_cause=top.name,
        top_likelihood=top_likelihood,
        top2_margin=top2_margin,
        entropy=entropy,
        explanation="Evidence is sufficient for a provisional diagnosis within the configured confidence thresholds.",
        candidates=_candidate_scores(score_results),
        next_best_question=None,
    )
