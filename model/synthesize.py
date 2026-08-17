"""Synthetic dispensing images: 3 patterns x 4 materials x 6 defects."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from model.classes import BACKGROUNDS, DEFECT_CLASSES, MATERIALS, PATTERNS, PATTERN_NAMES

SIZE = 224


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def make_background(rng: np.random.Generator, kind: str | None = None) -> np.ndarray:
    kind = kind or str(rng.choice(BACKGROUNDS))
    h = w = SIZE
    if kind == "pcb":
        base = np.array([38, 118, 52], dtype=np.float32)
        img = np.full((h, w, 3), base, dtype=np.float32)
        img += rng.normal(0, 4.5, img.shape)
        for _ in range(int(rng.integers(4, 9))):
            x1 = int(rng.integers(0, w))
            y1 = int(rng.integers(0, h))
            thick = int(rng.integers(2, 6))
            color = (20, 90 + int(rng.integers(0, 40)), 160)
            if rng.random() < 0.5:
                cv2.line(img, (0, y1), (w, y1), color, thick)
            else:
                cv2.line(img, (x1, 0), (x1, h), color, thick)
        for _ in range(int(rng.integers(3, 8))):
            cx, cy = int(rng.integers(20, w - 20)), int(rng.integers(20, h - 20))
            r = int(rng.integers(6, 14))
            cv2.circle(img, (cx, cy), r, (18, 70, 140), -1)
            cv2.circle(img, (cx, cy), max(2, r - 3), (30, 100, 45), -1)
    elif kind == "ceramic":
        img = np.full((h, w, 3), [228, 226, 220], dtype=np.float32)
        img += rng.normal(0, 3.0, img.shape)
        speckle = rng.random((h, w)) < 0.012
        img[speckle] = img[speckle] * 0.7
    else:
        img = np.full((h, w, 3), [118, 118, 122], dtype=np.float32)
        yy = np.linspace(0, 1, h)[:, None]
        img += (yy * 18)[..., None]
        brush = rng.normal(0, 7, (h, 1, 1)) + rng.normal(0, 2, (h, w, 1))
        img += brush
    return np.clip(img, 0, 255).astype(np.uint8), kind


def _soft_mask(mask: np.ndarray, ksize: int = 5) -> np.ndarray:
    k = ksize if ksize % 2 == 1 else ksize + 1
    return cv2.GaussianBlur(mask, (k, k), 0)


def _dot_mask(defect: str, rng: np.random.Generator) -> np.ndarray:
    mask = np.zeros((SIZE, SIZE), np.uint8)
    cx = int(rng.integers(80, 145))
    cy = int(rng.integers(80, 145))
    if defect == "missing":
        cv2.circle(mask, (cx, cy), int(rng.integers(16, 24)), 40, 2)
        if rng.random() < 0.25:
            cv2.circle(mask, (cx, cy), 3, 90, -1)
        return mask
    if defect == "under_dispense":
        cv2.circle(mask, (cx, cy), int(rng.integers(8, 15)), 255, -1)
    elif defect == "over_dispense":
        cv2.circle(mask, (cx, cy), int(rng.integers(40, 54)), 255, -1)
    elif defect == "inconsistent_volume":
        for dx, dy in ((-36, -32), (38, -28), (-34, 36), (36, 34), (0, 0)):
            r = int(rng.integers(6, 28))
            cv2.circle(mask, (cx + dx, cy + dy), r, 255, -1)
    elif defect == "spreading":
        axes = (int(rng.integers(42, 58)), int(rng.integers(28, 48)))
        cv2.ellipse(mask, (cx, cy), axes, int(rng.integers(0, 180)), 0, 360, 200, -1)
        for _ in range(int(rng.integers(2, 5))):
            px = cx + int(rng.integers(-50, 51))
            py = cy + int(rng.integers(-50, 51))
            cv2.circle(mask, (px, py), int(rng.integers(4, 12)), 160, -1)
        mask = _soft_mask(mask, 11)
    else:
        cv2.circle(mask, (cx, cy), int(rng.integers(22, 34)), 255, -1)
        hole = (cx + int(rng.integers(-8, 9)), cy + int(rng.integers(-8, 9)))
        cv2.circle(mask, hole, int(rng.integers(5, 10)), 0, -1)
        for _ in range(int(rng.integers(2, 5))):
            cv2.circle(
                mask,
                (cx + int(rng.integers(-48, 49)), cy + int(rng.integers(-48, 49))),
                int(rng.integers(2, 6)),
                220,
                -1,
            )
    return mask


def _line_mask(defect: str, rng: np.random.Generator) -> np.ndarray:
    mask = np.zeros((SIZE, SIZE), np.uint8)
    x1, y1 = int(rng.integers(24, 50)), int(rng.integers(70, 150))
    x2, y2 = int(rng.integers(170, 205)), y1 + int(rng.integers(-40, 41))
    if defect == "missing":
        cv2.line(mask, (x1, y1), (x1 + 50, y1), 255, 8)
        cv2.line(mask, (x2 - 45, y2), (x2, y2), 255, 8)
        return mask
    if defect == "under_dispense":
        cv2.line(mask, (x1, y1), (x2, y2), 255, int(rng.integers(3, 7)))
        if rng.random() < 0.5:
            mid = ((x1 + x2) // 2, (y1 + y2) // 2)
            cv2.circle(mask, mid, 8, 0, -1)
    elif defect == "over_dispense":
        cv2.line(mask, (x1, y1), (x2, y2), 255, int(rng.integers(16, 26)))
    elif defect == "inconsistent_volume":
        pts = np.linspace(0, 1, 8)
        last = (x1, y1)
        for t in pts[1:]:
            p = (int(x1 + t * (x2 - x1)), int(y1 + t * (y2 - y1)))
            cv2.line(mask, last, p, 255, int(rng.integers(3, 22)))
            last = p
    elif defect == "spreading":
        cv2.line(mask, (x1, y1), (x2, y2), 180, int(rng.integers(18, 30)))
        mask = _soft_mask(mask, 15)
        for _ in range(3):
            cv2.circle(
                mask,
                (int(rng.integers(x1, x2)), y1 + int(rng.integers(-18, 19))),
                int(rng.integers(6, 14)),
                140,
                -1,
            )
    else:
        cv2.line(mask, (x1, y1), (x2, y2), 255, 10)
        for t in (0.3, 0.55, 0.75):
            px = int(x1 + t * (x2 - x1))
            py = int(y1 + t * (y2 - y1))
            cv2.circle(mask, (px, py), int(rng.integers(3, 6)), 0, -1)
        cv2.circle(mask, (x1 + 20, y1 - 18), 4, 230, -1)
    return mask


def _dam_mask(defect: str, rng: np.random.Generator) -> np.ndarray:
    mask = np.zeros((SIZE, SIZE), np.uint8)
    m = int(rng.integers(36, 52))
    x1, y1, x2, y2 = m, m, SIZE - m, SIZE - m
    wall = int(rng.integers(7, 12))
    if defect == "missing":
        cv2.rectangle(mask, (x1, y1), (x2, y2), 70, 2)
        return mask
    if defect == "under_dispense":
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, max(3, wall - 4))
        cv2.rectangle(mask, (x1 + wall + 8, y1 + wall + 8), (x2 - 40, y2 - wall - 8), 160, -1)
    elif defect == "over_dispense":
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, wall + 4)
        cv2.rectangle(mask, (x1 + wall, y1 + wall), (x2 - wall, y2 - wall), 200, -1)
        cv2.circle(mask, (x2 + 6, (y1 + y2) // 2), 16, 190, -1)
    elif defect == "inconsistent_volume":
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, wall)
        cv2.rectangle(mask, (x1, y1), (x1 + 40, y2), 255, wall + 6)
        cv2.rectangle(mask, (x1 + wall, y1 + wall), (x2 - wall, y2 - wall), 140, -1)
        cv2.rectangle(mask, (x1 + wall, y1 + wall), ((x1 + x2) // 2, y2 - wall), 220, -1)
    elif defect == "spreading":
        cv2.rectangle(mask, (x1, y1), (x2, y2), 180, wall)
        cv2.rectangle(mask, (x2 - 8, y1 + 20), (x2 + 28, y2 - 20), 0, -1)
        spill = mask.copy()
        cv2.ellipse(spill, (x2 + 10, (y1 + y2) // 2), (28, 40), 0, 0, 360, 170, -1)
        mask = _soft_mask(cv2.max(mask, spill), 9)
    else:
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, wall)
        cv2.rectangle(mask, (x1 + wall, y1 + wall), (x2 - wall, y2 - wall), 200, -1)
        cv2.circle(mask, ((x1 + x2) // 2, (y1 + y2) // 2), int(rng.integers(10, 18)), 0, -1)
        cv2.circle(mask, (x1 + 24, y1 + 24), 5, 0, -1)
    return mask


def build_mask(pattern: str, defect: str, rng: np.random.Generator) -> np.ndarray:
    if pattern == "dot":
        return _dot_mask(defect, rng)
    if pattern == "line":
        return _line_mask(defect, rng)
    return _dam_mask(defect, rng)


def _material_layer(mask: np.ndarray, material: str, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    h, w = mask.shape
    alpha = (mask.astype(np.float32) / 255.0)
    yy, xx = np.ogrid[:h, :w]
    if material == "solder_paste":
        color = np.array([86, 90, 96], dtype=np.float32)
        grain = rng.normal(0, 11, (h, w))
        particles = (rng.random((h, w)) > 0.91).astype(np.float32) * 45
        rgb = color + grain[..., None] + particles[..., None]
        opacity = 0.93
    elif material == "silver_epoxy":
        color = np.array([168, 170, 176], dtype=np.float32)
        sheen = 38 * np.clip(np.cos((xx + yy) / 16.0), 0, 1)
        rgb = color + sheen[..., None] + rng.normal(0, 6, (h, w, 1))
        opacity = 0.9
    elif material == "uv_glue":
        color = np.array([190, 210, 160], dtype=np.float32)
        rgb = color + rng.normal(0, 4, (h, w, 1))
        gloss = np.exp(-((xx - w * 0.4) ** 2 + (yy - h * 0.35) ** 2) / (2 * 28**2)) * 70
        rgb = rgb + gloss[..., None]
        opacity = 0.55
        alpha = cv2.GaussianBlur(alpha, (7, 7), 0)
    else:
        color = np.array([170, 200, 210], dtype=np.float32)
        rgb = color + rng.normal(0, 5, (h, w, 1))
        opacity = 0.62
        alpha = cv2.GaussianBlur(alpha, (11, 11), 0)
    rgb = np.clip(rgb, 0, 255)
    return rgb, np.clip(alpha * opacity, 0, 1)


def composite(bg: np.ndarray, mask: np.ndarray, material: str, rng: np.random.Generator) -> np.ndarray:
    rgb, alpha = _material_layer(mask, material, rng)
    a = alpha[..., None]
    out = bg.astype(np.float32) * (1 - a) + rgb * a
    return np.clip(out, 0, 255).astype(np.uint8)


def augment(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = img.astype(np.float32)
    if rng.random() < 0.8:
        out = np.clip(out * float(rng.uniform(0.72, 1.28)) + float(rng.uniform(-12, 12)), 0, 255)
    if rng.random() < 0.45:
        k = int(rng.choice([3, 5]))
        out = cv2.GaussianBlur(out, (k, k), 0)
    if rng.random() < 0.7:
        out = np.clip(out + rng.normal(0, float(rng.uniform(2, 8)), out.shape), 0, 255)
    if rng.random() < 0.6:
        angle = float(rng.uniform(-18, 18))
        m = cv2.getRotationMatrix2D((SIZE / 2, SIZE / 2), angle, float(rng.uniform(0.92, 1.08)))
        out = cv2.warpAffine(out, m, (SIZE, SIZE), borderMode=cv2.BORDER_REFLECT_101)
    if rng.random() < 0.35:
        src = np.float32([[0, 0], [SIZE, 0], [0, SIZE], [SIZE, SIZE]])
        jitter = rng.uniform(-12, 12, (4, 2)).astype(np.float32)
        dst = src + jitter
        m = cv2.getPerspectiveTransform(src, dst)
        out = cv2.warpPerspective(out, m, (SIZE, SIZE), borderMode=cv2.BORDER_REFLECT_101)
    return np.clip(out, 0, 255).astype(np.uint8)


def render_image(
    defect: str,
    material: str,
    pattern: str,
    seed: int,
    background: str | None = None,
    do_augment: bool = True,
) -> tuple[np.ndarray, str]:
    rng = _rng(seed)
    bg, bg_kind = make_background(rng, background)
    mask = build_mask(pattern, defect, rng)
    img = composite(bg, mask, material, rng)
    if do_augment:
        img = augment(img, rng)
    return img, bg_kind


def _assign_splits(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    n_train = int(round(n * 0.70))
    n_val = int(round(n * 0.15))
    labels = ["train"] * n_train + ["val"] * n_val + ["test"] * (n - n_train - n_val)
    rng.shuffle(labels)
    return labels


def generate_dataset(
    out_dir: Path,
    per_combo: int = 48,
    seed: int = 42,
    preview_dir: Path | None = None,
) -> dict:
    out_dir = Path(out_dir)
    for split in ("train", "val", "test"):
        (out_dir / split).mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    image_id = 0
    for defect in DEFECT_CLASSES:
        splits = _assign_splits(
            per_combo * len(MATERIALS) * len(PATTERNS),
            seed + 17 * DEFECT_CLASSES.index(defect),
        )
        local = 0
        for material in MATERIALS:
            for pattern in PATTERNS:
                for _k in range(per_combo):
                    image_id += 1
                    split = splits[local]
                    local += 1
                    img_seed = seed * 100000 + image_id
                    img, bg_kind = render_image(defect, material, pattern, img_seed)
                    name = f"{defect}__{material}__{pattern}__{image_id:05d}.png"
                    rel = f"{split}/{name}"
                    cv2.imwrite(str(out_dir / rel), img)
                    rows.append(
                        {
                            "filename": rel,
                            "split": split,
                            "defect_class": defect,
                            "material_type": material,
                            "pattern_type": pattern,
                            "background": bg_kind,
                            "pattern_specific_name": PATTERN_NAMES[defect][pattern],
                        }
                    )

    labels_path = out_dir / "labels.csv"
    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize(rows)
    (out_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if preview_dir:
        write_preview(preview_dir, seed=seed + 999)

    return summary


def summarize(rows: list[dict]) -> dict:
    by_defect = Counter(r["defect_class"] for r in rows)
    by_split = Counter(r["split"] for r in rows)
    by_material = Counter(r["material_type"] for r in rows)
    by_pattern = Counter(r["pattern_type"] for r in rows)
    return {
        "total": len(rows),
        "by_split": dict(by_split),
        "by_defect_class": dict(by_defect),
        "by_material": dict(by_material),
        "by_pattern": dict(by_pattern),
        "image_size": SIZE,
    }


def write_preview(preview_dir: Path, seed: int = 1) -> None:
    """Small gallery: one of each defect x pattern (solder paste) plus a few other materials."""
    preview_dir = Path(preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)
    i = 0
    for defect in DEFECT_CLASSES:
        for pattern in PATTERNS:
            i += 1
            img, _ = render_image(defect, "solder_paste", pattern, seed + i, do_augment=False)
            cv2.imwrite(str(preview_dir / f"{defect}__solder_paste__{pattern}.png"), img)
    for j, material in enumerate(MATERIALS):
        img, _ = render_image(
            "inconsistent_volume", material, "dot", seed + 200 + j, do_augment=False
        )
        cv2.imwrite(str(preview_dir / f"inconsistent_volume__{material}__dot.png"), img)
