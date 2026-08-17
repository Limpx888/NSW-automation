"""Defect classifier: MobileNetV2 checkpoint with an OpenCV heuristic fallback."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision import transforms

from model.classes import DEFECT_CLASSES
from model.train import IMAGENET_MEAN, IMAGENET_STD, build_model

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CKPT = ROOT / "model" / "checkpoints" / "best.pt"

_MODEL = None
_DEVICE = None
_TF = transforms.Compose(
    [
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ]
)


def _device() -> torch.device:
    global _DEVICE
    if _DEVICE is None:
        _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return _DEVICE


def load_model(ckpt_path: Path | None = None):
    global _MODEL
    path = Path(ckpt_path) if ckpt_path else DEFAULT_CKPT
    if _MODEL is not None:
        return _MODEL
    if not path.exists():
        return None
    model = build_model()
    ckpt = torch.load(path, map_location=_device(), weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    model.to(_device())
    model.eval()
    _MODEL = model
    return _MODEL


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img


def heuristic_predict(bgr: np.ndarray) -> dict:
    """Cheap geometry fallback so /predict works before a checkpoint exists."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    corners = np.concatenate(
        [gray[:12, :12].ravel(), gray[:12, -12:].ravel(), gray[-12:, :12].ravel(), gray[-12:, -12:].ravel()]
    )
    bg = float(np.median(corners))
    fg = (np.abs(gray.astype(np.float32) - bg) > 28).astype(np.uint8) * 255
    fg = cv2.medianBlur(fg, 5)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ratio = float(fg.mean() / 255.0)
    contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) > 20]
    n = len(contours)
    areas = [cv2.contourArea(c) for c in contours] or [0]
    if ratio < 0.008 or n == 0:
        label = "missing"
    elif n >= 3 and (max(areas) / (np.mean(areas) + 1e-6) > 2.2):
        label = "inconsistent_volume"
    elif n >= 1:
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        peri = cv2.arcLength(c, True) + 1e-6
        circularity = 4 * np.pi * area / (peri * peri)
        x, y, bw, bh = cv2.boundingRect(c)
        fill = area / (bw * bh + 1e-6)
        holes = cv2.findContours(255 - fg, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)[0]
        if circularity < 0.45 and n > 1:
            label = "air_bubble_irregular"
        elif fill < 0.45 and ratio > 0.08:
            label = "spreading"
        elif ratio > 0.16:
            label = "over_dispense"
        elif ratio < 0.035:
            label = "under_dispense"
        elif circularity < 0.55:
            label = "air_bubble_irregular"
        else:
            label = "under_dispense" if ratio < 0.07 else "over_dispense"
        _ = holes
    else:
        label = "missing"

    conf = float(np.clip(0.42 + min(ratio, 0.2), 0.35, 0.72))
    probs = {c: (conf if c == label else (1 - conf) / 5) for c in DEFECT_CLASSES}
    return {
        "defect_class": label,
        "confidence": round(conf, 3),
        "probs": probs,
        "method": "heuristic",
    }


def model_predict(bgr: np.ndarray) -> dict | None:
    model = load_model()
    if model is None:
        return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    tensor = _TF(rgb).unsqueeze(0).to(_device())
    with torch.no_grad():
        logits = model(tensor)
        probs_t = torch.softmax(logits, dim=1)[0]
    probs = {DEFECT_CLASSES[i]: float(probs_t[i]) for i in range(len(DEFECT_CLASSES))}
    idx = int(probs_t.argmax().item())
    return {
        "defect_class": DEFECT_CLASSES[idx],
        "confidence": round(float(probs_t[idx]), 3),
        "probs": probs,
        "method": "mobilenetv2",
    }


def predict_image(bgr: np.ndarray) -> dict:
    result = model_predict(bgr)
    if result is None:
        result = heuristic_predict(bgr)
    return result


def quality_assessment(defect_class: str, confidence: float) -> dict:
    severity = {
        "missing": 0.85,
        "spreading": 0.7,
        "over_dispense": 0.62,
        "under_dispense": 0.58,
        "inconsistent_volume": 0.65,
        "air_bubble_irregular": 0.6,
    }[defect_class]
    overall = int(np.clip(100 - 80 * severity * confidence, 8, 96))
    stars = lambda s: int(np.clip(round(s), 1, 5))
    return {
        "overall_quality_score": overall,
        "shape_consistency": stars(5 - 3 * severity),
        "size_consistency": stars(5 - 2.5 * severity),
        "defect_risk": stars(1 + 4 * severity * confidence),
        "defect_class": defect_class,
        "confidence": confidence,
    }
