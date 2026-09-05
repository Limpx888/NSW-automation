"""Guided Q&A: core dimensions plus JSON-routed dynamic follow-ups."""

from __future__ import annotations

from typing import Any

from backend.app.reasoning.fuzzy import QUESTION_FIRE, when_strength
from backend.app.reasoning.rank_causes import load_rules
from backend.app.reasoning.select_question import pick_followup_id

AMOUNT_TO_DEFECT = {
    "too_small": "under_dispense",
    "too_large": "over_dispense",
    "missing": "missing",
    "inconsistent": "inconsistent_volume",
    "spreading": "spreading",
    "irregular": "air_bubble_irregular",
    "stringing": "air_bubble_irregular",
    "misaligned": "inconsistent_volume",
    "broken_line": "missing",
}

CORE_DIMENSIONS = [
    ("material", "Material type"),
    ("amount", "Defect appearance"),
    ("frequency", "Frequency and pattern"),
    ("recent_change", "Recent process changes"),
    ("location", "Spatial distribution"),
]

OPTION_LABELS = {
    "solder_paste": "Solder paste",
    "silver_epoxy": "Silver epoxy (epoxy)",
    "uv_glue": "UV glue",
    "silicone_gel": "Silicone gel",
    "liquid_metal": "Liquid metal (Ga/In TIM)",
    "dot": "Dot",
    "line": "Line",
    "dam_fill": "Dam and fill",
    "too_small": "Too small / under-dispense",
    "too_large": "Too large / over-dispense",
    "missing": "Missing shot",
    "inconsistent": "Inconsistent sizing",
    "spreading": "Spreading beyond the area",
    "irregular": "Air bubble / irregular shape",
    "stringing": "Stringing / tails on retract",
    "misaligned": "Misaligned dots",
    "broken_line": "Broken dispensing line",
    "occasional": "Occasional / random",
    "continuous": "Continuous / every shot",
    "none": "No recent change",
    "material": "Material batch changed",
    "nozzle": "Nozzle tip changed",
    "settings": "Pressure / time / suck-back settings changed",
    "temperature": "Operating temperature changed",
    "single": "One location / one point",
    "multiple": "Several points or boards",
    "after_restart": "Right after machine restart",
    "after_runtime": "Only after running for some time",
    "immediate": "From the first shots / right away",
    "from_start": "Wrong from the first shot",
    "got_worse": "Got worse after running a while",
    "after_idle": "After the tip idles",
    "after_long_run": "After a long run",
    "unknown": "Not sure",
    "blocking": "UV-blocking (amber / black)",
    "clear": "Clear barrel or tip",
    "yes": "Yes",
    "no": "No",
}

SKIPPED = "_skipped"


def when_matches(when: dict[str, Any] | None, answers: dict[str, Any]) -> bool:
    """True only for a near-crisp match (μ ≈ 1). Use when_strength for partial fire."""
    return when_strength(when, answers) >= 0.999


def label_for(option: str) -> str:
    return OPTION_LABELS.get(option, str(option).replace("_", " "))


def _decorate(question: dict[str, Any], *, source: str, dimension: str | None = None) -> dict[str, Any]:
    q = dict(question)
    q["source"] = source
    q["dimension"] = q.get("dimension") or dimension or source
    opts = q.get("options")
    if isinstance(opts, list):
        q["choices"] = [{"id": o, "label": label_for(str(o))} for o in opts]
    else:
        q["choices"] = []
    return q


def all_questions() -> list[dict[str, Any]]:
    rules = load_rules()
    return [_decorate(q, source="core", dimension=q["id"]) for q in rules["discovery_questions"]]


def followups_for(material: str | None) -> list[dict[str, Any]]:
    rules = load_rules()
    if not material:
        return []
    out = []
    for q in rules.get("followups", {}).get(material, []):
        node = dict(q)
        node.setdefault("when", {"material": material})
        when = dict(node["when"])
        when.setdefault("material", material)
        node["when"] = when
        out.append(_decorate(node, source="material"))
    return out


def dynamic_followups() -> list[dict[str, Any]]:
    rules = load_rules()
    return [_decorate(q, source="dynamic") for q in rules.get("dynamic_followups", [])]


