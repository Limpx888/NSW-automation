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
cd frontend
npm run dev
```

Open the frontend at <http://localhost:8443>.

The backend runs at <http://127.0.0.1:8000>.