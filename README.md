# AI Dispensing Defect Detective

**Tagline:** Helping manufacturers identify dispensing problems faster with AI.

NSW Automation · AI Horizon Solution Challenge 2026

This is a **material-aware dispensing troubleshooting assistant** — not a generic chatbot. It ranks root causes from deterministic NSW/AIM process rules (including the **nozzle ID ≥ 5× largest powder particle** rule for solder paste), optionally classifies defects from a photo, logs cases, and generates a PDF report for engineers.

---

## What you need

| Requirement | Notes |
| --- | --- |
| **Python 3.11+** | Tested on 3.13 |
| **Windows / macOS / Linux** | Commands below use PowerShell; adapt paths if needed |
| **~2 GB disk** | Synthetic dataset + PyTorch (optional if you skip training) |
| **Internet (first run only)** | PyTorch may download ImageNet weights when training |

You do **not** need a GPU. CPU training and inference work (slower training only).

---

## Quick start (run the demo now)

Use this if the repo already has `data/synthetic/`, `model/checkpoints/best.pt`, and `data/samples/` (as in a completed team setup).

### 1. Open a terminal in the project folder

```powershell
cd "C:\Users\User\Documents\Competition Project\AI horizon challenge\NSW-automation"
```

### 2. Install dependencies (once)

```powershell
python -m pip install -r requirements.txt
```

### 3. Start the web app (recommended for judges)

```powershell
streamlit run frontend/app.py
```

Your browser should open to **http://localhost:8501**. If it does not, open that URL manually.

### 4. Run a 2-minute judge demo

In the Streamlit UI:

1. **Photo** — Under “Or pick a synthetic demo image”, choose `under_dispense__solder_paste__dot.png` (or upload your own).
2. **Material** — `solder_paste`
3. **Pattern** — `dot`
4. **Symptom** — Too small / under-dispense
5. **Frequency** — `continuous`
6. **Recent change** — `nozzle`
7. **Location** — Multiple locations
8. **Follow-up** — Powder type **T6**, nozzle inner diameter **60** µm
9. Click **Analyse**
10. Confirm top causes are **Nozzle ID vs powder size (5× rule)** and **Partial nozzle clog**
11. Click **Download PDF report**

Expected explanation includes: *60 µm is below NSW’s 80 µm floor for Type 6 paste.*

---

## First-time full setup (new machine / fresh clone)

Run these **once** if you do not have the dataset or trained model yet. Training on CPU takes ~30–45 minutes total.

```powershell
cd "C:\Users\User\Documents\Competition Project\AI horizon challenge\NSW-automation"

python -m pip install -r requirements.txt

# Verify reasoning engine (fast, no images)
python -m pytest -q

# Generate 3,456 labeled synthetic images (~3 min)
python scripts/generate_dataset.py --per-combo 48

# Train vision model — baseline then fine-tune (~25–40 min on CPU)
python model/train.py --epochs 6
python model/train.py --epochs 5 --lr 0.0003 --unfreeze-last 4 --resume model/checkpoints/best.pt

# Seed SQLite with 20 example historical cases
python -c "from backend.app.db.cases import seed_if_empty; print('seeded', seed_if_empty())"

# Smoke-test full pipeline (8 scenarios, ~1 s)
python scripts/integration_demo.py

# Launch UI
streamlit run frontend/app.py
```

After setup, you only need `streamlit run frontend/app.py` for normal use.

---

## How to run each part

### A. Streamlit UI (main demo)

```powershell
streamlit run frontend/app.py
```

- URL: **http://localhost:8501**
- Upload a photo **or** pick from `data/samples/`
- Answer discovery questions → see ranked causes, quality score, similar cases → download PDF
- Does **not** require the FastAPI server

### B. FastAPI backend (optional / API testing)

Open a **second terminal** in the same folder:

```powershell
uvicorn backend.app.main:app --reload
```

- API docs: **http://127.0.0.1:8000/docs**
- Health check: **http://127.0.0.1:8000/health**

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Server alive |
| GET | `/meta` | Materials, patterns, defect classes, discovery questions |
| POST | `/discover` | Next unanswered discovery question |
| POST | `/predict` | Upload image → defect class + confidence |
| POST | `/diagnose` | Q&A JSON → ranked causes (no image) |
| POST | `/session` | Full session JSON (same as Streamlit logic, no file upload) |
| POST | `/report` | Session JSON → PDF bytes |
| GET | `/history` | Recent cases or `?material=&defect_class=` for similar-case stats |

