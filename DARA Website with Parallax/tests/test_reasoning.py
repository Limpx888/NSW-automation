from __future__ import annotations

from backend.reasoning import (
    Evidence,
    build_explanation_for_cause,
    compute_cause_scores,
    explain_diagnosis,
    get_cause_definitions,
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
