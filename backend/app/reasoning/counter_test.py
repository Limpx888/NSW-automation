"""Hypothesis-Testing & Counter-Test Loop (Differential Diagnosis Engine).

Provides low-cost physical verification actions and Bayesian/penalty re-scoring
to iteratively eliminate or confirm root causes.
"""

from __future__ import annotations

import copy
from typing import Any

# Catalog of rapid, low-cost verification tests mapped to root causes
VERIFICATION_ACTIONS: dict[str, dict[str, Any]] = {
    "air_trapped_syringe": {
        "action_id": "purge_air_test",
        "target_cause": "air_trapped_syringe",
        "title": "2-Second Air Purge & Tip Bubble Check",
        "cost_badge": "⚡ 30s · Zero Cost",
        "instruction": "Raise dispensing head into air, execute a 2-second continuous purge shot onto a lint-free wipe, and check for air bubble sputtering or voids.",
        "expected_resolved": "Dispense bead flows solid and uniform with no sputtering or popping sounds.",
        "expected_unresolved": "Flow remains intermittent or under-dispensed despite purge.",
        "penalty_factor": 0.15,
        "escalate_factor": 1.35,
    },
    "nozzle_partial_clog": {
        "action_id": "solvent_wipe_flush_test",
        "target_cause": "nozzle_partial_clog",
        "title": "IPA Tip Wipe & High-Pressure Flush",
        "cost_badge": "⏱️ 1 min · Low Cost",
        "instruction": "Wipe nozzle tip with an IPA-dampened lint-free swab. Increase pressure by +20% for a 1-second purge shot into purge cup to clear particle crust.",
        "expected_resolved": "Crust clears and full dot/line volume is restored.",
        "expected_unresolved": "Nozzle orifice still restricted or stream deviates sideways.",
        "penalty_factor": 0.20,
        "escalate_factor": 1.30,
    },
    "powder_nozzle_mismatch": {
        "action_id": "five_x_gauge_check",
        "target_cause": "powder_nozzle_mismatch",
        "title": "5× Rule Gauge Verification",
        "cost_badge": "🔍 1 min · Zero Cost",
        "instruction": "Cross-reference installed nozzle gauge against solder paste powder type: NSW requires Nozzle ID >= 5x largest powder particle (e.g. Type 6 >= 80 µm, Type 5 >= 125 µm).",
        "expected_resolved": "Nozzle ID was verified compliant, or swapping to >= 5x gauge immediately cured clogging.",
        "expected_unresolved": "Nozzle ID is confirmed compliant with 5x rule, yet under-dispensing persists.",
        "penalty_factor": 0.10,
        "escalate_factor": 1.25,
    },
    "pressure_time_low": {
        "action_id": "pressure_bump_test",
        "target_cause": "pressure_time_low",
        "title": "+10% Pressure Step Test",
        "cost_badge": "⚡ 45s · Minimal Cost",
        "instruction": "Increase dispense pressure by +10% on the pneumatic controller and run 5 test dots on scrap board.",
        "expected_resolved": "Dot diameter and volume return to nominal target size.",
        "expected_unresolved": "Volume remains undersized or restricted regardless of pressure increase.",
        "penalty_factor": 0.20,
        "escalate_factor": 1.30,
    },
    "pressure_time_high": {
        "action_id": "pressure_drop_test",
        "target_cause": "pressure_time_high",
        "title": "-15% Pressure Step Test",
        "cost_badge": "⚡ 45s · Minimal Cost",
        "instruction": "Decrease dispense pressure by -15% and observe if overflow/slump disappears on 5 test dots.",
        "expected_resolved": "Dot diameter conforms to specification without overflow.",
        "expected_unresolved": "Spreading/overflow persists (likely viscosity or surface tension issue).",
        "penalty_factor": 0.20,
        "escalate_factor": 1.30,
    },
    "viscosity_temp_humidity": {
        "action_id": "thermal_thaw_check",
        "target_cause": "viscosity_temp_humidity",
        "title": "Thaw Time & Syringe Temperature Audit",
        "cost_badge": "🌡️ 1 min · Zero Cost",
        "instruction": "Inspect syringe thaw tag. Confirm paste reached 22-25°C room equilibrium (minimum 2 hours from cold storage without artificial heating). Check booth thermometer.",
        "expected_resolved": "Temperature was out of spec; restoring temperature stabilizes flow.",
        "expected_unresolved": "Material is confirmed at stable 23°C nominal operating temperature.",
        "penalty_factor": 0.15,
        "escalate_factor": 1.25,
    },
    "flux_metal_separation": {
        "action_id": "lead_purge_consistency_test",
        "target_cause": "flux_metal_separation",
        "title": "0.5cc Syringe Lead Purge",
        "cost_badge": "⏱️ 1 min · Low Cost",
        "instruction": "Purge the first 0.5cc of paste from the syringe tip into a waste container to discharge unmixed flux supernatant.",
        "expected_resolved": "Homogeneous gray solder bead appears and dispense weight stabilizes.",
        "expected_unresolved": "Paste remains dry/crusty or liquid separation continues throughout barrel.",
        "penalty_factor": 0.20,
        "escalate_factor": 1.25,
    },
    "z_gap_wrong": {
        "action_id": "feeler_gauge_standoff_check",
        "target_cause": "z_gap_wrong",
        "title": "Standoff Gap Feeler Gauge Check",
        "cost_badge": "📏 2 min · Medium Cost",
        "instruction": "Use a precision feeler gauge or laser height sensor to verify nozzle-to-substrate standoff height (nominal: 50% of dispense dot diameter).",
        "expected_resolved": "Re-calibrating Z-datum restores wet-out and dot shape.",
        "expected_unresolved": "Z-height is verified accurate within +/- 10 µm, yet defect persists.",
        "penalty_factor": 0.15,
        "escalate_factor": 1.25,
    },
    "premature_uv_cure": {
        "action_id": "light_shielding_check",
        "target_cause": "premature_uv_cure",
        "title": "UV Shielding & Tip Gelling Inspection",
        "cost_badge": "💡 1 min · Low Cost",
        "instruction": "Inspect fluid line for amber/black UV shielding and inspect tip for polymerized skin using magnifying glass.",
        "expected_resolved": "Gelled tip replaced and shielding restored; normal flow resumes.",
        "expected_unresolved": "Tip is completely clean and fluid is free of polymerization.",
        "penalty_factor": 0.15,
        "escalate_factor": 1.30,
    },
    "filler_settling": {
        "action_id": "syringe_roller_homogenization",
        "target_cause": "filler_settling",
        "title": "Syringe Roller Re-homogenization",
        "cost_badge": "🔄 2 min · Medium Cost",
        "instruction": "Remove syringe and place on horizontal roller at 5-10 RPM for 3 minutes to resuspend settled silver or ceramic filler particles.",
        "expected_resolved": "Uniform filler density restored; consistent dispense resumes.",
        "expected_unresolved": "Fluid remains inconsistent despite roller agitation.",
        "penalty_factor": 0.20,
        "escalate_factor": 1.25,
    },
}

