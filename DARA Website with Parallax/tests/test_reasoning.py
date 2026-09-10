from __future__ import annotations

from backend.reasoning import (
    Evidence,
    MultimodalEvidenceFusion,
    build_explanation_for_cause,
    compute_cause_scores,
    evaluate_uncertainty,
    explain_diagnosis,
    get_cause_definitions,
    QuestionOption,
    QuestionSelector,
    build_sample_diagnostic_trace,
)
from backend.reasoning.knowledge_base import ROOT_CAUSE_KB


def test_supporting_and_contradicting_evidence_are_scored() -> None:
    evidence = [
        Evidence(
            id="e1",
            feature_name="intermittent_volume_variation",
            value="intermittent",
            source="questionnaire",
            reliability=0.9,
            supporting_causes={"air_bubble": 0.8, "material_viscosity_change": 0.3},
            contradicting_causes={"nozzle_blockage": 0.2},
            strength=30.0,
            explanation="Intermittent variation matches trapped air.",
        ),
        Evidence(
            id="e2",
            feature_name="visible_bubble",
            value=True,
            source="image_model",
            reliability=0.8,
            supporting_causes={"air_bubble": 0.7},
            contradicting_causes={"equipment_problem": 0.4},
            strength=18.0,
            explanation="Visible bubble supports air entrapment.",
        ),
    ]

    results = compute_cause_scores(evidence)
    by_cause = {item.cause_id: item for item in results}

    assert by_cause["air_bubble"].raw_score > 0
    assert by_cause["nozzle_blockage"].raw_score < 0
    assert by_cause["air_bubble"].supporting_total > by_cause["air_bubble"].contradicting_total


def test_normalized_likelihood_handles_zero_and_insufficient_evidence() -> None:
    evidence = [
        Evidence(
            id="e1",
            feature_name="stable_pressure",
            value="stable",
            source="process_parameter",
            reliability=0.8,
            supporting_causes={"incorrect_parameter": 0.3},
            contradicting_causes={"air_bubble": 0.4},
            strength=12.0,
            explanation="Stable pressure reduces air-bubble plausibility.",
        )
    ]

    results = compute_cause_scores(evidence, cause_ids=["air_bubble", "incorrect_parameter", "equipment_problem"])
    by_cause = {item.cause_id: item for item in results}

    assert by_cause["air_bubble"].normalized_likelihood == 0.0
    assert by_cause["incorrect_parameter"].normalized_likelihood > 0.0
    assert by_cause["equipment_problem"].insufficient_evidence is True


def test_full_traceability_is_returned_for_each_cause() -> None:
    evidence = [
        Evidence(
            id="e3",
            feature_name="parameter_change",
            value="pressure_adjusted",
            source="questionnaire",
            reliability=0.95,
            supporting_causes={"incorrect_parameter": 1.0},
            contradicting_causes={"material_viscosity_change": 0.1},
            strength=27.0,
            explanation="A recent parameter edit directly supports recipe drift.",
        )
    ]

    results = compute_cause_scores(evidence, cause_ids=["incorrect_parameter", "material_viscosity_change"])
    incorrect = next(item for item in results if item.cause_id == "incorrect_parameter")

    assert incorrect.supporting_total > 0
    assert incorrect.contradicting_total >= 0
    assert incorrect.supporting_evidence[0]["feature_name"] == "parameter_change"
    assert incorrect.as_dict()["calibrated_probability"] is None


def test_configurable_weights_change_scores() -> None:
    evidence = [
        Evidence(
            id="e4",
            feature_name="recent_material_change",
            value="yes",
            source="historical_case",
            reliability=0.9,
            supporting_causes={"material_viscosity_change": 1.0},
            contradicting_causes={},
            strength=20.0,
            explanation="A recent material change supports viscosity-related drift.",
        )
    ]

    base = compute_cause_scores(evidence, cause_ids=["material_viscosity_change"], source_weights={"historical_case": 1.0})
    boosted = compute_cause_scores(
        evidence,
        cause_ids=["material_viscosity_change"],
        source_weights={"historical_case": 2.0},
    )

    assert boosted[0].raw_score > base[0].raw_score


