"""Generate an interactive Troubleshooting Action Plan (SOP) via Gemini 2.5 Flash."""

from __future__ import annotations

import json
import os
from typing import Any


def generate_action_plan(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert probability rankings into a standard SOP using structured LLM output."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    
    # Fallback to the existing deterministic action plan if no LLM
    fallback_plan = []
    if "action_plan" in result:
        for idx, step in enumerate(result["action_plan"]):
            fallback_plan.append({
                "step_number": idx + 1,
                "target_cause": "System Detected",
                "likelihood_score": "N/A",
                "action_title": f"Step {idx + 1}",
                "action_details": step.get("instruction", str(step)),
                "urgency": "Medium",
                "estimated_time": "Unknown",
                "reasoning": "Deterministic rule-based check."
            })

    if not api_key:
        return fallback_plan

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return fallback_plan

    top_causes = result.get("ranked_causes", [])[:4]
    if not top_causes:
        return fallback_plan
        
    causes_summary = "\n".join(
        f"- {c['name']} (Likelihood: {c['likelihood_pct']}%)"
        for c in top_causes
    )

    prompt = (
        "Generate a standardized operating procedure (SOP) action plan based on these prioritized causes:\n"
        f"{causes_summary}\n\n"
        "Guidelines:\n"
        "1. Start with the cause that has the highest likelihood score.\n"
        "2. Prioritize non-destructive, quick, and non-intrusive checks first.\n"
        "3. Provide an actionable step with clear verification criteria.\n"
        "4. Include a short 'Why check this first?' reasoning statement for junior operators."
    )

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are an expert SMT and dispensing technician generating structured operating procedures.",
                temperature=0.2,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "troubleshooting_plan": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step_number": {"type": "integer"},
                                    "target_cause": {"type": "string"},
                                    "likelihood_score": {"type": "string"},
                                    "action_title": {"type": "string"},
                                    "action_details": {"type": "string"},
                                    "urgency": {"type": "string", "enum": ["Low", "Medium", "High"]},
                                    "estimated_time": {"type": "string"},
                                    "reasoning": {"type": "string"}
                                },
                                "required": ["step_number", "target_cause", "likelihood_score", "action_title", "action_details", "urgency", "estimated_time", "reasoning"]
                            }
                        }
                    },
                    "required": ["troubleshooting_plan"]
                }
            )
        )
        
        payload = json.loads(resp.text)
        return payload.get("troubleshooting_plan", fallback_plan)
    except Exception:
        return fallback_plan
