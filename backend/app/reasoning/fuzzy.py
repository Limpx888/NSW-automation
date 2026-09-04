"""Fuzzy membership for Q&A routing and cause scoring.

Crisp answers (occasional, yes, too_small) keep μ = 1 so existing rankings
stay the same. Overlapping defect looks, and 'unknown', get partial μ so rules
can fire softly instead of all-or-nothing.
"""

from __future__ import annotations

from typing import Any

# Minimum μ to ask a follow-up / apply evidence or a multiplier.
QUESTION_FIRE = 0.4
EVIDENCE_FIRE = 0.2
UNKNOWN_MU = 0.45

# Symmetric similarity for overlapping linguistic values (not opposites).
_AMOUNT = {
    ("too_small", "inconsistent"): 0.5,
    ("too_small", "missing"): 0.4,
    ("too_small", "broken_line"): 0.45,
    ("missing", "broken_line"): 0.65,
    ("inconsistent", "irregular"): 0.4,
    ("inconsistent", "missing"): 0.3,
    ("irregular", "stringing"): 0.55,
    ("irregular", "too_small"): 0.25,
    ("stringing", "too_large"): 0.2,
    ("misaligned", "inconsistent"): 0.35,
    ("spreading", "too_large"): 0.45,
}
_FREQUENCY = {
    ("occasional", "continuous"): 0.15,  # almost exclusive; leftover doubt only
}
_TIMING = {
    ("after_restart", "immediate"): 0.8,
    ("after_restart", "from_start"): 0.55,
    ("after_runtime", "got_worse"): 0.8,
    ("immediate", "from_start"): 0.7,
    ("after_runtime", "immediate"): 0.2,
}
_CHANGE = {
    ("settings", "temperature"): 0.25,
    ("material", "temperature"): 0.2,
}
_BOOLISH = {
    ("yes", "unknown"): UNKNOWN_MU,
    ("no", "unknown"): UNKNOWN_MU,
    ("blocking", "unknown"): UNKNOWN_MU,
    ("clear", "unknown"): UNKNOWN_MU,
    ("blocking", "clear"): 0.0,
}
_LOCATION = {
    ("single", "multiple"): 0.1,
}

_TABLES = {
    "amount": _AMOUNT,
    "frequency": _FREQUENCY,
    "timing": _TIMING,
    "onset": _TIMING,
    "recent_change": _CHANGE,
    "visible_bubbles": _BOOLISH,
    "retract_stringing": _BOOLISH,
    "mix_state": _BOOLISH,
    "uv_barrel": _BOOLISH,
    "location": _LOCATION,
}


def _lookup(table: dict[tuple[str, str], float], left: str, right: str) -> float:
    if left == right:
        return 1.0
    return table.get((left, right), table.get((right, left), 0.0))


def membership(field: str, actual: Any, expected: Any) -> float:
    """μ(actual is expected) in [0, 1]. Unanswered → 0."""
    if actual is None or actual == "":
        return 0.0
    actual_s = str(actual)
    expected_s = str(expected)
    if actual_s == expected_s:
        return 1.0
    if actual_s == "unknown":
        return UNKNOWN_MU
    table = _TABLES.get(field, {})
    return _lookup(table, actual_s, expected_s)


def clause_strength(field: str, expected: Any, answers: dict[str, Any]) -> float:
    actual = answers.get(field)
    if isinstance(expected, list):
        if not expected:
            return 1.0
        return max(membership(field, actual, item) for item in expected)
    return membership(field, actual, expected)


def when_strength(when: dict[str, Any] | None, answers: dict[str, Any]) -> float:
    """Mamdani AND: min of clause memberships. Empty when → 1."""
    if not when:
        return 1.0
    return min(clause_strength(key, expected, answers) for key, expected in when.items())


def blend_factor(factor: float, mu: float) -> float:
    """Interpolate a multiplier toward 1.0 when membership is partial."""
    mu = max(0.0, min(1.0, mu))
    return 1.0 + (float(factor) - 1.0) * mu