def test_knowledge_base_contains_definition_metadata() -> None:
    kb = get_cause_definitions()
    assert "air_bubble" in kb
    assert kb["air_bubble"].name == "Air Bubble"
    assert "intermittent_volume_variation" in kb["air_bubble"].supporting_evidence
    assert ROOT_CAUSE_KB["nozzle_blockage"].recommended_actions


def test_explanation_uses_only_evidence_for_supporting_and_contradicting_details() -> None:
    evidence = [
        Evidence(
            id="e1",
            feature_name="intermittent_volume_variation",
            value="intermittent",
            source="questionnaire",
            reliability=0.9,
            supporting_causes={"air_bubble": 1.0},
            contradicting_causes={"air_bubble": 0.2, "nozzle_blockage": 0.3},
            strength=32.0,
            explanation="Intermittent variation is more consistent with trapped air than a continuously blocked nozzle.",
        ),
        Evidence(
            id="e2",
            feature_name="visible_bubble",
            value=True,
            source="image_model",
            reliability=0.8,
            supporting_causes={"air_bubble": 0.8},
            contradicting_causes={"equipment_problem": 0.2, "air_bubble": 0.15},
            strength=18.0,
            explanation="Visible bubble supports air entrapment.",
        ),
        Evidence(
            id="e3",
            feature_name="no_visible_bubble",
            value=False,
            source="image_model",
            reliability=0.7,
            supporting_causes={"nozzle_blockage": 0.4},
            contradicting_causes={"air_bubble": 0.5},
            strength=14.0,
            explanation="No visible bubble weakens the trapped-air explanation.",
        ),
    ]

    scores = compute_cause_scores(evidence, cause_ids=["air_bubble", "nozzle_blockage", "equipment_problem"])
    explanation = explain_diagnosis(scores)
    assert explanation is not None
    assert explanation.top_cause == "Air Bubble"
    assert {item["feature_name"] for item in explanation.supporting_evidence}.issuperset({"intermittent_volume_variation", "visible_bubble"})
    assert {item["feature_name"] for item in explanation.contradicting_evidence}.issuperset({"no_visible_bubble"})
    assert "Intermittent Volume Variation" in explanation.explanation
    assert explanation.recommended_action
    assert explanation.recommended_inspection


def test_build_explanation_for_cause_returns_traceable_contributions() -> None:
    evidence = [
        Evidence(
            id="e1",
            feature_name="pressure_adjusted",
            value="yes",
            source="questionnaire",
            reliability=0.95,
            supporting_causes={"incorrect_parameter": 1.0},
            contradicting_causes={"material_viscosity_change": 0.1},
            strength=25.0,
            explanation="A change in pressure settings matches recipe drift.",
        )
    ]

    scores = compute_cause_scores(evidence, cause_ids=["incorrect_parameter", "material_viscosity_change"])
    explanation = build_explanation_for_cause("incorrect_parameter", next(item for item in scores if item.cause_id == "incorrect_parameter"))

    assert explanation.top_cause == "Incorrect Parameter"
    assert explanation.likelihood > 0.0
    assert explanation.contribution_summary[0]["feature_name"] == "pressure_adjusted"
    assert explanation.explanation


def test_high_confidence_diagnosis_is_not_uncertain() -> None:
    evidence = [
        Evidence(
            id="e1",
            feature_name="intermittent_volume_variation",
            value="intermittent",
            source="questionnaire",
            reliability=0.9,
            supporting_causes={"air_bubble": 1.0},
            contradicting_causes={"nozzle_blockage": 0.2},
            strength=30.0,
            explanation="Intermittent variation supports trapped air.",
        ),
        Evidence(
            id="e2",
            feature_name="visible_bubble",
            value=True,
            source="image_model",
            reliability=0.85,
            supporting_causes={"air_bubble": 0.9},
            contradicting_causes={"equipment_problem": 0.1},
            strength=22.0,
            explanation="Visible bubble strengthens the air-bubble case.",
        ),
    ]

    scores = compute_cause_scores(evidence, cause_ids=["air_bubble", "nozzle_blockage", "equipment_problem"])
    uncertainty = evaluate_uncertainty(scores, next_best_question="Confirm the material was recently changed?")

    assert uncertainty.is_uncertain is False
    assert uncertainty.top_cause == "Air Bubble"
    assert uncertainty.next_best_question is None


