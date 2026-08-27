# 20-day schedule (scope-locked)

Copied from the research brief and frozen so the team does not reopen framework debates.

**Do not slip Days 1–2.** The cause table is the intellectual core. If dataset generation (Days 4–7) runs late, delay the vision model and compress UI polish — never compress reasoning (Days 9–12).

Keep vision (`predict`) and reasoning (`rank_causes`) as separate functions so one track cannot block the other.

| Day | Deliverable | Status |
| --- | --- | --- |
| 1 | Domain notes + defect–material–pattern matrix | Done (`docs/01`, `docs/02`, `research/*.csv`) |
| 2 | Cause-ranking rules on paper/JSON | Done (`docs/03`, `research/cause_ranking_rules.json`) |
| 3 | Repo skeleton, locked stack, everyone can run locally | Done (this repo) |
| 4 | Clean synthetic dots / lines / dam-fill | Done (`model/synthesize.py`) |
| 5 | Defect injection + material textures + CSV labels | Done |
| 6 | 4k-scale images, augment, 70/15/15 split | Done (`scripts/generate_dataset.py`) |
| 7 | PCB-AoI pretrain set; optional 50–200 real phone photos | Optional — `data/real/` |
| 8 | MobileNetV2 baseline + discovery Q&A flow | Done (`model/train.py`, `discover.py`) |
| 9 | Optional PCB-AoI pretrain; encode tables | Tables encoded; PCB-AoI skipped unless downloaded |
| 10 | Real-photo val; `/predict`; LLM explanation wrapper | Done (`explain_llm.py`, falls back without API key) |
| 11 | Vision output into `rank_causes`; low-confidence flag | Done (`pipeline.py`) |
| 12 | Action-plan generator | Done |
| 13 | SQLite case log + similar-case counts | Done (20 seeded cases) |
| 14 | PDF report | Done |
| 15 | FastAPI: /discover /predict /diagnose /report /history | Done |
| 16 | Next.js end-to-end UI | Done (`frontend-next/`) |
| 17 | 15–20 full sessions, < 2 min demo path | Done (`scripts/integration_demo.py`) |
| 18 | Seed 15–20 historical cases | Done (20 seed rows in `db/cases.py`) |
| 19 | Polish + slides | Outline in `docs/presentation_outline.md` |
| 20 | Rehearsal only — no new features | |

## Critical path

- Days 4–7 block Days 8–10 (vision).
- Real photos on Day 7 are optional but high-value for an honest validation slide.
- Bonus challenges in the NSW brief: image recognition, quality score, learning database, PDF. Database + PDF + vision are all in this plan.