# Generic fallback verification test if cause has no specialized mapping
DEFAULT_ACTION = {
    "action_id": "baseline_purge_check",
    "target_cause": "general_dispense_anomaly",
    "title": "Controlled Calibration Purge & Weight Check",
    "cost_badge": "⚡ 1 min · Low Cost",
    "instruction": "Execute a standard 1-second purge shot on an analytical balance to verify volumetric flow rate against baseline specification.",
    "expected_resolved": "Dispensed mass matches recipe target (+/- 5%).",
    "expected_unresolved": "Dispensed mass is out of specification.",
    "penalty_factor": 0.25,
    "escalate_factor": 1.20,
}


def get_verification_test_for_cause(cause_id: str) -> dict[str, Any]:
    """Retrieve the low-cost verification action for a given cause."""
    action = VERIFICATION_ACTIONS.get(cause_id)
    if action:
        return copy.deepcopy(action)
    fallback = copy.deepcopy(DEFAULT_ACTION)
    fallback["target_cause"] = cause_id
    fallback["title"] = f"Verification Test for {cause_id.replace('_', ' ').title()}"
    return fallback


def select_next_verification_action(
    ranked_causes: list[dict[str, Any]],
    completed_test_ids: list[str],
    symptoms: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select the next highest diagnostic value action with the lowest execution cost.
    
    If >= 3 tests have completed and all are unresolved, triggers the FAE Escalation pathway.
    """
    if len(completed_test_ids) >= 3:
        return {
            "action_id": "escalate_fae",
            "action_type": "ESCALATE",
            "target_cause": "hardware_or_chemistry_anomaly",
            "title": "Escalate to Field Application Engineer / Vendor Support",
            "cost_badge": "🚨 Engineering Escalation",
            "instruction": (
                "All automated low-cost checks completed without resolution. "
                "Issue likely stems from hardware piezo driver drift, closed-loop pressure regulator defect, "
                "or unlisted chemical batch contamination. Please log an engineering maintenance ticket."
            ),
            "expected_resolved": "Engineer assigned and machine put in maintenance bypass.",
            "expected_unresolved": "N/A",
            "penalty_factor": 1.0,
            "escalate_factor": 1.0,
        }

    # Find the top-ranked cause whose test hasn't been executed yet
    for cause in ranked_causes:
        cid = cause.get("id", "")
        test = get_verification_test_for_cause(cid)
        if test["action_id"] not in completed_test_ids:
            test["action_type"] = "VERIFY"
            test["current_cause_name"] = cause.get("name", cid)
            test["current_confidence"] = cause.get("likelihood_pct", 0)
            return test

    # Fallback if all top causes had tests executed
    fallback = copy.deepcopy(DEFAULT_ACTION)
    fallback["action_type"] = "VERIFY"
    return fallback


def normalize_likelihoods(causes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize cause scores so likelihood_pct sums to 100%."""
    total = sum(max(0.01, float(c.get("raw_score", c.get("likelihood_pct", 10)))) for c in causes)
    if total <= 0:
        total = 1.0
    for c in causes:
        score = max(0.01, float(c.get("raw_score", c.get("likelihood_pct", 10))))
        c["likelihood_pct"] = round((score / total) * 100, 1)
        c["raw_score"] = score
    # Sort descending
    causes.sort(key=lambda x: x["likelihood_pct"], reverse=True)
    return causes


def apply_counter_test_feedback(
    current_causes: list[dict[str, Any]],
    test_id: str,
    feedback: str,  # 'resolved' | 'unresolved' | 'shifted'
    test_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Dynamically re-score hypotheses using Bayesian / penalty update logic.
    
    Returns:
        {
            "ranked_causes": updated_causes,
            "resolved": bool,
            "confirmed_cause": str | None,
            "elimination_step": dict,
            "elimination_pathway": list[dict],
            "next_test": dict,
        }
    """
    causes = copy.deepcopy(current_causes)
    history = copy.deepcopy(test_history or [])

    # Find test definition
    test_def = None
    for action in VERIFICATION_ACTIONS.values():
        if action["action_id"] == test_id:
            test_def = action
            break
    if not test_def:
        test_def = copy.deepcopy(DEFAULT_ACTION)
        test_def["action_id"] = test_id

    target_cause_id = test_def.get("target_cause", "")
    target_cause_obj = next((c for c in causes if c.get("id") == target_cause_id), None)
    initial_pct = target_cause_obj.get("likelihood_pct", 0) if target_cause_obj else 0

    elimination_step: dict[str, Any] = {
        "test_id": test_id,
        "test_title": test_def.get("title", test_id),
        "target_cause_id": target_cause_id,
        "target_cause_name": target_cause_obj.get("name", target_cause_id) if target_cause_obj else target_cause_id,
        "feedback": feedback,
        "initial_confidence": initial_pct,
    }

    resolved = False
    confirmed_cause = None

    if feedback == "resolved":
        resolved = True
        confirmed_cause = target_cause_id
        for c in causes:
            if c.get("id") == target_cause_id:
                c["raw_score"] = 999.0
                c["likelihood_pct"] = 99.0
            else:
                c["raw_score"] = 0.1
                c["likelihood_pct"] = 0.1
        elimination_step["status"] = "CONFIRMED"
        elimination_step["new_confidence"] = 99.0
        elimination_step["summary"] = f"Confirmed {elimination_step['target_cause_name']} as root cause via {test_def['title']}."

    elif feedback == "unresolved":
        # Degrade target hypothesis significantly
        penalty = test_def.get("penalty_factor", 0.15)
        escalate = test_def.get("escalate_factor", 1.30)

        for c in causes:
            current_score = float(c.get("raw_score", c.get("likelihood_pct", 10)))
            if c.get("id") == target_cause_id:
                c["raw_score"] = max(0.5, current_score * penalty)
            else:
                # Competing causes that resist this test escalate
                c["raw_score"] = current_score * escalate

        causes = normalize_likelihoods(causes)
        new_pct = next((c.get("likelihood_pct", 0) for c in causes if c.get("id") == target_cause_id), 0)
        elimination_step["status"] = "ELIMINATED"
        elimination_step["new_confidence"] = new_pct
        top_now = causes[0] if causes else None
        escalated_name = top_now.get("name", "") if top_now else "Alternative cause"
        elimination_step["summary"] = (
            f"Refuted {elimination_step['target_cause_name']} ({initial_pct}% -> {new_pct}%). "
            f"Escalated {escalated_name} to {top_now.get('likelihood_pct', 0)}%."
        )

    elif feedback == "shifted":
        # Symptom changed/shifted (e.g. under-dispense to stringing or irregular dot)
        for c in causes:
            current_score = float(c.get("raw_score", c.get("likelihood_pct", 10)))
            if c.get("id") == target_cause_id:
                c["raw_score"] = current_score * 0.5
            elif c.get("id") in {"viscosity_temp_humidity", "pressure_time_high", "air_trapped_syringe"}:
                c["raw_score"] = current_score * 1.4
            else:
                c["raw_score"] = current_score * 1.1

        causes = normalize_likelihoods(causes)
        new_pct = next((c.get("likelihood_pct", 0) for c in causes if c.get("id") == target_cause_id), 0)
        elimination_step["status"] = "SHIFTED"
        elimination_step["new_confidence"] = new_pct
        elimination_step["summary"] = f"Symptom shifted. Re-weighted secondary dynamics ({elimination_step['target_cause_name']} at {new_pct}%)."

    history.append(elimination_step)
    completed_test_ids = [step["test_id"] for step in history]

    next_test = select_next_verification_action(causes, completed_test_ids)

    return {
        "ranked_causes": causes,
        "resolved": resolved,
        "confirmed_cause": confirmed_cause,
        "elimination_step": elimination_step,
        "elimination_pathway": history,
        "next_test": next_test,
    }
