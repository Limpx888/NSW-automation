"""YOLO multi-model ensemble inference for solder-paste and PCB defect detection."""

from __future__ import annotations

import base64
from typing import Any

import cv2
import numpy as np

from backend.config import get_settings

# Normalization mapping for defect labels across models
LABEL_NORMALIZATION = {
    # Primary defect detector (defect_detector.pt) — deploy_config.json classes
    "missing_void": "missing_void",
    "oversized": "oversized",
    "undersized": "undersized",
    "irregular_shape": "irregular_shape",
    "excessive_spreading": "excessive_spreading",

    # Pattern classifier (pattern_classifier.pt) — pattern types
    "micro_bump": "micro_bump",
    "micro_lines": "micro_lines",
    "micro_dam": "micro_dam",
    "micro_cavity": "micro_cavity",

    # Legacy dispense labels (kept for backward compat with old models/records)
    "too_little": "undersized",
    "too_much": "oversized",
    "inconsistent_size": "irregular_shape",
    "missing_dot": "missing_void",
    "spreading": "excessive_spreading",
    "air_bubble": "irregular_shape",

    # Legacy PCB-AOI labels
    "missing_hole": "missing_void",
    "mouse_bite": "irregular_shape",
    "open_circuit": "missing_void",
    "short": "oversized",
    "spur": "irregular_shape",
    "spurious_copper": "excessive_spreading",
}

DISPLAY_LABELS = {
    # New deploy classes
    "missing_void": "MISSING / VOID DEPOSIT",
    "oversized": "OVER DISPENSE (OVERSIZED)",
    "undersized": "UNDER DISPENSE (UNDERSIZED)",
    "irregular_shape": "IRREGULAR SHAPE",
    "excessive_spreading": "EXCESSIVE SPREADING",
    # Pattern types
    "micro_bump": "MICRO BUMP PATTERN",
    "micro_lines": "MICRO LINES PATTERN",
    "micro_dam": "MICRO DAM PATTERN",
    "micro_cavity": "MICRO CAVITY PATTERN",
    # Fallback
    "no_defect_detected": "NO DEFECT DETECTED",
}

# Distinct RGB colors per class (converted to BGR during rendering)
BOX_COLORS = {
    "missing_void": (40, 40, 40),
    "oversized": (80, 80, 220),
    "undersized": (214, 106, 44),
    "irregular_shape": (76, 175, 80),
    "excessive_spreading": (242, 166, 90),
    "micro_bump": (11, 104, 115),
    "micro_lines": (180, 50, 150),
    "micro_dam": (230, 130, 30),
    "micro_cavity": (230, 30, 30),
}

_MODELS: dict[str, Any] = {}
_MODEL_ERRORS: dict[str, str] = {}


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


def load_models() -> dict[str, Any]:
    """Load all available Ultralytics YOLO checkpoints."""
    global _MODELS, _MODEL_ERRORS
    if _MODELS:
        return _MODELS

    settings = get_settings()
    model_configs = [
        ("defect_detector", settings.model_path),
        ("pattern_classifier", settings.dispense_model_path),
    ]
    # Only include pcb_aoi if a path is configured
    if settings.pcb_aoi_model_path is not None:
        model_configs.append(("pcb_aoi", settings.pcb_aoi_model_path))

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        _MODEL_ERRORS["import"] = f"Failed to import ultralytics: {exc}"
        return _MODELS

    for key, path in model_configs:
        if path and path.exists() and path.is_file():
            try:
                model = YOLO(str(path))
                _MODELS[key] = model
                if key in _MODEL_ERRORS:
                    del _MODEL_ERRORS[key]
            except Exception as exc:  # noqa: BLE001
                _MODEL_ERRORS[key] = str(exc)
        else:
            _MODEL_ERRORS[key] = f"Model file not found: {path}"

    return _MODELS


def load_model() -> Any:
    """Backward-compatible loader for the primary segmentation model."""
    models = load_models()
    return models.get("segmentation") or next(iter(models.values()), None)