def test_close_competing_causes_are_marked_uncertain() -> None:
    evidence = [
        Evidence(
            id="e1",
            feature_name="under_dispense",
            value="yes",
            source="questionnaire",
            reliability=0.9,
            supporting_causes={"nozzle_blockage": 1.0, "incorrect_parameter": 0.9},
            contradicting_causes={},
            strength=20.0,
            explanation="Under-dispense supports both blockage and settings drift.",
        ),
    ]

    scores = compute_cause_scores(evidence, cause_ids=["nozzle_blockage", "incorrect_parameter"])
    uncertainty = evaluate_uncertainty(scores, config={"min_top1_likelihood": 0.5, "min_top2_margin": 0.25, "max_entropy": 1.0})

    assert uncertainty.is_uncertain is True
    assert uncertainty.top_cause in {"Nozzle Blockage", "Incorrect Parameter"}
    assert uncertainty.next_best_question


def test_completely_ambiguous_evidence_is_uncertain() -> None:
    evidence = [
        Evidence(
            id="e1",
            feature_name="defect_observed",
            value="generic",
            source="questionnaire",
            reliability=0.5,
            supporting_causes={"air_bubble": 0.5, "incorrect_parameter": 0.5, "material_viscosity_change": 0.5},
            contradicting_causes={},
            strength=5.0,
            explanation="Generic defect signal is not discriminative.",
        )
    ]

    scores = compute_cause_scores(evidence, cause_ids=["air_bubble", "incorrect_parameter", "material_viscosity_change"])
    uncertainty = evaluate_uncertainty(scores)

    assert uncertainty.is_uncertain is True
    assert uncertainty.entropy > 0.0
    assert "Insufficient evidence" in uncertainty.explanation


def test_no_evidence_returns_uncertain_state() -> None:
    uncertainty = evaluate_uncertainty([])

    assert uncertainty.is_uncertain is True
    assert uncertainty.top_cause is None
    assert uncertainty.next_best_question
    assert "No evidence" in uncertainty.explanation


def test_multimodal_fusion_preserves_provenance_and_does_not_double_count_correlated_evidence() -> None:
    engine = MultimodalEvidenceFusion()
    result = engine.diagnose(
        questionnaire=[
            Evidence(
                id="q-pattern",
                feature_name="intermittent_volume_variation",
                value="intermittent",
                source="questionnaire",
                reliability=0.9,
                supporting_causes={"air_bubble": 1.0},
                strength=30.0,
                correlation_group="flow_pattern",
            )
        ],
        vision=[
            Evidence(
                id="v-pattern",
                feature_name="irregular_dot_shape",
                value=True,
                source="vision",
                reliability=0.8,
                supporting_causes={"air_bubble": 1.0},
                strength=20.0,
                correlation_group="flow_pattern",
            )
        ],
        cause_ids=["air_bubble", "nozzle_blockage"],
    )

    assert {item["source"] for item in result.trace.evidence} == {"questionnaire", "vision"}
    assert result.trace.evidence[0]["correlation_group"] == "flow_pattern"
    assert len(result.trace.raw_scores) == 2
    assert any(item.get("suppressed") for item in result.trace.contributions)
    assert result.score_results[0].raw_score == 27.0


def test_multimodal_fusion_explicitly_records_conflicting_sources() -> None:
    engine = MultimodalEvidenceFusion()
    result = engine.diagnose(
        questionnaire=[
            Evidence(
                id="q-bubble",
                feature_name="visible_bubble",
                value=True,
                source="questionnaire",
                supporting_causes={"air_bubble": 1.0},
                strength=10.0,
                correlation_group="bubble_observation",
            )
        ],
        vision=[
            Evidence(
                id="v-no-bubble",
                feature_name="no_visible_bubble",
                value=True,
                source="vision",
                contradicting_causes={"air_bubble": 1.0},
                strength=9.0,
                correlation_group="bubble_observation",
            )
        ],
        cause_ids=["air_bubble", "nozzle_blockage"],
    )

    assert result.trace.conflicts[0]["cause_id"] == "air_bubble"
    assert result.trace.conflicts[0]["supporting_evidence_ids"] == ["q-bubble"]
    assert result.trace.conflicts[0]["contradicting_evidence_ids"] == ["v-no-bubble"]


