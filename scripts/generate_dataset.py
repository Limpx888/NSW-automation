"""Generate the labeled synthetic dispensing dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.synthesize import generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "data" / "synthetic"))
    parser.add_argument("--per-combo", type=int, default=48)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--preview", default=str(ROOT / "data" / "samples"))
    args = parser.parse_args()
    summary = generate_dataset(
        Path(args.out),
        per_combo=args.per_combo,
        seed=args.seed,
        preview_dir=Path(args.preview),
    )
    md = ROOT / "data" / "dataset_summary.md"
    lines = [
        "# Dataset summary",
        "",
        "Synthetic top-down dispense images. Labels are ground truth from the generator, not hand-annotated photos.",
        "",
        f"- Total images: **{summary['total']}**",
        f"- Split: train {summary['by_split'].get('train', 0)} / val {summary['by_split'].get('val', 0)} / test {summary['by_split'].get('test', 0)} (70/15/15, stratified by defect class)",
        f"- Image size: {summary['image_size']}×{summary['image_size']}",
        "",
        "## By defect class",
    ]
    for k, v in summary["by_defect_class"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## By material"]
    for k, v in summary["by_material"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## By pattern"]
    for k, v in summary["by_pattern"].items():
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "## How it was made",
        "OpenCV procedural shapes (dot, line, dam-and-fill) on PCB green / ceramic / metal backgrounds.",
        "Material textures: grainy solder paste, metallic silver epoxy, translucent UV glue, soft-edge silicone.",
        "Defects: shrink/enlarge, skip, multi-deposit variance, bleed, punched voids + satellites.",
        "Augmentation baked in: brightness, blur, noise, rotation, slight perspective warp.",
        "",
        "Real photos belong in `data/real/` and are a validation set, not the training set.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(summary)
    print("wrote", md)


if __name__ == "__main__":
    main()
