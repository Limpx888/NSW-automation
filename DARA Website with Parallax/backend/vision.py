"""YOLO segmentation inference for solder-paste defect detection."""

from __future__ import annotations

import base64
from functools import lru_cache
from typing import Any

import cv2
import numpy as np

from backend.config import get_settings

# Model class id → internal label (matches best (2).pt names)
CLASS_LABELS = {
    0: "too_little",
    1: "too_much",
    2: "inconsistent_size",
    3: "missing_dot",
    4: "spreading",
    5: "air_bubble",
}

DISPLAY_LABELS = {
    "too_little": "UNDER DISPENSE",
    "too_much": "OVER DISPENSE",
    "inconsistent_size": "INCONSISTENT DISPENSING VOLUME",
    "missing_dot": "MISSING DOT",
    "spreading": "SPREADING",
    "air_bubble": "AIR BUBBLE / IRREGULAR",
}

# Distinct BGR colors per class for bounding boxes
BOX_COLORS = {
    "too_little": (214, 106, 44),
    "too_much": (80, 80, 220),
    "inconsistent_size": (11, 104, 115),
    "missing_dot": (40, 40, 40),
    "spreading": (242, 166, 90),
    "air_bubble": (76, 175, 80),
}

_MODEL = None
_MODEL_ERROR: str | None = None


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Upload a JPEG or PNG.")
    return img


def encode_image_b64(bgr: np.ndarray, ext: str = ".jpg") -> str:
    ok, buf = cv2.imencode(ext, bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise ValueError("Failed to encode annotated image")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def load_model():
    """Load Ultralytics YOLO checkpoint once."""
    global _MODEL, _MODEL_ERROR
    if _MODEL is not None:
        return _MODEL

    settings = get_settings()
    path = settings.model_path
    if not path.exists():
        _MODEL_ERROR = f"Model not found at {path}"
        return None

    try:
        from ultralytics import YOLO

        _MODEL = YOLO(str(path))
        _MODEL_ERROR = None
        return _MODEL
    except Exception as exc:  # noqa: BLE001 — surface load failures to /meta
        _MODEL_ERROR = str(exc)
        return None


def model_status() -> dict[str, Any]:
    model = load_model()
    settings = get_settings()
    return {
        "ready": model is not None,
        "path": str(settings.model_path),
        "error": _MODEL_ERROR,
        "task": getattr(model, "task", None) if model else None,
        "classes": list(DISPLAY_LABELS.values()),
        "labels": CLASS_LABELS,
    }


def _xyxy_to_box(xyxy: np.ndarray) -> dict[str, float]:
    x1, y1, x2, y2 = [float(v) for v in xyxy]
    return {
        "x1": round(x1, 2),
        "y1": round(y1, 2),
        "x2": round(x2, 2),
        "y2": round(y2, 2),
        "width": round(x2 - x1, 2),
        "height": round(y2 - y1, 2),
        "cx": round((x1 + x2) / 2, 2),
        "cy": round((y1 + y2) / 2, 2),
    }


def _draw_detections(bgr: np.ndarray, detections: list[dict[str, Any]]) -> np.ndarray:
    out = bgr.copy()
    for det in detections:
        box = det["box"]
        label = det["label"]
        color = BOX_COLORS.get(label, (11, 104, 115))
        # OpenCV uses BGR; our palette is RGB-ish — convert
        bgr_color = (color[2], color[1], color[0])
        pt1 = (int(box["x1"]), int(box["y1"]))
        pt2 = (int(box["x2"]), int(box["y2"]))
        cv2.rectangle(out, pt1, pt2, bgr_color, 2)

        caption = f"{det['display_label']} {det['confidence']:.0%}"
        (tw, th), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        y_text = max(pt1[1] - 6, th + 4)
        cv2.rectangle(out, (pt1[0], y_text - th - 6), (pt1[0] + tw + 6, y_text + 2), bgr_color, -1)
        cv2.putText(
            out,
            caption,
            (pt1[0] + 3, y_text - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        # Optional segmentation mask overlay
        mask = det.get("mask")
        if mask is not None:
            overlay = out.copy()
            overlay[mask > 0] = (
                (0.55 * np.array(bgr_color) + 0.45 * overlay[mask > 0]).astype(np.uint8)
            )
            out = cv2.addWeighted(overlay, 0.45, out, 0.55, 0)
            # re-draw box after blend for crisp edges
            cv2.rectangle(out, pt1, pt2, bgr_color, 2)

    return out


def analyze_image(bgr: np.ndarray) -> dict[str, Any]:
    """Run YOLO segmentation and return detections + annotated preview."""
    model = load_model()
    settings = get_settings()
    h, w = bgr.shape[:2]

    if model is None:
        raise RuntimeError(_MODEL_ERROR or "YOLO model is not loaded")

    results = model.predict(
        source=bgr,
        conf=settings.yolo_conf,
        iou=settings.yolo_iou,
        verbose=False,
    )
    result = results[0]
    names = result.names or CLASS_LABELS

    detections: list[dict[str, Any]] = []
    if result.boxes is not None and len(result.boxes):
        boxes_xyxy = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        clss = result.boxes.cls.cpu().numpy().astype(int)
        masks_data = None
        if result.masks is not None and result.masks.data is not None:
            masks_data = result.masks.data.cpu().numpy()

        for i, (xyxy, conf, cls_id) in enumerate(zip(boxes_xyxy, confs, clss)):
            raw_name = names.get(int(cls_id), CLASS_LABELS.get(int(cls_id), str(cls_id)))
            label = raw_name if raw_name in DISPLAY_LABELS else CLASS_LABELS.get(int(cls_id), raw_name)
            det: dict[str, Any] = {
                "id": i,
                "class_id": int(cls_id),
                "label": label,
                "display_label": DISPLAY_LABELS.get(label, label.replace("_", " ").upper()),
                "confidence": round(float(conf), 4),
                "box": _xyxy_to_box(xyxy),
            }
            if masks_data is not None and i < len(masks_data):
                mask = masks_data[i]
                if mask.shape[:2] != (h, w):
                    mask = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
                det["mask"] = (mask > 0.5).astype(np.uint8)
            detections.append(det)

    # Primary defect = highest confidence, else majority vote
    if detections:
        primary = max(detections, key=lambda d: d["confidence"])
        counts: dict[str, int] = {}
        for d in detections:
            counts[d["label"]] = counts.get(d["label"], 0) + 1
        majority_label = max(counts, key=counts.get)
        if counts[majority_label] > 1:
            primary = next(d for d in detections if d["label"] == majority_label)
        primary_label = primary["label"]
        primary_display = primary["display_label"]
        primary_conf = primary["confidence"]
    else:
        primary_label = "no_defect_detected"
        primary_display = "NO DEFECT DETECTED"
        primary_conf = 1.0

    annotated = _draw_detections(bgr, detections)
    # Strip mask arrays before JSON serialization
    serializable = []
    for d in detections:
        item = {k: v for k, v in d.items() if k != "mask"}
        serializable.append(item)

    return {
        "method": "yolo_seg",
        "image_size": {"width": w, "height": h},
        "detection_count": len(serializable),
        "defect_class": primary_label,
        "defect_label": primary_display,
        "confidence": round(float(primary_conf), 4),
        "detections": serializable,
        "annotated_image_base64": encode_image_b64(annotated),
        "annotated_image_mime": "image/jpeg",
    }
