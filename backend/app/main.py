"""FastAPI: /discover /predict /diagnose /session /report /history /samples."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from backend.app.applications import DIAGNOSIS_MODES, list_applications, resolve_answers
from backend.app.db.cases import (
    connect,
    get_case_by_session_id,
    recent_cases,
    seed_if_empty,
    similar_cases,
    update_case_feedback,
    update_case_resolution,
)
from backend.app.pipeline import run_session
from backend.app.reasoning.counter_test import apply_counter_test_feedback, select_next_verification_action
from backend.app.reasoning.discover import core_progress, is_complete, next_question
from backend.app.reasoning.explain_llm import explain_with_llm
from backend.app.reasoning.rank_causes import explain_rules, load_rules, rank_causes
from backend.app.reports.pdf import build_pdf
from backend.app.vision.predict import decode_image, load_model, predict_image
from backend.app.vision.yolo_detect import yolo_ready

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
    allow_origin_regex=r"^https?://.*",
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
        "applications": list_applications(),
        "diagnosis_modes": DIAGNOSIS_MODES,
        "nsw_home": "https://nswautomation.com/NSW/",
        "score_formula": (
            "Score(cause) = material×defect baseline × fuzzy multipliers "
            "+ Σ (symptom evidence × μ). Likelihoods then sum to 100%."
        ),
        "samples": _sample_names(),
        "sample_count": len(_sample_names()),
        "case_count": case_count,
        "vision_ready": load_model() is not None,
        "yolo_ready": yolo_ready(),
        "vision_backend": "yolo" if yolo_ready() else "mobilenet_or_heuristic",
    }


@app.get("/applications")
def applications() -> dict:
    return {"applications": list_applications(), "modes": DIAGNOSIS_MODES}


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
    answers = resolve_answers(dict(payload or {}))
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
    result = rank_causes(resolve_answers(symptoms))
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


@app.post("/counter-test/verify")
def counter_test_verify(payload: dict) -> dict:
    current_causes = payload.get("current_causes") or []
    test_id = payload.get("test_id")
    feedback = payload.get("feedback")  # 'resolved' | 'unresolved' | 'shifted'
    test_history = payload.get("test_history") or []
    session_id = payload.get("session_id")

    if not test_id or not feedback:
        raise HTTPException(400, "Missing test_id or feedback")

    res = apply_counter_test_feedback(current_causes, test_id, feedback, test_history)

    # If resolved and session_id is provided, automatically persist confirmed cause
    if res.get("resolved") and session_id and res.get("confirmed_cause"):
        update_case_resolution(session_id, res["confirmed_cause"], res["elimination_pathway"])

    return res


@app.post("/counter-test/confirm")
def counter_test_confirm(payload: dict) -> dict:
    session_id = payload.get("session_id")
    confirmed_cause = payload.get("confirmed_cause")
    elimination_pathway = payload.get("elimination_pathway") or []
    if not session_id or not confirmed_cause:
        raise HTTPException(400, "Missing session_id or confirmed_cause")
    success = update_case_resolution(session_id, confirmed_cause, elimination_pathway)
    return {"status": "ok", "updated": success}


@app.get("/cases/{session_id}")
def get_case(session_id: str) -> dict:
    case = get_case_by_session_id(session_id)
    if not case:
        raise HTTPException(404, f"Case with session_id '{session_id}' not found")
    return case


@app.post("/cases/feedback")
@app.post("/api/v1/cases/feedback")
def submit_case_feedback(payload: dict) -> dict:
    session_id = payload.get("session_id")
    status = payload.get("status") or "RESOLVED"
    confirmed_cause = payload.get("confirmed_cause")
    operator_notes = payload.get("operator_notes")

    if not session_id or not confirmed_cause:
        raise HTTPException(400, "Missing session_id or confirmed_cause")

    updated = update_case_feedback(
        session_id=session_id,
        status=status,
        confirmed_cause=confirmed_cause,
        operator_notes=operator_notes,
    )
    if not updated:
        raise HTTPException(404, f"Case with session_id '{session_id}' not found")
    return {
        "status": "ok",
        "session_id": session_id,
        "is_resolved": status.upper() in {"RESOLVED", "OK", "CONFIRMED"},
        "confirmed_cause": confirmed_cause,
    }
