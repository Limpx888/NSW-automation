from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .evidence import Evidence
from .explainability import ExplanationResult, explain_diagnosis
from .question_selector import QuestionOption, QuestionSelector
from .scoring import CauseScoreResult, compute_cause_scores
from .uncertainty import UncertaintyResult, evaluate_uncertainty


@dataclass
class DiagnosticTrace:
    inputs: dict[str, Any]
    evidence: list[dict[str, Any]]
    contributions: list[dict[str, Any]]
    raw_scores: list[dict[str, Any]]
    normalized_likelihoods: list[dict[str, Any]]
    uncertainty: dict[str, Any]
    final_diagnosis: dict[str, Any] | None
    explanation: dict[str, Any] | None
    recommended_action: list[str]
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "inputs": self.inputs,
            "evidence": self.evidence,
            "contributions": self.contributions,
            "raw_scores": self.raw_scores,
            "normalized_likelihoods": self.normalized_likelihoods,
            "uncertainty": self.uncertainty,
            "final_diagnosis": self.final_diagnosis,
            "explanation": self.explanation,
            "recommended_action": list(self.recommended_action),
            "conflicts": list(self.conflicts),
        }


@dataclass
class DiagnosticResult:
    trace: DiagnosticTrace
    score_results: list[CauseScoreResult]
    uncertainty_result: UncertaintyResult
    explanation_result: ExplanationResult | None
    selected_question: QuestionOption | None

    def as_dict(self) -> dict[str, Any]:
        return self.trace.as_dict()


class MultimodalEvidenceFusion:
    """Deterministic multimodal pipeline from source observations to action."""

    def __init__(self, question_selector: QuestionSelector | None = None) -> None:
        self.question_selector = question_selector or QuestionSelector()

    def diagnose(
        self,
        *,
        questionnaire: Iterable[Evidence | Mapping[str, Any]] = (),
        vision: Iterable[Evidence | Mapping[str, Any]] = (),
        process_parameters: Iterable[Evidence | Mapping[str, Any]] = (),
        historical_cases: Iterable[Evidence | Mapping[str, Any]] = (),
        cause_ids: Sequence[str] | None = None,
        questions: Iterable[QuestionOption] = (),
        inputs: Mapping[str, Any] | None = None,
    ) -> DiagnosticResult:
        source_groups = {
            "questionnaire": questionnaire,
            "vision": vision,
            "process_parameters": process_parameters,
            "historical_cases": historical_cases,
        }
        extracted = [
            self._coerce_evidence(item, source_name)
            for source_name, items in source_groups.items()
            for item in items
        ]
        fused, suppressed, conflicts = self._fuse_evidence(extracted)
        score_results = compute_cause_scores(fused, cause_ids=cause_ids)
        question = self.question_selector.select_question(score_results_as_mappings(score_results), questions)
        question_text = question.text if question is not None else None
        uncertainty = evaluate_uncertainty(score_results, next_best_question=question_text)
        explanation = explain_diagnosis(score_results) if not uncertainty.is_uncertain else None
        final_diagnosis = None
        recommended_action: list[str] = []
        if not uncertainty.is_uncertain and explanation is not None:
            final_diagnosis = {
                "cause_id": score_results[0].cause_id,
                "name": explanation.top_cause,
                "likelihood": explanation.normalized_likelihood,
            }
            recommended_action = list(explanation.recommended_action)

        trace = DiagnosticTrace(
            inputs=dict(inputs or {}),
            evidence=[item.as_dict() for item in extracted],
            contributions=[
                *[item for result in score_results for item in result.supporting_evidence],
                *[item for result in score_results for item in result.contradicting_evidence],
                *suppressed,
            ],
            raw_scores=[{"cause_id": result.cause_id, "name": result.name, "raw_score": result.raw_score} for result in score_results],
            normalized_likelihoods=[
                {"cause_id": result.cause_id, "name": result.name, "likelihood": result.normalized_likelihood}
                for result in score_results
            ],
            uncertainty=uncertainty.as_dict(),
            final_diagnosis=final_diagnosis,
            explanation=explanation.as_dict() if explanation is not None else None,
            recommended_action=recommended_action,
            conflicts=conflicts,
        )
        return DiagnosticResult(trace, score_results, uncertainty, explanation, question)

    @staticmethod
    def _coerce_evidence(item: Evidence | Mapping[str, Any], source_name: str) -> Evidence:
        if isinstance(item, Evidence):
            if item.source == source_name:
                return item
            return Evidence(**{**item.as_dict(), "source": source_name})
        data = dict(item)
        data.setdefault("source", source_name)
        data.setdefault("id", f"{source_name}:{data.get('feature_name', 'unknown')}")
        data.setdefault("provenance", {"source_collection": source_name})
        data.setdefault("correlation_group", data.get("feature_name"))
        return Evidence(**data)

    @staticmethod
    def _fuse_evidence(evidence: Sequence[Evidence]) -> tuple[list[Evidence], list[dict[str, Any]], list[dict[str, Any]]]:
        groups: dict[str, list[Evidence]] = {}
        for item in evidence:
            groups.setdefault(str(item.correlation_group), []).append(item)

        fused: list[Evidence] = []
        suppressed: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        for group_id, items in groups.items():
            causes = set().union(*(set(item.supporting_causes) | set(item.contradicting_causes) for item in items))
            for cause_id in causes:
                supports = [item for item in items if item.supporting_for(cause_id) > 0]
                contradicts = [item for item in items if item.contradicting_for(cause_id) > 0]
                if supports and contradicts:
                    conflicts.append({
                        "correlation_group": group_id,
                        "cause_id": cause_id,
                        "supporting_evidence_ids": [item.id for item in supports],
                        "contradicting_evidence_ids": [item.id for item in contradicts],
                    })
                candidates = supports + contradicts
                if not candidates:
                    continue
                selected = max(candidates, key=lambda item: item.strength * item.reliability * max(item.supporting_for(cause_id), item.contradicting_for(cause_id)))
                if selected not in fused:
                    fused.append(selected)
                for duplicate in candidates:
                    if duplicate is not selected:
                        suppressed.append({
                            **duplicate.as_dict(),
                            "suppressed": True,
                            "suppressed_by": selected.id,
                            "reason": "correlated evidence was not scored twice",
                        })
        return fused, suppressed, conflicts


