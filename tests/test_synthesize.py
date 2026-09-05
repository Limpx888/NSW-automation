from pathlib import Path

from model.classes import DEFECT_CLASSES, MATERIALS, PATTERNS
from model.synthesize import generate_dataset, render_image


def test_render_every_combo():
    for defect in DEFECT_CLASSES:
        for material in MATERIALS:
            for pattern in PATTERNS:
                img, bg = render_image(defect, material, pattern, seed=7, do_augment=False)
                assert img.shape == (224, 224, 3), (defect, material, pattern)
                assert bg in {"pcb", "ceramic", "metal"}


def test_generate_tiny_dataset(tmp_path: Path):
    summary = generate_dataset(tmp_path, per_combo=1, seed=1, preview_dir=tmp_path / "preview")
    assert summary["total"] == len(DEFECT_CLASSES) * len(MATERIALS) * len(PATTERNS)
    assert (tmp_path / "labels.csv").exists()
    assert summary["by_split"]["train"] + summary["by_split"]["val"] + summary["by_split"]["test"] == summary["total"]
    assert any((tmp_path / "preview").glob("*.png"))
