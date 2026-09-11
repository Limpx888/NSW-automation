from __future__ import annotations

from dataclasses import dataclass, field
from math import log2
from typing import Any, Iterable, Mapping, Sequence

from .evidence import Evidence
from .knowledge_base import ROOT_CAUSE_KB

DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "questionnaire": 1.0,
    "image_model": 1.15,
    "process_parameter": 1.1,
    "historical_case": 0.85,
    "engineering_rule": 1.0,
    "statistical_analysis": 0.9,
    "default": 1.0,
}


@dataclass
class CauseScoreResult:
    cause_id: str
    name: str
    raw_score: float
    supporting_total: float
    contradicting_total: float
    net_evidence: float
    normalized_likelihood: float
    calibrated_probability: None = None
    supporting_evidence: list[dict[str, Any]] = field(default_factory=list)
    contradicting_evidence: list[dict[str, Any]] = field(default_factory=list)
    insufficient_evidence: bool = False
    entropy: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "name": self.name,
            "raw_score": self.raw_score,
            "supporting_total": self.supporting_total,
            "contradicting_total": self.contradicting_total,
            "net_evidence": self.net_evidence,
            "normalized_likelihood": self.normalized_likelihood,
            "calibrated_probability": self.calibrated_probability,
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "insufficient_evidence": self.insufficient_evidence,
            "entropy": self.entropy,
        }


def normalize_likelihoods(raw_scores: Mapping[str, float]) -> dict[str, float]:
    positive_scores = {cause: max(0.0, float(score)) for cause, score in raw_scores.items()}
    total_positive = sum(positive_scores.values())
    if total_positive <= 0.0:
        return {cause: 0.0 for cause in raw_scores}

    normalized = {}
    for cause, score in raw_scores.items():
        normalized[cause] = max(0.0, float(score)) / total_positive
    return normalized


def compute_entropy(probabilities: Sequence[float]) -> float:
    total = sum(float(p) for p in probabilities if p > 0.0)
    if total <= 0.0:
        return 0.0
    normalized = [float(p) / total for p in probabilities if p > 0.0]
    entropy = 0.0
    for p in normalized:
        if p > 0.0:
            entropy -= p * log2(p)
    return entropy


def _source_weight(source: str, source_weights: Mapping[str, float] | None = None) -> float:
    weights = (source_weights or DEFAULT_SOURCE_WEIGHTS)
    return float(weights.get(source, weights.get("default", 1.0)))


def _cause_relationship_weight(cause_id: str, cause_relationship_weights: Mapping[str, float] | None = None) -> float:
    if not cause_relationship_weights:
        return 1.0
    return float(cause_relationship_weights.get(cause_id, 1.0))


def compute_cause_scores(
    evidence_items: Iterable[Evidence],
    cause_ids: Sequence[str] | None = None,
    source_weights: Mapping[str, float] | None = None,
    cause_relationship_weights: Mapping[str, float] | None = None,
) -> list[CauseScoreResult]:
    """Compute raw scores, supporting and contradicting evidence, and normalized likelihoods."""

    evidence_list = list(evidence_items)
    if cause_ids is None:
        inferred = sorted(
            {
                cause_id
                for item in evidence_list
                for cause_id in set(item.supporting_causes) | set(item.contradicting_causes)
            }
        )
    else:
        inferred = list(cause_ids)

    if not inferred:
        return []

    raw_scores: dict[str, float] = {cause_id: 0.0 for cause_id in inferred}
    support_breakdown: dict[str, list[dict[str, Any]]] = {cause_id: [] for cause_id in inferred}
    contradiction_breakdown: dict[str, list[dict[str, Any]]] = {cause_id: [] for cause_id in inferred}
    support_total: dict[str, float] = {cause_id: 0.0 for cause_id in inferred}
    contradiction_total: dict[str, float] = {cause_id: 0.0 for cause_id in inferred}

    for item in evidence_list:
        source_mult = _source_weight(item.source, source_weights)
        for cause_id, relationship_weight in item.supporting_causes.items():
            if cause_id not in raw_scores:
                raw_scores[cause_id] = 0.0
                support_breakdown[cause_id] = []
                contradiction_breakdown[cause_id] = []
                support_total[cause_id] = 0.0
                contradiction_total[cause_id] = 0.0
            contribution = (
                item.strength
                * item.reliability
                * source_mult
                * relationship_weight
                * _cause_relationship_weight(cause_id, cause_relationship_weights)
            )
            raw_scores[cause_id] += contribution
            support_total[cause_id] += contribution
            support_breakdown[cause_id].append(
                {
                    "evidence_id": item.id,
                    "feature_name": item.feature_name,
                    "value": item.value,
                    "source": item.source,
                    "reliability": item.reliability,
                    "strength": item.strength,
                    "relationship_weight": relationship_weight,
                    "contribution": contribution,
                    "explanation": item.explanation,
                }
            )

        for cause_id, relationship_weight in item.contradicting_causes.items():
            if cause_id not in raw_scores:
                raw_scores[cause_id] = 0.0
                support_breakdown[cause_id] = []
                contradiction_breakdown[cause_id] = []
                support_total[cause_id] = 0.0
                contradiction_total[cause_id] = 0.0
            contribution = -(
                item.strength
                * item.reliability
                * source_mult
                * relationship_weight
                * _cause_relationship_weight(cause_id, cause_relationship_weights)
            )
            raw_scores[cause_id] += contribution
            contradiction_total[cause_id] += abs(contribution)
            contradiction_breakdown[cause_id].append(
                {
                    "evidence_id": item.id,
                    "feature_name": item.feature_name,
                    "value": item.value,
                    "source": item.source,
                    "reliability": item.reliability,
                    "strength": item.strength,
                    "relationship_weight": relationship_weight,
                    "contribution": contribution,
                    "explanation": item.explanation,
                }
            )

    normalized = normalize_likelihoods(raw_scores)
    positive = [max(normalized.get(cause_id, 0.0), 0.0) for cause_id in inferred]
    entropy = compute_entropy(positive)

    results: list[CauseScoreResult] = []
    for cause_id in inferred:
        total_positive = max(0.0, raw_scores.get(cause_id, 0.0))
        if total_positive <= 0.0 and raw_scores.get(cause_id, 0.0) <= 0.0:
            insufficient = True
        else:
            insufficient = False

        cause_definition = ROOT_CAUSE_KB.get(cause_id)
        name = cause_definition.name if cause_definition is not None else cause_id.replace("_", " ").title()

        result = CauseScoreResult(
            cause_id=cause_id,
            name=name,
            raw_score=float(raw_scores.get(cause_id, 0.0)),
            supporting_total=float(support_total.get(cause_id, 0.0)),
            contradicting_total=float(contradiction_total.get(cause_id, 0.0)),
            net_evidence=float(raw_scores.get(cause_id, 0.0)),
            normalized_likelihood=float(normalized.get(cause_id, 0.0)),
            calibrated_probability=None,
            supporting_evidence=support_breakdown.get(cause_id, []),
            contradicting_evidence=contradiction_breakdown.get(cause_id, []),
            insufficient_evidence=insufficient,
            entropy=entropy,
        )
        results.append(result)

    if not any(result.normalized_likelihood > 0.0 for result in results):
        for result in results:
            result.insufficient_evidence = True
            result.entropy = 0.0

    results.sort(key=lambda r: r.raw_score, reverse=True)
    return results
