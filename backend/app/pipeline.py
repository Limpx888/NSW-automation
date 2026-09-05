"""Photo + Q&A -> ranked causes + similar cases + quality score."""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.app.applications import resolve_answers
from backend.app.db.cases import log_case, similar_cases
from backend.app.reasoning.discover import apply_amount
from backend.app.reasoning.explain_llm import explain_with_llm
from backend.app.reasoning.rank_causes import explain_rules, rank_causes
from backend.app.reasoning.generate_sop import generate_action_plan
from backend.app.reasoning.counter_test import select_next_verification_action
from backend.app.vision.predict import predict_image, quality_assessment


def run_session(answers: dict[str, Any], image_bgr: np.ndarray | None = None) -> dict[str, Any]:
    answers = apply_amount(resolve_answers(dict(answers)))
    vision = None
    if image_bgr is not None:
        vision = predict_image(image_bgr)
        answers["vision_confidence"] = vision["confidence"]
        if not answers.get("defect_class"):
            answers["defect_class"] = vision["defect_class"]
        elif vision["defect_class"] != answers["defect_class"]:
            answers["vision_disagreement"] = True

    result = rank_causes(answers)
    result["explanation"] = explain_with_llm(result)
    result["explanation_deterministic"] = explain_rules(result)
    
    # Generate the LLM structured SOP plan
    result["sop_plan"] = generate_action_plan(result)
    
    # Attach initial low-cost counter-test
    result["initial_test"] = select_next_verification_action(result.get("ranked_causes", []), [])
    
    if vision:
        result["vision"] = vision
        result["quality"] = quality_assessment(vision["defect_class"], vision["confidence"])
    else:
        result["quality"] = quality_assessment(result["defect_class"], 0.55)

    result["similar"] = similar_cases(result["material"], result["defect_class"])
    result["symptoms"] = answers
    result["session_id"] = log_case(result)
    return result