def score_results_as_mappings(results: Sequence[CauseScoreResult]) -> list[dict[str, Any]]:
    return [
        {
            "cause_id": result.cause_id,
            "name": result.name,
            "normalized_likelihood": result.normalized_likelihood,
            "raw_score": result.raw_score,
        }
        for result in results
    ]


def build_sample_diagnostic_trace() -> dict[str, Any]:
    engine = MultimodalEvidenceFusion()
    result = engine.diagnose(
        inputs={"case_id": "sample-001", "defect_class": "inconsistent_size"},
        questionnaire=[Evidence(
            id="q-frequency",
            feature_name="intermittent_volume_variation",
            value="intermittent",
            source="questionnaire",
            reliability=0.9,
            supporting_causes={"air_bubble": 1.0},
            strength=30.0,
            correlation_group="flow_pattern",
            explanation="Operator reports intermittent volume variation.",
        )],
        vision=[Evidence(
            id="v-bubble",
            feature_name="visible_bubble",
            value=True,
            source="vision",
            reliability=0.85,
            supporting_causes={"air_bubble": 0.9},
            strength=22.0,
            correlation_group="bubble_observation",
            explanation="Vision model detected bubble-like morphology.",
        )],
        process_parameters=[Evidence(
            id="p-pressure",
            feature_name="pressure_stable",
            value=True,
            source="process_parameters",
            reliability=0.9,
            contradicting_causes={"incorrect_parameter": 0.8},
            strength=16.0,
            correlation_group="pressure_state",
            explanation="Recorded pressure stayed within the process window.",
        )],
        cause_ids=["air_bubble", "nozzle_blockage", "incorrect_parameter"],
    )
    return result.as_dict()