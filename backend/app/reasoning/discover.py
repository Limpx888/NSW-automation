"""Discovery question flow, including material-specific follow-ups."""

from __future__ import annotations

from typing import Any

from backend.app.reasoning.rank_causes import load_rules

AMOUNT_TO_DEFECT = {
    "too_small": "under_dispense",
    "too_large": "over_dispense",
    "missing": "missing",
    "inconsistent": "inconsistent_volume",
    "spreading": "spreading",
    "irregular": "air_bubble_irregular",
}


def all_questions() -> list[dict[str, Any]]:
    rules = load_rules()
    return list(rules["discovery_questions"])


def followups_for(material: str | None) -> list[dict[str, Any]]:
    rules = load_rules()
    if not material:
        return []
    return list(rules.get("followups", {}).get(material, []))


def next_question(answers: dict[str, Any]) -> dict[str, Any] | None:
    """Return the next unanswered question, or None when the set is complete."""
    for q in all_questions():
        if not answers.get(q["id"]):
            return q
    for q in followups_for(answers.get("material")):
        qid = q["id"]
        if qid == "nozzle_id_um":
            continue
        if not answers.get(qid):
            return q
    return None


def is_complete(answers: dict[str, Any]) -> bool:
    return next_question(answers) is None


def apply_amount(answers: dict[str, Any]) -> dict[str, Any]:
    out = dict(answers)
    if not out.get("defect_class") and out.get("amount") in AMOUNT_TO_DEFECT:
        out["defect_class"] = AMOUNT_TO_DEFECT[out["amount"]]
    return out
