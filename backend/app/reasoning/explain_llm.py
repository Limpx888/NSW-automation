"""Optional LLM explanation layer. Ranking stays deterministic; LLM only narrates."""

from __future__ import annotations

import os
from typing import Any

from backend.app.reasoning.rank_causes import explain_rules


def explain_with_llm(result: dict[str, Any]) -> str:
    """Use OpenAI if OPENAI_API_KEY is set; otherwise return rule-based text."""
    base = explain_rules(result)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return base

    try:
        from openai import OpenAI
    except ImportError:
        return base

    top = result.get("ranked_causes") or []
    rules = result.get("fired_rules") or []
    prompt = (
        "You are an industrial dispensing engineer assistant for NSW Automation. "
        "Write 3-5 short sentences explaining WHY the ranked causes make sense. "
        "Do NOT change the ranking or invent new causes. "
        "Cite the fired rules when relevant.\n\n"
        f"Defect: {result.get('pattern_specific_name')} on {result.get('material')} / {result.get('pattern')}\n"
        f"Top causes: {', '.join(c['name'] + ' ' + str(c['likelihood_pct']) + '%' for c in top[:4])}\n"
        f"Fired rules:\n" + "\n".join(f"- {r.get('explain', '')}" for r in rules) + "\n"
        f"Deterministic summary:\n{base}"
    )
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "Be concise, technical, and grounded in the provided rules only.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=220,
            temperature=0.2,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text if text else base
    except Exception:
        return base
