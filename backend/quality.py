"""Map YOLO detections → dispensing quality assessment (mockup scores)."""

from __future__ import annotations

from typing import Any

import numpy as np

SEVERITY = {
    "missing_dot": 0.9,
    "spreading": 0.78,
    "too_much": 0.68,
    "too_little": 0.62,
    "inconsistent_size": 0.72,
    "air_bubble": 0.58,
    "no_defect_detected": 0.08,
}


def _clamp_stars(value: float) -> float:
    """Return 0.5-step stars in [1.0, 5.0]."""
    stepped = round(value * 2) / 2
    return float(np.clip(stepped, 1.0, 5.0))


def assess_quality(analysis: dict[str, Any]) -> dict[str, Any]:
    detections = analysis.get("detections") or []
    defect = analysis.get("defect_class") or "no_defect_detected"
    conf = float(analysis.get("confidence") or 0.5)
    severity = SEVERITY.get(defect, 0.55)

    if not detections:
        overall = 92
        return {
            "overall_quality_score": overall,
            "shape_consistency": 4.5,
            "size_consistency": 4.5,
            "dispensing_position": 4.5,
            "defect_risk": 1.5,
            "defect_class": defect,
            "defect_label": analysis.get("defect_label", "NO DEFECT DETECTED"),
            "confidence": conf,
        }

    boxes = [d["box"] for d in detections]
    widths = np.array([b["width"] for b in boxes], dtype=np.float32)
    heights = np.array([b["height"] for b in boxes], dtype=np.float32)
    areas = widths * heights
    cxs = np.array([b["cx"] for b in boxes], dtype=np.float32)
    cys = np.array([b["cy"] for b in boxes], dtype=np.float32)

    # Size consistency from area CV
    area_cv = float(areas.std() / (areas.mean() + 1e-6))
    size_stars = _clamp_stars(5.0 - min(area_cv, 1.2) * 3.2)

    # Shape consistency from width/height aspect variance
    aspects = widths / (heights + 1e-6)
    aspect_cv = float(aspects.std() / (aspects.mean() + 1e-6))
    shape_stars = _clamp_stars(5.0 - min(aspect_cv, 1.0) * 3.5 - severity * 0.6)

    # Position consistency from centroid scatter (normalized by image diagonal)
    img_w = max(float(analysis.get("image_size", {}).get("width", 1)), 1.0)
    img_h = max(float(analysis.get("image_size", {}).get("height", 1)), 1.0)
    diag = float(np.hypot(img_w, img_h))
    scatter = float(np.hypot(cxs.std(), cys.std()) / diag)
    # High scatter can be OK for dense arrays; penalize when few detections are wildly off
    position_stars = _clamp_stars(5.0 - scatter * 8.0 - (0.8 if defect in {"spreading", "missing_dot"} else 0.0))

    # Defect risk rises with severity × confidence × count
    count_factor = min(len(detections) / 8.0, 1.0)
    risk_raw = 1.0 + 4.0 * severity * conf * (0.55 + 0.45 * count_factor)
    defect_risk = _clamp_stars(risk_raw)

    # Overall score mirrors mockup (higher is better)
    overall = int(
        np.clip(
            100
            - 55 * severity * conf
            - 8 * max(0, 5 - size_stars)
            - 6 * max(0, 5 - shape_stars)
            - 5 * max(0, 5 - position_stars),
            8,
            98,
        )
    )

    # Class-specific nudges to match expected UI examples
    if defect == "inconsistent_size":
        size_stars = min(size_stars, 4.0)
        position_stars = min(position_stars, 2.5)
        defect_risk = max(defect_risk, 2.0)
        overall = min(overall, 82)

    return {
        "overall_quality_score": overall,
        "shape_consistency": shape_stars,
        "size_consistency": size_stars,
        "dispensing_position": position_stars,
        "defect_risk": defect_risk,
        "defect_class": defect,
        "defect_label": analysis.get("defect_label"),
        "confidence": conf,
        "detection_count": len(detections),
    }
