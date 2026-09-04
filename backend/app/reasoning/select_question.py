"""Optional LLM pick among eligible follow-ups (highest information gain).

The interview graph stays a JSON FSM. When GEMINI_API_KEY is set, the model
may only choose from candidate question ids via structured JSON output — it cannot
invent questions or change ranking weights.
"""

from __future__ import annotations

import json
import os
from typing import Any


def pick_followup_id(answers: dict[str, Any], candidates: list[dict[str, Any]]) -> str | None:
    """Return a candidate id, or None to fall back to the deterministic sort."""
    if len(candidates) <= 1:
        return candidates[0]["id"] if candidates else None

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    allowed = [q["id"] for q in candidates]
    catalog = "\n".join(
        f"- {q['id']} (gain {q.get('information_gain', 0.5):.2f}): {q['prompt']}"
        for q in candidates
    )
    known = {k: v for k, v in answers.items() if not str(k).startswith("_")}
    
    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Known answers: {known}\n\nCandidates:\n{catalog}",
            config=types.GenerateContentConfig(
                system_instruction="You pick the next diagnostic question for a dispensing engineer. Choose the id that most splits remaining root causes.",
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "question_id": {
                            "type": "string",
                            "enum": allowed,
                            "description": "Must be one of the candidate ids."
                        },
                        "reason": {"type": "string"}
                    },
                    "required": ["question_id"]
                }
            )
        )
        
        payload = json.loads(resp.text)
        token = str(payload.get("question_id") or "").strip()
        if token in allowed:
            return token
    except Exception:
        return None
    return None
