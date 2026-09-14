"""
backend/cloud/rag_assistant.py
Retrieval-Augmented Generation (RAG) copilot for DARA.

1. Searches the Supabase cloud knowledge base for similar past incidents.
2. Falls back to the local SQLite learning database if Supabase is unavailable.
3. Synthesises a 3-step action plan using Gemini (already configured in Settings).
   Falls back to a deterministic rule-based summary if Gemini is not available.

No OpenAI dependency — uses the same Gemini key already set in backend/.env.
"""

from __future__ import annotations

from typing import Any

from backend.cloud.copilot import search_similar_incidents


# ── Local fallback search ────────────────────────────────────────────────────

def _local_fallback(
    defect_type: str,
    problem: str,
) -> list[dict[str, Any]]:
    """Pull relevant cases from the local SQLite learning DB as a fallback."""
    try:
        from backend import learning
        rows = learning.list_cases(limit=20, defect_class=defect_type)
        resolved = [r for r in rows if r.get("successful_solution")]
        # Return top 3 resolved cases in dict format matching Supabase rows
        return [
            {
                "root_cause": r.get("successful_cause") or "Unknown",
                "resolution_action": r.get("successful_solution") or "",
                "similarity": 0.85,  # assumed similarity for local matches
                "dispensing_problem": r.get("dispensing_problem") or "",
                "source": "local_db",
            }
            for r in resolved[:3]
        ]
    except Exception:  # noqa: BLE001
        return []


# ── Prompt builder ───────────────────────────────────────────────────────────

def _build_prompt(
    defect_type: str,
    problem: str,
    past_cases: list[dict[str, Any]],
    defect_label: str = "",
    pressure: float | None = None,
    viscosity: float | None = None,
    size_um: float | None = None,
) -> str:
    label = defect_label or defect_type.replace("_", " ").title()
    lines = [
        "You are DARA, an expert AI Copilot for precision manufacturing fluid dispensing quality control.",
        "",
        "## Current Line Defect",
        f"- Type: {label}",
    ]
    if problem:
        lines.append(f"- Problem Description: {problem}")
    if size_um is not None:
        lines.append(f"- Measured Size: {size_um:.1f} µm")
    if pressure is not None:
        lines.append(f"- Dispense Pressure: {pressure:.2f} bar")
    if viscosity is not None:
        lines.append(f"- Material Viscosity: {viscosity:.1f} cps")

    if past_cases:
        lines += ["", "## Historical Cases from Knowledge Base"]
        for idx, case in enumerate(past_cases, 1):
            sim = case.get("similarity", 0)
            sim_str = f"{sim*100:.1f}%" if sim else "N/A"
            lines.append(f"\n### Case #{idx} (Similarity: {sim_str})")
            lines.append(f"- Root Cause: {case.get('root_cause', 'Unknown')}")
            lines.append(f"- Resolution: {case.get('resolution_action', 'N/A')}")
            if case.get("dispensing_problem"):
                lines.append(f"- Problem: {case.get('dispensing_problem')}")
    else:
        lines += ["", "## No Historical Cases Found", "Provide guidance based on dispensing engineering best practices."]

    lines += [
        "",
        "## Instructions",
        "Based on the defect type and the historical cases above, provide:",
        "1. The most likely root cause (one sentence)",
        "2. An immediate 3-step action plan for the operator",
        "3. A preventive measure to avoid recurrence",
        "",
        "Keep the response concise, practical, and in plain language for a factory technician.",
    ]
    return "\n".join(lines)


# ── LLM synthesis ────────────────────────────────────────────────────────────

def _synthesise_with_gemini(prompt: str) -> str | None:
    try:
        from backend.config import get_settings
        import google.generativeai as genai  # type: ignore

        settings = get_settings()
        if not settings.gemini_api_key.strip():
            return None
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:  # noqa: BLE001
        print(f"[cloud.rag_assistant] Gemini synthesis failed: {exc}")
        return None


def _deterministic_summary(
    defect_type: str,
    past_cases: list[dict[str, Any]],
) -> str:
    """Rule-based fallback when LLM is unavailable."""
    if not past_cases:
        return (
            f"No historical cloud data for {defect_type}. "
            "Check nozzle tip, purge for air bubbles, and verify dispense parameters against last known-good recipe."
        )
    top = past_cases[0]
    cause = top.get("root_cause", "undetermined cause")
    action = top.get("resolution_action", "review dispensing settings")
    return (
        f"Based on {len(past_cases)} similar historical case(s), the most likely root cause is: {cause}.\n\n"
        f"Recommended action: {action}\n\n"
        "Additional steps: Verify nozzle cleanliness, confirm material viscosity is within process window, "
        "and run 5–10 dummy shots before resuming production."
    )


# ── Public API ───────────────────────────────────────────────────────────────

def generate_technician_guidance(
    defect_type: str,
    *,
    problem: str = "",
    defect_label: str = "",
    size_um: float | None = None,
    pressure: float | None = None,
    viscosity: float | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Generate a RAG-powered technician guidance response.

    Returns
    -------
    dict with keys:
      - guidance (str): the synthesised action plan
      - past_cases (list): the retrieved similar incidents
      - source (str): 'cloud', 'local_db', or 'deterministic'
      - provider (str): 'gemini' or 'rule_based'
    """
    # 1. Search cloud knowledge base (falls back to [] if Supabase not configured)
    past_cases = search_similar_incidents(
        defect_type=defect_type,
        problem=problem,
        size_um=size_um,
        pressure=pressure,
        viscosity=viscosity,
        top_k=top_k,
    )
    source = "cloud" if past_cases else "local_db"

    # 2. Fallback to local SQLite learning DB when cloud has no results
    if not past_cases:
        past_cases = _local_fallback(defect_type, problem)
        if not past_cases:
            source = "deterministic"

    # 3. Build prompt and synthesise response
    prompt = _build_prompt(
        defect_type=defect_type,
        defect_label=defect_label,
        problem=problem,
        past_cases=past_cases,
        size_um=size_um,
        pressure=pressure,
        viscosity=viscosity,
    )

    guidance = _synthesise_with_gemini(prompt)
    provider = "gemini"
    if guidance is None:
        guidance = _deterministic_summary(defect_type, past_cases)
        provider = "rule_based"

    return {
        "guidance": guidance,
        "past_cases": past_cases,
        "case_count": len(past_cases),
        "source": source,
        "provider": provider,
    }
