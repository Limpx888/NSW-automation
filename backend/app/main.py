"""FastAPI: /discover /predict /diagnose /report /history."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend.app.db.cases import recent_cases, seed_if_empty, similar_cases
from backend.app.pipeline import run_session
from backend.app.reasoning.discover import next_question
from backend.app.reasoning.explain_llm import explain_with_llm
from backend.app.reasoning.rank_causes import explain_rules, load_rules, rank_causes
from backend.app.reports.pdf import build_pdf
from backend.app.vision.predict import decode_image, predict_image

app = FastAPI(
    title="AI Dispensing Defect Detective",
    description="NSW Automation — AI Horizon Solution Challenge 2026",
    version="0.2.0",
)


@app.on_event("startup")
def startup() -> None:
    seed_if_empty()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict:
    rules = load_rules()
    return {
        "materials": rules["materials"],
        "patterns": rules["patterns"],
        "defect_classes": rules["defect_classes"],
        "powder_types": list(rules["powder_types"].keys()),
        "five_x_rule": rules["five_x_rule"]["statement"],
        "discovery_questions": rules["discovery_questions"],
        "followups": rules["followups"],
    }


@app.post("/discover")
def discover(answers: dict) -> dict:
    nxt = next_question(answers or {})
    return {"complete": nxt is None, "next": nxt, "answers": answers}


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


@app.post("/session")
async def session(payload: dict) -> dict:
    return run_session(payload)


@app.post("/report")
def report(session_data: dict) -> Response:
    pdf = build_pdf(session_data)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=dispense-report.pdf"})


@app.get("/history")
def history(material: str | None = None, defect_class: str | None = None) -> dict:
    if material and defect_class:
        return similar_cases(material, defect_class)
    return {"cases": recent_cases(20)}
