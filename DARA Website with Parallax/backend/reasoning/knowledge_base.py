from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CauseDefinition:
    cause_id: str
    name: str
    description: str = ""
    symptoms: tuple[str, ...] = ()
    supporting_evidence: tuple[str, ...] = ()
    contradicting_evidence: tuple[str, ...] = ()
    related_defects: tuple[str, ...] = ()
    recommended_inspections: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    verification_steps: tuple[str, ...] = ()
    severity: str = "medium"
    parameter_constraints: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "name": self.name,
            "description": self.description,
            "symptoms": list(self.symptoms),
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "related_defects": list(self.related_defects),
            "recommended_inspections": list(self.recommended_inspections),
            "recommended_actions": list(self.recommended_actions),
            "verification_steps": list(self.verification_steps),
            "severity": self.severity,
            "parameter_constraints": dict(self.parameter_constraints),
        }


ROOT_CAUSE_KB: dict[str, CauseDefinition] = {
    "air_bubble": CauseDefinition(
        cause_id="air_bubble",
        name="Air Bubble",
        description="Entrapped air disrupts the dispense path and creates intermittent or irregular deposits.",
        symptoms=("intermittent_volume_variation", "irregular_dot_shape", "visible_bubbles"),
        supporting_evidence=("intermittent_volume_variation", "irregular_dot_shape", "recent_material_change"),
        contradicting_evidence=("continuous_under_dispensing", "stable_pressure"),
        related_defects=("inconsistent_size", "missing_dot", "air_bubble"),
        recommended_inspections=("inspect_material_path", "check_cartridge_connection", "purge_dispensing_line"),
        recommended_actions=("purge_line", "inspect_cartridge", "verify_tip_seating"),
        verification_steps=("run_test_dispensing", "inspect_deposit_consistency"),
        severity="medium",
    ),
    "nozzle_blockage": CauseDefinition(
        cause_id="nozzle_blockage",
        name="Nozzle Blockage",
        description="Reduced orifice flow causes under-dispense, skipped deposits, or intermittent blockage.",
        symptoms=("continuous_under_dispensing", "missing_dot", "intermittent_blockage"),
        supporting_evidence=("continuous_under_dispensing", "missing_dot", "after_hours_degradation"),
        contradicting_evidence=("stable_pressure", "sudden_volume_increase"),
        related_defects=("too_little", "missing_dot"),
        recommended_inspections=("inspect_nozzle_tip", "verify_nozzle_id", "clean_or_replace_tip"),
        recommended_actions=("clean_tip", "replace_tip", "verify_material_filter"),
        verification_steps=("run_test_dispense", "check_tip_drift"),
        severity="high",
    ),
    "material_viscosity_change": CauseDefinition(
        cause_id="material_viscosity_change",
        name="Material Viscosity Change",
        description="Flow behavior shifts with temperature, age, or material condition and changes deposit volume or spread.",
        symptoms=("spread_and_bleed", "volume_drift", "temperature_sensitive_behaviour"),
        supporting_evidence=("temperature_shift", "material_age_change", "spread_pattern"),
        contradicting_evidence=("stable_material_temperature", "consistent_short_term_volume"),
        related_defects=("too_much", "spreading", "inconsistent_size"),
        recommended_inspections=("check_material_temperature", "verify_storage_conditions", "inspect_material_age"),
        recommended_actions=("verify_room_temperature", "mix_material", "check_expiry"),
        verification_steps=("compare_with_last_good_batch", "review_temperature_log"),
        severity="medium",
    ),
    "incorrect_parameter": CauseDefinition(
        cause_id="incorrect_parameter",
        name="Incorrect Parameter",
        description="Recipe or machine settings are outside the expected process window, causing drift or over/under dispense.",
        symptoms=("recipe_drift", "pressure_setting_issue", "z_gap_issue"),
        supporting_evidence=("parameter_change", "recipe_mismatch", "pressure_or_time_shift"),
        contradicting_evidence=("stable_recipes", "consistent_volume_over_time"),
        related_defects=("too_little", "too_much", "spreading"),
        recommended_inspections=("compare_to_last_good_recipe", "verify_pressure_settings", "check_z_gap"),
        recommended_actions=("reset_recipe", "verify_pressure", "recalibrate_z_gap"),
        verification_steps=("run_short_test", "compare_to_reference_deposit"),
        severity="high",
    ),
    "equipment_problem": CauseDefinition(
        cause_id="equipment_problem",
        name="Equipment Problem",
        description="Mechanical or control-system wear or drift is causing unstable or unreliable dispensing.",
        symptoms=("drifting_shot_weight", "equipment_noise", "intermittent_failure"),
        supporting_evidence=("drifting_pressure", "maintenance_gap", "worn_seals"),
        contradicting_evidence=("recent_repair", "fresh_equipment"),
        related_defects=("inconsistent_size", "missing_dot", "too_much"),
        recommended_inspections=("inspect_valves", "check_regulator", "verify_seals"),
        recommended_actions=("service_equipment", "calibrate_regulator", "inspect_seals"),
        verification_steps=("perform_shot_weight_test", "review_machine_logs"),
        severity="high",
    ),
}


def get_cause_definitions() -> dict[str, CauseDefinition]:
    return dict(ROOT_CAUSE_KB)


def get_related_causes_for_defect(defect_type: str) -> list[str]:
    matches = [
        cause_id
        for cause_id, definition in ROOT_CAUSE_KB.items()
        if defect_type in definition.related_defects
    ]
    return matches
