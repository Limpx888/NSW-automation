# DARA Solder Paste Scan

- `frontend/` - React and Vite frontend
- `backend/` - FastAPI and YOLO backend

## First-time setup

Run these commands in PowerShell from the project folder:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

The `best (2).pt` file must be in the project folder.

## Run the app

Open two PowerShell terminals in the project folder.

### Terminal 1: Backend

```powershell
.\.venv\Scripts\Activate.ps1
npm run backend
```

### Terminal 2: Frontend

```powershell
npm run dev
```

Open the frontend at <http://localhost:8443>.

The backend runs at <http://127.0.0.1:8000>.

## History and reports

- Every analyze/diagnose run is saved to History (`data/scan_cases.db`).
- Reports include cause charts, quality donut, and deep analysis.
- Download as **PDF** or **Word (.docx)** from Scan results, History, or Reports.

## Evidence-first multimodal reasoning

`POST /reasoning/diagnose` accepts questionnaire, vision, process-parameter, and
optional historical evidence. Each item should include an `id`, `feature_name`,
`value`, source-specific reliability, and explicit supporting or contradicting
cause weights. Historical evidence is never inferred when omitted.

The response contains a complete diagnostic trace: extracted evidence,
correlation suppression, conflicts, contributions, raw scores, normalized
likelihoods, uncertainty, next-best question, diagnosis when justified,
explanation, and recommended actions. Normalized likelihoods are ranking scores,
not calibrated probabilities.