"""Deterministic cause ranking. LLM may explain fired rules; it must not change weights."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_PATH = (
    Path(__file__).resolve().parents[3] / "research" / "cause_ranking_rules.json"
)

AMOUNT_TO_DEFECT = {
    "too_small": "under_dispense",
    "too_large": "over_dispense",
    "missing": "missing",
    "inconsistent": "inconsistent_volume",
    "spreading": "spreading",
    "irregular": "air_bubble_irregular",
}

CLOG_CAUSES = {"nozzle_partial_clog", "powder_nozzle_mismatch"}
OXIDATION_CAUSES = {"powder_oxidation", "flux_metal_separation"}
SPREAD_CAUSES = {"viscosity_temp_humidity", "pressure_time_high"}

LOW_VISION_CONFIDENCE = 0.45


@lru_cache(maxsize=1)
def load_rules(path: str | None = None) -> dict[str, Any]:
    rules_file = Path(path) if path else RULES_PATH
    with rules_file.open(encoding="utf-8") as handle:
        return json.load(handle)


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(v, 0.0) for v in weights.values())
    if total <= 0:
        n = len(weights) or 1
        return {k: 100.0 / n for k in weights}
    return {k: 100.0 * max(v, 0.0) / total for k, v in weights.items()}


def _apply_multipliers(weights: dict[str, float], factors: dict[str, float]) -> None:
    for cause_id, factor in factors.items():
        if cause_id in weights:
            weights[cause_id] *= factor


def resolve_defect(symptoms: dict[str, Any], rules: dict[str, Any]) -> str:
    if symptoms.get("defect_class") in rules["defect_classes"]:
        return symptoms["defect_class"]
    amount = symptoms.get("amount")
    mapped = AMOUNT_TO_DEFECT.get(amount)
    if mapped:
        return mapped
    raise ValueError(
        "Need defect_class or amount "
        f"(one of {sorted(AMOUNT_TO_DEFECT)})."
    )


def _powder_factors(symptoms: dict[str, Any], rules: dict[str, Any]) -> tuple[dict[str, float], list[dict[str, str]]]:
    fired: list[dict[str, str]] = []
    extra: dict[str, float] = {}
    if symptoms.get("material") != "solder_paste":
        return extra, fired

    powder = symptoms.get("powder_type") or symptoms.get("powder") or "T4"
    if powder not in rules["powder_types"]:
        powder = "T4"
    spec = rules["powder_types"][powder]
    fired.append(
        {
            "id": f"powder_{powder}",
            "explain": (
                f"{powder}: particles {spec['d_min_um']}-{spec['d_max_um']} um. "
                f"Surface-area-to-volume vs Type 4 ~ {spec['sa_v_ratio_vs_t4']}x. "
                f"{spec['typical_use']}"
            ),
        }
    )
    extra["nozzle_partial_clog"] = spec["clog_factor"]
    extra["powder_nozzle_mismatch"] = spec["clog_factor"]
    extra["powder_oxidation"] = spec["oxidation_factor"]
    extra["flux_metal_separation"] = spec["oxidation_factor"]
    extra["viscosity_temp_humidity"] = spec["spread_factor"]
    extra["pressure_time_high"] = spec["spread_factor"]

    nozzle_id = symptoms.get("nozzle_id_um")
    if nozzle_id is not None:
        try:
            nozzle_id = float(nozzle_id)
        except (TypeError, ValueError):
            nozzle_id = None
    if nozzle_id is not None:
        min_id = spec["nsw_min_nozzle_um"]
        five_x = 5 * spec["d_max_um"]
        if nozzle_id < min_id or nozzle_id < five_x:
            extra["powder_nozzle_mismatch"] = extra.get("powder_nozzle_mismatch", 1.0) * 2.2
            extra["nozzle_partial_clog"] = extra.get("nozzle_partial_clog", 1.0) * 1.4
            rule = rules["five_x_rule"]
            fired.append(
                {
                    "id": "five_x_nozzle_violation",
                    "explain": (
                        f"Nozzle ID {nozzle_id:.0f} um is below the NSW floor of {min_id} um "
                        f"for {powder} (5x largest particle {spec['d_max_um']} um = {five_x} um). "
                        f"{rule['t6_vs_t4_copy']}"
                    ),
                }
            )
        else:
            fired.append(
                {
                    "id": "five_x_nozzle_ok",
                    "explain": (
                        f"Nozzle ID {nozzle_id:.0f} um meets the NSW 5x floor of {min_id} um for {powder}."
                    ),
                }
            )
    return extra, fired


def rank_causes(symptoms: dict[str, Any], rules_path: str | None = None) -> dict[str, Any]:
    """Rank root causes from Q&A (+ optional vision defect).

    Expected keys: material, pattern, defect_class or amount, frequency,
    recent_change, location. Optional: powder_type, nozzle_id_um, timing,
    uv_barrel, mix_state, vision_confidence.
    """
    rules = load_rules(rules_path)
    material = symptoms.get("material")
    if material not in rules["materials"]:
        raise ValueError(f"Unknown material: {material}")
    pattern = symptoms.get("pattern", "dot")
    if pattern not in rules["patterns"]:
        pattern = "dot"

    defect = resolve_defect(symptoms, rules)
    baseline = dict(rules["baselines"][material][defect])
    allowed = {
        cid
        for cid, meta in rules["causes"].items()
        if material in meta["materials"]
    }
    weights = {cid: w for cid, w in baseline.items() if cid in allowed}

    fired: list[dict[str, str]] = []
    powder_mult, powder_fired = _powder_factors(symptoms, rules)
    _apply_multipliers(weights, powder_mult)
    fired.extend(powder_fired)

    _apply_multipliers(weights, rules.get("pattern_multipliers", {}).get(pattern, {}))

    answers = {
        "frequency": symptoms.get("frequency"),
        "recent_change": symptoms.get("recent_change"),
        "location": symptoms.get("location"),
        "timing": symptoms.get("timing"),
        "uv_barrel": symptoms.get("uv_barrel"),
        "mix_state": symptoms.get("mix_state"),
    }
    for rule in rules["adjustment_rules"]:
        when = rule.get("when", {})
        if all(answers.get(k) == v for k, v in when.items()):
            _apply_multipliers(weights, rule.get("multiply", {}))
            fired.append({"id": rule["id"], "explain": rule["explain"]})

    weights = _renormalize(weights)

    vision_conf = symptoms.get("vision_confidence")
    manual_review = False
    if vision_conf is not None:
        try:
            vision_conf = float(vision_conf)
        except (TypeError, ValueError):
            vision_conf = None
    if vision_conf is not None and vision_conf < LOW_VISION_CONFIDENCE:
        manual_review = True
        fired.append(
            {
                "id": "low_vision_confidence",
                "explain": (
                    f"Vision confidence {vision_conf:.0%} is below {LOW_VISION_CONFIDENCE:.0%}. "
                    "Treat the defect class as a suggestion and confirm visually before acting."
                ),
            }
        )

    ranked = sorted(weights.items(), key=lambda item: item[1], reverse=True)
    causes_out = []
    for cause_id, pct in ranked:
        meta = rules["causes"][cause_id]
        causes_out.append(
            {
                "id": cause_id,
                "name": meta["name"],
                "category": meta["category"],
                "likelihood_pct": round(pct, 1),
                "cost_rank": meta["cost_rank"],
                "check": meta["check"],
            }
        )

    action_plan = generate_action_plan(causes_out)
    warnings = rules.get("downstream_warnings", {}).get(defect, [])
    pattern_names = {
        "under_dispense": {"dot": "undersized_dot", "line": "thin_or_broken_line", "dam_fill": "low_dam_or_incomplete_fill"},
        "over_dispense": {"dot": "oversized_dot", "line": "thick_line", "dam_fill": "overflow_fill"},
        "missing": {"dot": "missing_dot", "line": "missing_segment", "dam_fill": "missing_dam_or_fill"},
        "inconsistent_volume": {"dot": "inconsistent_dots", "line": "inconsistent_width", "dam_fill": "inconsistent_height"},
        "spreading": {"dot": "dot_slump_bleed", "line": "line_bleed", "dam_fill": "dam_collapse"},
        "air_bubble_irregular": {"dot": "satellite_or_voided_dot", "line": "voids_or_ragged_edge", "dam_fill": "void_in_fill"},
    }

    return {
        "defect_class": defect,
        "pattern_specific_name": pattern_names.get(defect, {}).get(pattern, defect),
        "material": material,
        "pattern": pattern,
        "ranked_causes": causes_out,
        "fired_rules": fired,
        "action_plan": action_plan,
        "downstream_warnings": warnings,
        "manual_review": manual_review,
        "vision_confidence": vision_conf,
    }


def generate_action_plan(ranked_causes: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    """Cheap/fast checks first, but keep the #1 likely cause in the top three."""
    if not ranked_causes:
        return []
    by_cost = sorted(ranked_causes, key=lambda c: (c["cost_rank"], -c["likelihood_pct"]))
    leader = ranked_causes[0]
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    cheap = [c for c in by_cost if c["cost_rank"] <= 2][:2]
    for cause in cheap + [leader] + by_cost:
        if cause["id"] in seen:
            continue
        seen.add(cause["id"])
        ordered.append(cause)
        if len(ordered) >= top_n:
            break

    steps = []
    for i, cause in enumerate(ordered, start=1):
        steps.append(
            {
                "step": i,
                "cause_id": cause["id"],
                "title": cause["name"],
                "instruction": cause["check"],
                "likelihood_pct": cause["likelihood_pct"],
            }
        )
    return steps


def explain_rules(result: dict[str, Any]) -> str:
    """Deterministic fallback explanation (LLM wraps this on Day 10)."""
    top = result["ranked_causes"][:3]
    lines = [
        f"Most likely defect: {result['pattern_specific_name']} "
        f"({result['defect_class']}) on {result['material']} / {result['pattern']}."
    ]
    if top:
        names = ", ".join(f"{c['name']} ({c['likelihood_pct']:.0f}%)" for c in top)
        lines.append(f"Top ranked causes: {names}.")
    for rule in result.get("fired_rules", []):
        lines.append(f"- {rule['explain']}")
    if result.get("downstream_warnings"):
        lines.append(
            "Downstream risk if unfixed: " + ", ".join(result["downstream_warnings"]) + "."
        )
    if result.get("manual_review"):
        lines.append("Vision confidence is low — confirm the defect by eye before changing the process.")
    return "\n".join(lines)