def model_status() -> dict[str, Any]:
    models = load_models()
    settings = get_settings()
    loaded_names = {k: getattr(m, "names", {}) for k, m in models.items()}
    return {
        "ready": len(models) > 0,
        "loaded_models": list(models.keys()),
        "paths": {
            "defect_detector": str(settings.model_path),
            "pattern_classifier": str(settings.dispense_model_path),
        },
        "conf_threshold": settings.yolo_conf,
        "errors": _MODEL_ERRORS,
        "classes": list(DISPLAY_LABELS.values()),
        "model_classes": loaded_names,
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


def _box_iou(box1: dict[str, float], box2: dict[str, float]) -> float:
    """Compute Intersection over Union between two box dictionaries."""
    x1 = max(box1["x1"], box2["x1"])
    y1 = max(box1["y1"], box2["y1"])
    x2 = min(box1["x2"], box2["x2"])
    y2 = min(box1["y2"], box2["y2"])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection == 0.0:
        return 0.0

    area1 = max(0.0, box1["x2"] - box1["x1"]) * max(0.0, box1["y2"] - box1["y1"])
    area2 = max(0.0, box2["x2"] - box2["x1"]) * max(0.0, box2["y2"] - box2["y1"])
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0.0


def _apply_nms(detections: list[dict[str, Any]], iou_thresh: float = 0.5) -> list[dict[str, Any]]:
    """Deduplicate overlapping detections across multiple models."""
    if not detections:
        return []

    # Sort descending by confidence
    sorted_dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    kept: list[dict[str, Any]] = []

    for cand in sorted_dets:
        suppressed = False
        for k in kept:
            iou = _box_iou(cand["box"], k["box"])
            if iou > iou_thresh:
                # If candidate has a mask and kept doesn't, attach mask to kept
                if "mask" in cand and "mask" not in k:
                    k["mask"] = cand["mask"]
                suppressed = True
                break
        if not suppressed:
            kept.append(cand)

    # Re-index
    for idx, d in enumerate(kept):
        d["id"] = idx
    return kept


def _draw_detections(bgr: np.ndarray, detections: list[dict[str, Any]]) -> np.ndarray:
    out = bgr.copy()
    for det in detections:
        box = det["box"]
        label = det["label"]
        color = BOX_COLORS.get(label, (11, 104, 115))
        # OpenCV uses BGR; BOX_COLORS is RGB-ish -> convert
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
            # Re-draw box after blend for crisp edges
            cv2.rectangle(out, pt1, pt2, bgr_color, 2)

    return out


def analyze_image(bgr: np.ndarray) -> dict[str, Any]:
    """Run multi-model YOLO inference and return unified detections + annotated preview."""
    models = load_models()
    settings = get_settings()
    h, w = bgr.shape[:2]

    if not models:
        raise RuntimeError("No YOLO models loaded: " + str(_MODEL_ERRORS))

    raw_candidates: list[dict[str, Any]] = []

    for model_key, model in models.items():
        try:
            results = model.predict(
                source=bgr,
                conf=settings.yolo_conf,
                iou=settings.yolo_iou,
                verbose=False,
            )
            if not results:
                continue

            result = results[0]
            names = result.names or {}

            if result.boxes is not None and len(result.boxes):
                boxes_xyxy = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                clss = result.boxes.cls.cpu().numpy().astype(int)
                masks_data = None
                if result.masks is not None and result.masks.data is not None:
                    masks_data = result.masks.data.cpu().numpy()

                for i, (xyxy, conf, cls_id) in enumerate(zip(boxes_xyxy, confs, clss)):
                    raw_name = str(names.get(int(cls_id), str(cls_id))).strip()
                    lookup_key = raw_name.lower().replace(" ", "_").replace("-", "_")
                    label = LABEL_NORMALIZATION.get(lookup_key, lookup_key)
                    display_label = DISPLAY_LABELS.get(label, label.replace("_", " ").upper())

                    det: dict[str, Any] = {
                        "class_id": int(cls_id),
                        "raw_name": raw_name,
                        "model_source": model_key,
                        "label": label,
                        "display_label": display_label,
                        "confidence": round(float(conf), 4),
                        "box": _xyxy_to_box(xyxy),
                    }
                    if masks_data is not None and i < len(masks_data):
                        mask = masks_data[i]
                        if mask.shape[:2] != (h, w):
                            mask = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
                        det["mask"] = (mask > 0.5).astype(np.uint8)

                    raw_candidates.append(det)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: Model {model_key} inference failed: {exc}")

    # Deduplicate overlapping detections across models
    detections = _apply_nms(raw_candidates, iou_thresh=settings.yolo_iou)

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
        "method": "yolo_multi_ensemble",
        "loaded_models": list(models.keys()),
        "image_size": {"width": w, "height": h},
        "detection_count": len(serializable),
        "defect_class": primary_label,
        "defect_label": primary_display,
        "confidence": round(float(primary_conf), 4),
        "detections": serializable,
        "annotated_image_base64": encode_image_b64(annotated),
        "annotated_image_mime": "image/jpeg",
    }
