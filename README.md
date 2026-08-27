# AI Dispensing Defect Detective

**Tagline:** Helping manufacturers identify dispensing problems faster with AI.

NSW Automation · AI Horizon Solution Challenge 2026

This is a **material-aware dispensing troubleshooting assistant** — not a generic chatbot. It ranks root causes from deterministic NSW/AIM process rules (including the **nozzle ID ≥ 5× largest powder particle** rule for solder paste), optionally classifies defects from a photo, logs cases, and generates a PDF report for engineers.

The UI is a **Next.js** app. Reasoning, vision, and PDF stay in the **FastAPI** backend.

---

## What you need

| Requirement | Notes |
| --- | --- |
| **Python 3.11+** | Tested on 3.13 |
| **Node.js 18+** | For the Next.js UI |
| **Windows / macOS / Linux** | Commands below use PowerShell; adapt paths if needed |
| **~2 GB disk** | Synthetic dataset + PyTorch (optional if you skip training) |

You do **not** need a GPU. CPU training and inference work (slower training only).

---

## Quick start (run the demo now)

Use this if the repo already has `data/synthetic/`, `model/checkpoints/best.pt`, and `data/samples/` (as in a completed team setup).

### 1. Open a terminal in the project folder

```powershell
cd "C:\Users\User\Documents\Competition Project\AI horizon challenge\NSW-automation"
```

### 2. Install Python dependencies (once)

```powershell
python -m pip install -r requirements.txt
```

### 3. Start the API (terminal 1)

```powershell
uvicorn backend.app.main:app --reload --port 8000
```

API docs: **http://127.0.0.1:8000/docs**

### 4. Start the Next.js UI (terminal 2)

```powershell
cd frontend-next
npm install
npm run dev
```

Open **http://localhost:3000**.

### 5. Run a 2-minute judge demo

1. Dashboard → **Load demo on Troubleshoot** (or Troubleshoot `?demo=1`)
2. Confirm Type 6 paste, 60 µm nozzle, continuous under-dispense after a nozzle change
3. Click **Analyse**
4. Top causes should be **Nozzle ID vs powder size (5× rule)** and **Partial nozzle clog**
5. **Download PDF report**

Expected explanation includes: *60 µm is below NSW’s 80 µm floor for Type 6 paste.*

---

## First-time full setup (new machine / fresh clone)

```powershell
cd "C:\Users\User\Documents\Competition Project\AI horizon challenge\NSW-automation"

python -m pip install -r requirements.txt
python -m pytest -q

python scripts/generate_dataset.py --per-combo 48
python model/train.py --epochs 6
python model/train.py --epochs 5 --lr 0.0003 --unfreeze-last 4 --resume model/checkpoints/best.pt

python -c "from backend.app.db.cases import seed_if_empty; print('seeded', seed_if_empty())"
python scripts/integration_demo.py

uvicorn backend.app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend-next
npm install
npm run dev
```

After setup, day-to-day use is: API on **8000** + Next.js on **3000**.

---

## How to run each part

### A. Next.js UI (main demo)

```powershell
cd frontend-next
npm run dev
```

- URL: **http://localhost:3000**
- Pages: Dashboard `/`, Troubleshoot `/troubleshoot`, Case history `/history`
- Requires the FastAPI server on port 8000

### B. FastAPI backend

```powershell
uvicorn backend.app.main:app --reload --port 8000
```

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Server alive |
| GET | `/meta` | Materials, patterns, samples, vision status |
| GET | `/samples` | Demo image names |
| GET | `/samples/{name}` | Serve a demo PNG |
| POST | `/discover` | Next guided / fuzzy follow-up |
| POST | `/predict` | Upload image → defect class |
| POST | `/diagnose` | Q&A JSON → ranked causes (no image) |
| POST | `/session` | JSON or multipart (`answers` + optional `file` / `sample`) |
| POST | `/report` | Session JSON → PDF bytes |
| GET | `/history` | Recent cases |

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

### D. Integration smoke test

```powershell
python scripts/integration_demo.py
```

---

## Optional: richer explanation text (LLM)

Ranking is **always deterministic**. If you set an OpenAI API key, the app can rewrite the explanation and optionally pick among follow-up questions:

```powershell
$env:OPENAI_API_KEY = "sk-..."
uvicorn backend.app.main:app --reload --port 8000
```

Without a key, rule-based explanations and the JSON decision tree are used automatically.

---

## Project layout

```
NSW-automation/
├── frontend-next/           # Next.js UI (start here: npm run dev)
├── backend/app/
│   ├── main.py              # FastAPI routes
│   ├── pipeline.py          # Photo + Q&A → full session
│   ├── reasoning/           # Cause ranking, fuzzy Q&A, discovery
│   ├── vision/predict.py    # MobileNetV2 + heuristic fallback
│   ├── db/cases.py          # SQLite case log
│   └── reports/pdf.py       # PDF generator
├── model/
├── data/
├── research/
├── scripts/
└── docs/
```

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` from the project root |
| UI cannot reach API | Start `uvicorn backend.app.main:app --port 8000` |
| Next.js port in use | `npm run dev -- -p 3001` |
| Vision always says heuristic | Train the model or copy `model/checkpoints/best.pt` into place |
| `No module named 'backend'` | Run commands from the **NSW-automation** folder |
| Empty similar-case lookup | Run `seed_if_empty()` once or complete a few sessions in the UI |

---

## Scope & honesty (for judges)

- **Materials:** solder paste (T3–T6), silver epoxy, UV glue, silicone gel  
- **Patterns:** dot, line, dam-and-fill  
- **Defects:** under-dispense, over-dispense, missing, inconsistent volume, spreading, air-bubble/irregular  
- **Vision:** trained on **synthetic** images (~86% test accuracy — see `docs/model_metrics.md`)  
- **Core differentiator:** material + pattern + NSW 5× nozzle rule in the ranking engine  

---

## Further reading

1. `docs/01_domain_research.md`
2. `docs/02_defect_material_pattern_matrix.md`
3. `docs/03_cause_ranking_rules.md`
4. `docs/model_metrics.md`
5. `docs/presentation_outline.md`
6. `docs/20_day_plan.md`

---

## Team roles

| Person | Owns |
| --- | --- |
| A — Data & Vision | `model/synthesize.py`, `model/train.py`, dataset |
| B — Reasoning & Backend | `research/cause_ranking_rules.json`, `backend/`, API |
| C — Frontend & Reports | `frontend-next/`, PDF, demo flow |
