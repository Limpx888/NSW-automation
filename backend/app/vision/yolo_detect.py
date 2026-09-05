"""YOLOv8 defect detector using the team's best (1).pt checkpoint.

Returns bounding boxes with class label + confidence, plus an annotated image
(same visual style as Ultralytics results[0].plot() in Colab).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_YOLO_CKPT = ROOT / "model" / "checkpoints" / "yolo_best.pt"
# Prefer the file the user keeps at repo root if present
ROOT_ALIAS = ROOT / "best (1).pt"

# Map PCB YOLO labels → dispensing ranking vocabulary used by cause engine
YOLO_TO_DISPENSE = {
    "missing_hole": "missing",
    "mouse_bite": "air_bubble_irregular",
    "open_circuit": "missing",
    "short": "spreading",
    "spur": "air_bubble_irregular",
    "spurious_copper": "over_dispense",
}

_YOLO = None


def resolve_yolo_path(ckpt_path: Path | None = None) -> Path | None:
    if ckpt_path and Path(ckpt_path).exists():
        return Path(ckpt_path)
    if DEFAULT_YOLO_CKPT.exists():
        return DEFAULT_YOLO_CKPT
    if ROOT_ALIAS.exists():
        return ROOT_ALIAS
    return None


def load_yolo(ckpt_path: Path | None = None):
    global _YOLO
    if _YOLO is not None:
        return _YOLO
    path = resolve_yolo_path(ckpt_path)
    if path is None:
        return None
    from ultralytics import YOLO

    _YOLO = YOLO(str(path))
    return _YOLO


def yolo_ready() -> bool:
    return resolve_yolo_path() is not None


def _encode_png_b64(bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise ValueError("Could not encode annotated image")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def detect_yolo(
    bgr: np.ndarray,
    *,
    conf: float = 0.25,
    iou: float = 0.45,
    ckpt_path: Path | None = None,
) -> dict[str, Any]:
    """Run YOLO detection and return boxes + Colab-style annotated frame."""
    model = load_yolo(ckpt_path)
    if model is None:
        return {
            "method": "yolo",
            "available": False,
            "detections": [],
            "defect_class": None,
            "confidence": 0.0,
            "annotated_image_b64": None,
            "class_counts": {},
        }

    # Ultralytics accepts BGR ndarray; plot() returns BGR annotated image
    results = model.predict(source=bgr, conf=conf, iou=iou, verbose=False)
    result = results[0]
    names = result.names or getattr(model, "names", {}) or {}

    detections: list[dict[str, Any]] = []
    class_counts: dict[str, int] = {}
    if result.boxes is not None and len(result.boxes):
        xyxy = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        clss = result.boxes.cls.cpu().numpy().astype(int)
        for box, score, cls_id in zip(xyxy, confs, clss):
            label = str(names.get(int(cls_id), cls_id))
            x1, y1, x2, y2 = [float(v) for v in box]
            detections.append(
                {
                    "class": label,
                    "confidence": round(float(score), 3),
                    "bbox": {
                        "x1": round(x1, 1),
                        "y1": round(y1, 1),
                        "x2": round(x2, 1),
                        "y2": round(y2, 1),
                    },
                    "dispense_class": YOLO_TO_DISPENSE.get(label),
                }
            )
            class_counts[label] = class_counts.get(label, 0) + 1

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    top = detections[0] if detections else None
    mapped = YOLO_TO_DISPENSE.get(top["class"]) if top else None

    annotated = result.plot()  # BGR with boxes + class + confidence
    return {
        "method": "yolo",
        "available": True,
        "detections": detections,
        "detection_count": len(detections),
        "class_counts": class_counts,
        "defect_class": mapped or (top["class"] if top else None),
        "yolo_class": top["class"] if top else None,
        "confidence": top["confidence"] if top else 0.0,
        "annotated_image_b64": _encode_png_b64(annotated),
        "classes": list(names.values()) if isinstance(names, dict) else list(names),
    }