**Example — diagnose without image** (PowerShell):

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/diagnose" -ContentType "application/json" -Body (@{
  material = "solder_paste"
  pattern = "dot"
  amount = "too_small"
  frequency = "continuous"
  recent_change = "nozzle"
  location = "multiple"
  powder_type = "T6"
  nozzle_id_um = 60
} | ConvertTo-Json)
```

### C. Command-line reasoning only (no UI, no vision)

```powershell
python scripts/diagnose_cli.py
```

Uses a built-in T6 / 60 µm demo payload. Pass custom JSON as the first argument if needed.

### D. Integration smoke test

```powershell
python scripts/integration_demo.py
```

Runs 8 end-to-end scenarios (vision + ranking + PDF + similar cases). Should finish in a few seconds and print `All integration checks passed.`

---

## Optional: richer explanation text (LLM)

Ranking is **always deterministic**. If you set an OpenAI API key, the app can rewrite the explanation in friendlier prose without changing cause percentages:

```powershell
$env:OPENAI_API_KEY = "sk-..."
# optional: pip install openai
streamlit run frontend/app.py
```

Without a key, rule-based explanations are used automatically.

---

## Project layout

```
NSW-automation/
├── frontend/app.py          # Streamlit demo (start here)
├── backend/app/
│   ├── main.py              # FastAPI routes
│   ├── pipeline.py          # Photo + Q&A → full session
│   ├── reasoning/           # Cause ranking + discovery flow
│   ├── vision/predict.py    # MobileNetV2 + heuristic fallback
│   ├── db/cases.py          # SQLite case log
│   └── reports/pdf.py       # PDF generator
├── model/
│   ├── synthesize.py        # Synthetic image generator
│   ├── train.py             # MobileNetV2 training
│   └── checkpoints/best.pt  # Trained weights (gitignored; regenerate if missing)
├── data/
│   ├── synthetic/           # Training images + labels.csv
│   ├── samples/             # Demo preview PNGs
│   └── cases.db             # Runtime case database (created on first run)
├── research/                # Cause-ranking JSON + defect matrix
├── scripts/                 # generate_dataset, integration_demo, diagnose_cli
└── docs/                    # Research notes, metrics, presentation outline
```

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` from the project root |
| Streamlit port in use | Stop the other Streamlit process or run `streamlit run frontend/app.py --server.port 8502` |
| Vision always says “heuristic” | Train the model or copy `model/checkpoints/best.pt` into place |
| `No module named 'backend'` | Run commands from the **NSW-automation** folder, not the parent |
| Training is very slow | Normal on CPU; use existing checkpoint and skip `model/train.py` |
| Empty similar-case lookup | Run `seed_if_empty()` once or complete a few sessions in the UI |
| `use_container_width` warning in Streamlit | Harmless deprecation warning; app still works |

---

## Scope & honesty (for judges)

- **Materials:** solder paste (T3–T6), silver epoxy, UV glue, silicone gel  
- **Patterns:** dot, line, dam-and-fill  
- **Defects:** under-dispense, over-dispense, missing, inconsistent volume, spreading, air-bubble/irregular  
- **Vision:** trained on **synthetic** images (~86% test accuracy — see `docs/model_metrics.md`)  
- **Real photos:** optional validation set in `data/real/`; expect lower accuracy  
- **Core differentiator:** material + pattern + NSW 5× nozzle rule in the ranking engine  

---

## Further reading

1. `docs/01_domain_research.md` — NSW materials, powder types, industry terms  
2. `docs/02_defect_material_pattern_matrix.md` — defect × material × pattern grid  
3. `docs/03_cause_ranking_rules.md` — how weights and Q&A adjustments work  
4. `docs/model_metrics.md` — vision accuracy numbers  
5. `docs/presentation_outline.md` — slide skeleton for judging  
6. `docs/20_day_plan.md` — 20-day build schedule  

---

## Team roles

| Person | Owns |
| --- | --- |
| A — Data & Vision | `model/synthesize.py`, `model/train.py`, dataset |
| B — Reasoning & Backend | `research/cause_ranking_rules.json`, `backend/`, API |
| C — Frontend & Reports | `frontend/app.py`, PDF, demo flow |

If the team has two people, merge B + C.