def test_high_uncertainty_stops_before_diagnosis_and_requests_next_question() -> None:
    engine = MultimodalEvidenceFusion()
    result = engine.diagnose(
        questionnaire=[
            Evidence(
                id="q-generic",
                feature_name="generic_defect_signal",
                value=True,
                source="questionnaire",
                supporting_causes={"air_bubble": 1.0, "nozzle_blockage": 1.0},
                strength=5.0,
            )
        ],
        cause_ids=["air_bubble", "nozzle_blockage"],
        questions=[QuestionOption(id="q-frequency", text="Is the defect intermittent or continuous?", feature="frequency")],
    )

    assert result.uncertainty_result.is_uncertain is True
    assert result.trace.final_diagnosis is None
    assert result.trace.explanation is None
    assert result.trace.uncertainty["next_best_question"] == "Is the defect intermittent or continuous?"
    assert result.trace.recommended_action == []


def test_sample_diagnostic_trace_contains_all_pipeline_stages() -> None:
    trace = build_sample_diagnostic_trace()

    for key in (
        "inputs",
        "evidence",
        "contributions",
        "raw_scores",
        "normalized_likelihoods",
        "uncertainty",
        "final_diagnosis",
        "explanation",
        "recommended_action",
    ):
        assert key in trace
    assert trace["evidence"]
    assert trace["raw_scores"]
    assert trace["normalized_likelihoods"]


def test_question_selector_uses_expected_information_gain_when_distributions_exist() -> None:
    scores = [
        {
            "cause_id": "air_bubble",
            "name": "Air Bubble",
            "normalized_likelihood": 0.55,
            "raw_score": 40.0,
        },
        {
            "cause_id": "nozzle_blockage",
            "name": "Nozzle Blockage",
            "normalized_likelihood": 0.45,
            "raw_score": 35.0,
        },
    ]

    question_a = QuestionOption(
        id="q1",
        text="Was the defect intermittent or continuous?",
        feature="intermittent_volume_variation",
        answer_distributions={
            "intermittent": {"air_bubble": 0.85, "nozzle_blockage": 0.15},
            "continuous": {"air_bubble": 0.2, "nozzle_blockage": 0.8},
        },
    )
    question_b = QuestionOption(
        id="q2",
        text="Was there a recent material change?",
        feature="recent_material_change",
        answer_distributions={
            "yes": {"air_bubble": 0.5, "nozzle_blockage": 0.5},
            "no": {"air_bubble": 0.5, "nozzle_blockage": 0.5},
        },
    )

    selector = QuestionSelector()
    selected = selector.select_question(scores, [question_a, question_b])

    assert selected is not None
    assert selected.id == "q1"


def test_question_selector_falls_back_to_weighted_information_heuristic_without_distributions() -> None:
    scores = [
        {"cause_id": "air_bubble", "name": "Air Bubble", "normalized_likelihood": 0.38, "raw_score": 25.0},
        {"cause_id": "nozzle_blockage", "name": "Nozzle Blockage", "normalized_likelihood": 0.31, "raw_score": 22.0},
        {"cause_id": "incorrect_parameter", "name": "Incorrect Parameter", "normalized_likelihood": 0.31, "raw_score": 21.0},
    ]

    selector = QuestionSelector()
    selected = selector.select_question(
        scores,
        [
            QuestionOption(id="q1", text="Was the defect intermittent?", feature="intermittent_volume_variation"),
            QuestionOption(id="q2", text="Was a nozzle recently replaced?", feature="nozzle_blockage"),
        ],
    )

    assert selected is not None
    assert selected.id in {"q1", "q2"}
    assert selected.text
