"""FastAPI: /discover /predict /diagnose /session /report /history /samples."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from backend.app.db.cases import connect, recent_cases, seed_if_empty, similar_cases
from backend.app.pipeline import run_session
from backend.app.reasoning.discover import core_progress, is_complete, next_question
from backend.app.reasoning.explain_llm import explain_with_llm
from backend.app.reasoning.rank_causes import explain_rules, load_rules, rank_causes
from backend.app.reports.pdf import build_pdf
from backend.app.vision.predict import decode_image, load_model, predict_image

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"

app = FastAPI(
    title="AI Dispensing Defect Detective",
    description="NSW Automation — AI Horizon Solution Challenge 2026",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    seed_if_empty()


def _sample_names() -> list[str]:
    if not SAMPLES.exists():
        return []
    return sorted(p.name for p in SAMPLES.glob("*.png"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict:
    rules = load_rules()
    try:
        case_count = connect().execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    except Exception:
        case_count = 0
    return {
        "materials": rules["materials"],
        "patterns": rules["patterns"],
        "defect_classes": rules["defect_classes"],
        "powder_types": list(rules["powder_types"].keys()),
        "five_x_rule": rules["five_x_rule"]["statement"],
        "discovery_questions": rules["discovery_questions"],
        "followups": rules["followups"],
        "dynamic_followups": rules.get("dynamic_followups", []),
        "cause_families": rules.get("cause_families", {}),
        "evidence_rules": rules.get("evidence_rules", []),
        "score_formula": (
            "Score(cause) = material×defect baseline × fuzzy multipliers "
            "+ Σ (symptom evidence × μ). Likelihoods then sum to 100%."
        ),
        "samples": _sample_names(),
        "sample_count": len(_sample_names()),
        "case_count": case_count,
        "vision_ready": load_model() is not None,
    }


@app.get("/samples")
def list_samples() -> dict:
    return {"samples": _sample_names()}


@app.get("/samples/{name}")
def get_sample(name: str) -> FileResponse:
    safe = Path(name).name
    path = SAMPLES / safe
    if not path.exists() or path.suffix.lower() != ".png":
        raise HTTPException(404, "Sample not found")
    return FileResponse(path, media_type="image/png")


@app.post("/discover")
def discover(payload: dict) -> dict:
    answers = dict(payload or {})
    use_llm = bool(answers.pop("use_llm", False))
    include_optional = answers.pop("include_optional", True)
    if include_optional is None:
        include_optional = True
    nxt = next_question(answers, include_optional=bool(include_optional), use_llm=use_llm)
    return {
        "complete": is_complete(answers),
        "next": nxt,
        "answers": answers,
        "progress": core_progress(answers),
        "mode": "llm" if nxt and nxt.get("selected_by") == "llm" else "decision_tree",
    }


@app.post("/predict")
async def predict(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        image = decode_image(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return predict_image(image)


@app.post("/diagnose")
def diagnose(symptoms: dict) -> dict:
    result = rank_causes(symptoms)
    result["explanation"] = explain_with_llm(result)
    result["explanation_deterministic"] = explain_rules(result)
    result["similar"] = similar_cases(result["material"], result["defect_class"])
    return result


def _load_sample_image(name: str):
    import cv2

    safe = Path(name).name
    path = SAMPLES / safe
    if not path.exists():
        return None
    return cv2.imread(str(path))


@app.post("/session")
async def session(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()
    image = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        raw = form.get("answers") or "{}"
        if hasattr(raw, "read"):
            raw = (await raw.read()).decode("utf-8")
        answers = json.loads(str(raw))
        upload = form.get("file")
        if upload is not None and hasattr(upload, "read"):
            data = await upload.read()
            if data:
                try:
                    image = decode_image(data)
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
        sample = form.get("sample")
        if image is None and sample:
            image = _load_sample_image(str(sample))
        return run_session(answers, image_bgr=image)
    payload = await request.json()
    sample = payload.pop("sample", None)
    if sample:
        image = _load_sample_image(str(sample))
    return run_session(payload, image_bgr=image)


@app.post("/report")
def report(session_data: dict) -> Response:
    pdf = build_pdf(session_data)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=dispense-report.pdf"},
    )


@app.get("/history")
def history(material: str | None = None, defect_class: str | None = None) -> dict:
    if material and defect_class:
        return similar_cases(material, defect_class)
    return {"cases": recent_cases(20)}
