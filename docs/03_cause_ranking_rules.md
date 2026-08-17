# Day 2 deliverable — Cause-ranking rules

The engine is a **weighted table**, not a free-form LLM diagnosis. `research/cause_ranking_rules.json` is the source of truth. `backend/app/reasoning/rank_causes.py` applies it.

## How a score is built

1. Pick the **baseline** for `material × defect_class` (weights sum to 100).
2. If material is solder paste, apply **powder-type factors** (T3–T6) to clog / oxidation / spread causes, then renormalize.
3. If the user gave a nozzle ID, fire the **NSW 5× rule**: if `nozzle_id < 5 × d_max`, multiply `powder_nozzle_mismatch` and `nozzle_partial_clog`.
4. Apply **pattern multipliers** (dam-and-fill boosts flow geometry; dots stay default).
5. Apply every **Q&A adjustment rule** whose `when` matches.
6. Drop causes not allowed for this material, renormalize to 100%, sort descending.
7. Build the action plan by sorting remaining causes by `cost_rank` (cheap checks first), not by likelihood alone — then interleave so the top-likelihood cause is never buried.

The LLM (Day 10) receives `ranked_causes` + `fired_rules` and writes the paragraph. It does not vote.

## Solder paste Type 4 baseline (excerpt)

| Defect | Top causes (starting %) |
| --- | --- |
| Under-dispense | Partial clog 26, 5× nozzle mismatch 16, trapped air 14, low pressure/time 14 |
| Missing | Partial clog 30, 5× mismatch 18, trapped air 16 |
| Inconsistent volume | Trapped air 24, partial clog 18, viscosity 14 |
| Over-dispense | High pressure/time 28, viscosity 18, Z-gap 14 |
| Spreading | Viscosity 26, high pressure 20, Z-gap 14 |
| Irregular / bubble | Trapped air 28, suck-back 16, stringing/satellites 16 |

Type 6 multiplies clog ×1.7 and oxidation ×1.85, spread ×0.6, then renormalizes. That is how the chatbot can say:

> Clogging risk is elevated because Type 6 paste is being dispensed through a fine-pitch nozzle. Type 6 powder has ~3× the surface-area-to-volume ratio of Type 4, so it oxidizes and agglomerates faster. NSW requires nozzle ID ≥ 80 µm for T6 (5× the largest particle).

## Q&A levers (the brief’s example, now per material)

| Answer | What moves |
| --- | --- |
| Occasional | Air ×1.8, suck-back ×1.35; clog down |
| Continuous | Clog ×1.45, 5× mismatch ×1.3, viscosity ×1.25; air down |
| Recent nozzle change | 5× mismatch ×1.7, clog, Z-gap |
| Recent material change | Storage, oxidation, filler settling, UV gel |
| Recent settings | Pressure/time, Z-gap, suck-back |
| Single location | Z-gap, local contamination |
| Multiple locations | Material + environment + parameters |
| Fails after runtime | UV premature cure ×1.7, clog, oxidation |
| Clear UV barrel | Premature cure ×1.9 |
| Silver epoxy not mixed | Filler settling ×1.8 |

## Action-plan order (cost_rank)

1. Look in the syringe for bubbles (fastest).
2. Check expiry / storage / tip-down paste.
3. Inspect / purge nozzle.
4. Verify pressure, time, suck-back.
5. Check Z-gap and 5× nozzle vs powder (solder) or UV-blocking hardware.
6. Environment, mix, dam path.
7. Equipment inspection last.

## Worked example (judge demo)

**Inputs:** solder paste, Type 6, dot, under-dispense, continuous, recent nozzle change, multiple locations, nozzle ID 60 µm.

**Why the ranking should come out clog + 5× mismatch on top:** T6 clog factor, continuous, new nozzle, and 60 µm < 80 µm NSW floor. Air should not win.

**Contrast:** same photo class, but UV glue, occasional, clear barrel, after runtime → premature UV cure and trapped air, not powder size.
