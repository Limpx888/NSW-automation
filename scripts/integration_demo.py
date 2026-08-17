"""End-to-end demo smoke test — run before judging."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.synthesize import render_image, write_preview

from backend.app.db.cases import seed_if_empty, similar_cases
from backend.app.pipeline import run_session
from backend.app.reports.pdf import build_pdf
from backend.app.vision.predict import load_model, predict_image

SCENARIOS = [
    {
        "name": "T6 fine nozzle under-dispense",
        "answers": {
            "material": "solder_paste",
            "pattern": "dot",
            "amount": "too_small",
            "frequency": "continuous",
            "recent_change": "nozzle",
            "location": "multiple",
            "powder_type": "T6",
            "nozzle_id_um": 60,
        },
        "render": ("under_dispense", "solder_paste", "dot", 101),
        "expect_top": {"powder_nozzle_mismatch", "nozzle_partial_clog"},
    },
    {
        "name": "Occasional inconsistent T4",
        "answers": {
            "material": "solder_paste",
            "pattern": "dot",
            "amount": "inconsistent",
            "frequency": "occasional",
            "recent_change": "none",
            "location": "multiple",
            "powder_type": "T4",
        },
        "render": ("inconsistent_volume", "solder_paste", "dot", 202),
        "expect_top": {"air_trapped_syringe"},
    },
    {
        "name": "UV glue dam collapse",
        "answers": {
            "material": "uv_glue",
            "pattern": "dam_fill",
            "amount": "spreading",
            "frequency": "continuous",
            "recent_change": "none",
            "location": "multiple",
            "uv_barrel": "clear",
            "timing": "after_runtime",
        },
        "render": ("spreading", "uv_glue", "dam_fill", 303),
        "expect_top": {"viscosity_temp_humidity", "premature_uv_cure", "dam_flow_geometry", "pressure_time_high"},
    },
    {
        "name": "Silver epoxy not mixed",
        "answers": {
            "material": "silver_epoxy",
            "pattern": "dot",
            "amount": "inconsistent",
            "frequency": "continuous",
            "recent_change": "material",
            "location": "multiple",
            "mix_state": "no",
        },
        "render": ("inconsistent_volume", "silver_epoxy", "dot", 404),
        "expect_top": {"filler_settling", "air_trapped_syringe"},
    },
    {
        "name": "Silicone missing line segment",
        "answers": {
            "material": "silicone_gel",
            "pattern": "line",
            "amount": "missing",
            "frequency": "occasional",
            "recent_change": "none",
            "location": "single",
        },
        "render": ("missing", "silicone_gel", "line", 505),
        "expect_top": None,
    },
    {
        "name": "T5 over-dispense thick line",
        "answers": {
            "material": "solder_paste",
            "pattern": "line",
            "amount": "too_large",
            "frequency": "continuous",
            "recent_change": "settings",
            "location": "multiple",
            "powder_type": "T5",
        },
        "render": ("over_dispense", "solder_paste", "line", 606),
        "expect_top": {"pressure_time_high"},
    },
    {
        "name": "UV irregular bubble",
        "answers": {
            "material": "uv_glue",
            "pattern": "dot",
            "amount": "irregular",
            "frequency": "occasional",
            "recent_change": "none",
            "location": "multiple",
            "uv_barrel": "blocking",
        },
        "render": ("air_bubble_irregular", "uv_glue", "dot", 707),
        "expect_top": {"air_trapped_syringe", "piston_suckback"},
    },
    {
        "name": "Silicone dam void",
        "answers": {
            "material": "silicone_gel",
            "pattern": "dam_fill",
            "amount": "irregular",
            "frequency": "continuous",
            "recent_change": "none",
            "location": "multiple",
        },
        "render": ("air_bubble_irregular", "silicone_gel", "dam_fill", 808),
        "expect_top": {"air_trapped_syringe", "dam_flow_geometry"},
    },
]


def main() -> int:
    t0 = time.perf_counter()
    write_preview(ROOT / "data" / "samples", seed=42)
    seeded = seed_if_empty()
    model_ok = load_model() is not None
    print(f"seeded={seeded} model={'ok' if model_ok else 'heuristic-only'}")

    failures = []
    for i, sc in enumerate(SCENARIOS, start=1):
        img, _ = render_image(*sc["render"], do_augment=False)
        pred = predict_image(img)
        result = run_session(sc["answers"], image_bgr=img)
        pdf = build_pdf(result)
        top_id = result["ranked_causes"][0]["id"]
        if sc["expect_top"] and top_id not in sc["expect_top"]:
            failures.append(f"{sc['name']}: expected one of {sc['expect_top']}, got {top_id}")
        similar = similar_cases(result["material"], result["defect_class"])
        print(
            f"[{i}/{len(SCENARIOS)}] {sc['name']}: "
            f"vision={pred['defect_class']}({pred['confidence']:.0%}) "
            f"ranked={top_id} pdf={len(pdf)}B similar={similar['total']}"
        )

    elapsed = time.perf_counter() - t0
    print(f"Completed {len(SCENARIOS)} sessions in {elapsed:.1f}s ({elapsed / len(SCENARIOS):.1f}s each)")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("All integration checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