def core_progress(answers: dict[str, Any]) -> dict[str, Any]:
    filled = [dim for dim, _title in CORE_DIMENSIONS if answers.get(dim)]
    return {
        "answered": len(filled),
        "total": len(CORE_DIMENSIONS),
        "dimensions": [
            {"id": dim, "title": title, "done": bool(answers.get(dim))}
            for dim, title in CORE_DIMENSIONS
        ],
        "pattern_done": bool(answers.get("pattern")),
    }


def _is_answered(answers: dict[str, Any], qid: str) -> bool:
    skipped = answers.get(SKIPPED) or []
    if qid in skipped:
        return True
    return qid in answers and answers.get(qid) not in (None, "")


def eligible_followups(answers: dict[str, Any]) -> list[dict[str, Any]]:
    """Follow-ups whose fuzzy `when` strength is high enough, still unanswered."""
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for q in followups_for(answers.get("material")) + dynamic_followups():
        qid = q["id"]
        if qid in seen:
            continue
        if _is_answered(answers, qid):
            continue
        strength = when_strength(q.get("when"), answers)
        if strength < QUESTION_FIRE:
            continue
        seen.add(qid)
        node = dict(q)
        node["fuzzy_strength"] = round(strength, 3)
        node["fuzzy_gain"] = round(float(q.get("information_gain") or 0.5) * strength, 4)
        candidates.append(node)
    candidates.sort(
        key=lambda item: (
            float(item.get("fuzzy_gain") or 0.0),
            float(item.get("information_gain") or 0.5),
        ),
        reverse=True,
    )
    return candidates


def next_question(
    answers: dict[str, Any],
    *,
    include_optional: bool = True,
    use_llm: bool = False,
) -> dict[str, Any] | None:
    """Next unanswered node in the interview FSM, or None when the set is complete.

    Core dimensions are asked in JSON order (predictable). Follow-ups are selected
    by information_gain. If use_llm is true, the model may only pick among those
    eligible ids — it cannot invent questions.
    """
    from backend.app.applications import get_application

    app = get_application(answers.get("application"))
    allowed_materials = None
    if app and app.get("material_choices"):
        allowed_materials = set(app["material_choices"])

    for q in all_questions():
        if not _is_answered(answers, q["id"]):
            node = dict(q)
            if node["id"] == "material" and allowed_materials:
                opts = [o for o in (node.get("options") or []) if o in allowed_materials]
                node["options"] = opts
                node["choices"] = [{"id": o, "label": label_for(str(o))} for o in opts]
                node["prompt"] = "Which dam / fill material are you using?"
            if node["id"] == "pattern" and app and app.get("patterns"):
                opts = [o for o in (node.get("options") or []) if o in set(app["patterns"])]
                if opts:
                    node["options"] = opts
                    node["choices"] = [{"id": o, "label": label_for(str(o))} for o in opts]
            return node

    candidates = eligible_followups(answers)
    required = [q for q in candidates if not q.get("optional")]
    optional = [q for q in candidates if q.get("optional")]
    pool = required if required else (optional if include_optional else [])
    if not pool:
        return None

    if use_llm:
        picked_id = pick_followup_id(answers, pool)
        if picked_id:
            for q in pool:
                if q["id"] == picked_id:
                    chosen = dict(q)
                    chosen["selected_by"] = "llm"
                    return chosen

    chosen = dict(pool[0])
    chosen["selected_by"] = "fuzzy_gain" if chosen.get("fuzzy_strength", 1) < 0.999 else "information_gain"
    return chosen


def is_complete(answers: dict[str, Any]) -> bool:
    return next_question(answers, include_optional=False, use_llm=False) is None


def apply_amount(answers: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in answers.items() if k != SKIPPED}
    if not out.get("defect_class") and out.get("amount") in AMOUNT_TO_DEFECT:
        out["defect_class"] = AMOUNT_TO_DEFECT[out["amount"]]
    if out.get("onset") == "got_worse" and not out.get("timing"):
        out["timing"] = "after_runtime"
    if out.get("retract_stringing") == "yes" and out.get("amount") not in {"stringing", "irregular"}:
        out["amount"] = out.get("amount") or "stringing"
    return out
