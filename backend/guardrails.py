"""
backend/guardrails.py
Expert Rules & Domain Constraints (Domain Guardrails) for DARA.

Validates and refines recommendations to ensure engineering physical common sense
and inject actionable parameter directions.
"""

from __future__ import annotations

from typing import Iterable


def apply_domain_guardrails(
    defect_class: str | None,
    recommended_solutions: Iterable[str],
) -> list[str]:
    """
    Filter and refine recommended solutions against industrial domain rules:
    1. For voiding issues, never recommend increasing squeegee/dispense pressure.
    2. Forcefully inject actionable parameter increments (e.g. ±0.05 MPa) if generic pressure mentioned.
    3. Ensure safe non-empty fallback.
    """
    filtered_solutions: list[str] = []
    d_class = (defect_class or "").lower()

    for sol in recommended_solutions:
        if not isinstance(sol, str) or not sol.strip():
            continue
        text = sol.strip()
        lower = text.lower()

        # Rule 1: For voiding defects, never recommend increasing pressure (traps volatiles)
        if "void" in d_class and ("increase squeegee pressure" in lower or "increase pressure" in lower):
            continue

        # Rule 2: Forcefully inject actionable parameter directions if generic pressure is mentioned
        if "pressure" in lower and not any(unit in lower for unit in ("mpa", "bar", "kg", "psi")):
            text += " (Recommended adjustment: ±0.05 MPa / ±0.5 bar)"

        filtered_solutions.append(text)

    # If filtered list is empty, provide a safe domain fallback solution
    if not filtered_solutions:
        filtered_solutions.append("Verify machine parameters against the golden recipe standard.")

    return filtered_solutions
