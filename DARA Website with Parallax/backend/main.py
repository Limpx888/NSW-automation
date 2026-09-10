"""FastAPI entrypoint for DARA solder-paste scan."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
import pandas as pd
import joblib
from fastapi import Form
from backend import history
from backend.config import get_settings
from backend.qa import answer_question
from backend.quality import assess_quality
from backend.report.data import build_report_data
from backend.report.docx_renderer import render_docx
from backend.report.pdf_renderer import render_pdf, render_report_html
from backend.vision import analyze_image, decode_image, load_model, model_status
from backend.workflow import PostInspectionWorkflow

app = FastAPI(
    title="DARA Solder Paste Scan",
    description="YOLO defect analysis + rule-based cause ranking + fast Q&A + reports",
    version="0.3.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class QaMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class QaRequest(BaseModel):
    question: str = Field(min_length=1)
    analysis: dict[str, Any] | None = None
    history: list[QaMessage] = Field(default_factory=list)
    use_gemini: bool = False


class DiagnoseRequest(BaseModel):
    defect_class: str
    confidence: float = 0.8
    detection_count: int = 0
    answers: dict[str, str] = Field(default_factory=dict)
    analysis: dict[str, Any] | None = None
    session_id: str | None = None


def _defect_from_analysis(analysis: dict[str, Any] | None) -> tuple[str, float, int]:
    if not analysis:
        return "inconsistent_size", 0.8, 0
    vision = analysis.get("vision") or {}
    defect = (
        vision.get("defect_class")
        or analysis.get("defect_class")
        or "inconsistent_size"
    )
    conf = float(vision.get("confidence") or analysis.get("confidence") or 0.8)
    count = int(
        vision.get("detection_count")
        or len(analysis.get("detections") or vision.get("detections") or [])
        or analysis.get("detection_count")
        or 0
    )
    return str(defect), conf, count


@app.on_event("startup")
def startup() -> None:
    history.connect().close()
    load_model()
    try:
        global ml_pipeline
        ml_pipeline = joblib.load("backend/weights/aoi_diagnostic_model.pkl")
    except Exception as e:
        print(f"Error loading ML model: {e}")
        ml_pipeline = None

ACTION_DB = {
    "Air Bubble": "Inspect syringe barrel for micro-bubbles and perform line purge.",
    "Nozzle Blockage": "Inspect nozzle tip under microscope; clean or replace tip.",
    "Material Viscosity Change": "Verify syringe temperature and check material pot-life.",
    "Incorrect Parameter": "Verify pressure regulator, pulse timer, and standoff height.",
    "Equipment Problem": "Perform Z-height sensor zeroing and substrate flatness check."
}

@app.post("/api/diagnose")
async def run_ml_diagnostics(
    yolo_defect: str = Form(...),
    material: str = Form(...),
    amount: str = Form(...),
    frequency: str = Form(...),
    recent_change: str = Form(...),
    location: str = Form(...)
):
    if ml_pipeline is None:
        raise HTTPException(500, "ML model not loaded.")
        
    input_df = pd.DataFrame([{
        "yolo_defect": yolo_defect,
        "material": material,
        "amount": amount,
        "frequency": frequency,
        "recent_change": recent_change,
        "location": location
    }])

    probabilities = ml_pipeline.predict_proba(input_df)[0]
    classes = ml_pipeline.named_steps["classifier"].classes_

    cause_scores = []
    for cause_name, prob in zip(classes, probabilities):
        score_pct = int(round(prob * 100))
        cause_scores.append({
            "cause": cause_name,
            "score": f"{score_pct}%",
            "score_num": score_pct,
            "reasoning": f"ML model calculated {score_pct}% confidence based on operational inputs."
        })

    sorted_causes = sorted(cause_scores, key=lambda x: x["score_num"], reverse=True)[:3]

    action_plan = []
    statuses = ["In progress", "Pending", "Pending"]
    for idx, (cause_item, status) in enumerate(zip(sorted_causes, statuses), start=1):
        action_plan.append({
            "step": idx,
            "cause": cause_item["cause"],
            "action": ACTION_DB.get(cause_item["cause"], "Perform general visual inspection."),
            "status": status
        })

    return {
        "cause_table": sorted_causes,
        "action_plan": action_plan
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict[str, Any]:
    status = model_status()
    return {
        "service": "dara-solder-paste-scan",
        "vision": status,
        "gemini_configured": bool(get_settings().gemini_api_key.strip()),
        "gemini_model": get_settings().gemini_model,
        "qa_default": "rule_based",
        "case_count": history.count_cases(),
        "endpoints": {
            "analyze": "POST /analyze",
            "questions": "POST /workflow/questions",
            "diagnose": "POST /workflow/diagnose",
            "qa": "POST /qa (fast rule-based; optional use_gemini=true)",
            "history": "GET /history",
            "case": "GET /cases/{session_id}",
            "report": "GET /report/{session_id}?format=pdf|docx",
            "report_data": "GET /report/{session_id}/data",
            "report_preview": "GET /report/{session_id}/preview",
        },
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a defect image → YOLO boxes/masks + quality assessment + follow-up prompts."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty upload. Choose a JPEG or PNG image.")
    try:
        image = decode_image(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        vision = analyze_image(image)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Inference failed: {exc}") from exc

    quality = assess_quality(vision)
    wf = PostInspectionWorkflow(
        defect_class=vision["defect_class"],
        confidence=float(vision["confidence"]),
        detection_count=int(vision.get("detection_count") or 0),
    )
    payload = {
        "filename": file.filename,
        "vision": vision,
        "quality": quality,
        "defect_label": vision["defect_label"],
        "defect_class": vision["defect_class"],
        "confidence": vision["confidence"],
        "overall_quality_score": quality["overall_quality_score"],
        "shape_consistency": quality["shape_consistency"],
        "size_consistency": quality["size_consistency"],
        "dispensing_position": quality["dispensing_position"],
        "defect_risk": quality["defect_risk"],
        "annotated_image_base64": vision["annotated_image_base64"],
        "detections": vision["detections"],
        "status": "analyzed",
    }
    session_id = history.create_case(payload)
    return {
        **payload,
        "session_id": session_id,
        "followup_questions": wf.get_followup_questions(),
    }


@app.post("/workflow/questions")
def workflow_questions(payload: DiagnoseRequest) -> dict[str, Any]:
    defect, conf, count = payload.defect_class, payload.confidence, payload.detection_count
    if payload.analysis:
        defect, conf, count = _defect_from_analysis(payload.analysis)
    wf = PostInspectionWorkflow(defect, conf, count)
    return {
        "defect_class": wf.defect_class,
        "defect_label": wf.defect_label,
        "confidence": wf.confidence,
        "questions": wf.get_followup_questions(),
    }


@app.post("/workflow/diagnose")
def workflow_diagnose(payload: DiagnoseRequest) -> dict[str, Any]:
    """STEP 2 answers → STEP 4 cause table + STEP 5 action plan (instant, no LLM)."""
    defect, conf, count = payload.defect_class, payload.confidence, payload.detection_count
    analysis = payload.analysis or {}
    if payload.analysis:
        d2, c2, n2 = _defect_from_analysis(payload.analysis)
        defect = defect or d2
        conf = conf or c2
        count = count or n2

    wf = PostInspectionWorkflow(defect, conf, count)
    if len(payload.answers) < 2:
        raise HTTPException(
            400, "Provide answers for both follow-up questions (frequency, recent_change)."
        )

    result = wf.run(payload.answers)
    out = result.as_dict()
    session_id = payload.session_id or analysis.get("session_id")
    session_id = history.upsert_diagnosed_case(
        {
            "session_id": session_id,
            "filename": analysis.get("filename"),
            "defect_class": out["defect_class"],
            "defect_label": out["defect_label"],
            "confidence": out["confidence"],
            "detection_count": count,
            "vision": analysis.get("vision"),
            "quality": analysis.get("quality")
            or {
                "overall_quality_score": analysis.get("overall_quality_score"),
                "shape_consistency": analysis.get("shape_consistency"),
                "size_consistency": analysis.get("size_consistency"),
                "dispensing_position": analysis.get("dispensing_position"),
                "defect_risk": analysis.get("defect_risk"),
            },
            "overall_quality_score": analysis.get("overall_quality_score"),
            "annotated_image_base64": analysis.get("annotated_image_base64")
            or (analysis.get("vision") or {}).get("annotated_image_base64"),
            "detections": analysis.get("detections")
            or (analysis.get("vision") or {}).get("detections"),
            "answers": out["answers"],
            "causes": out["causes"],
            "action_plan": out["action_plan"],
            "status": "diagnosed",
        }
    )
    out["session_id"] = session_id
    return out


@app.post("/qa")
def qa(payload: QaRequest) -> dict[str, Any]:
    """Fast rule-based Q&A by default. Optional Gemini via use_gemini=true."""
    analysis = payload.analysis
    defect, conf, count = _defect_from_analysis(analysis)
    wf = PostInspectionWorkflow(defect, conf, count)

    prior_causes = None
    if analysis and analysis.get("causes"):
        from backend.workflow import CauseRow

        prior_causes = [
            CauseRow(
                cause_id=c.get("cause_id", ""),
                name=c.get("name", ""),
                likelihood_pct=float(c.get("likelihood_pct") or 0),
                reasoning=c.get("reasoning", ""),
            )
            for c in analysis["causes"]
        ]

    if not payload.use_gemini:
        answer = wf.answer_fast(payload.question, prior_causes)
        return {
            "answer": answer,
            "provider": "rule_based",
            "model": None,
            "gemini_configured": bool(get_settings().gemini_api_key.strip()),
            "latency": "instant",
        }

    if analysis and "quality" not in analysis:
        analysis = {
            **(payload.analysis.get("vision") or {}),
            "quality": payload.analysis.get("quality")
            or {
                "overall_quality_score": payload.analysis.get("overall_quality_score"),
                "shape_consistency": payload.analysis.get("shape_consistency"),
                "size_consistency": payload.analysis.get("size_consistency"),
                "dispensing_position": payload.analysis.get("dispensing_position"),
                "defect_risk": payload.analysis.get("defect_risk"),
            },
            "defect_label": payload.analysis.get("defect_label"),
            "defect_class": defect,
            "confidence": conf,
            "detection_count": count,
            "detections": payload.analysis.get("detections")
            or (payload.analysis.get("vision") or {}).get("detections"),
        }

    result = answer_question(
        question=payload.question,
        analysis=analysis,
        history=[m.model_dump() for m in payload.history],
    )
    return result


@app.get("/history")
def list_history(limit: int = 50) -> dict[str, Any]:
    cases = history.list_cases(limit=max(1, min(limit, 200)))
    return {"cases": cases, "count": len(cases), "total": history.count_cases()}


@app.get("/cases/{session_id}")
def get_case(session_id: str) -> dict[str, Any]:
    case = history.get_case(session_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@app.get("/report/{session_id}")
def download_report(session_id: str, format: Literal["pdf", "docx"] = "pdf") -> Response:
    if format not in MEDIA_TYPES:
        raise HTTPException(400, f"format must be one of {list(MEDIA_TYPES)}")
    try:
        data = build_report_data(session_id)
    except LookupError:
        raise HTTPException(404, "Session not found") from None

    content = render_docx(data) if format == "docx" else render_pdf(data)
    filename = f"dara-report-{session_id[:12]}.{format}"
    return Response(
        content=content,
        media_type=MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/report/{session_id}/data")
def report_data(session_id: str) -> dict[str, Any]:
    try:
        data = build_report_data(session_id)
    except LookupError:
        raise HTTPException(404, "Session not found") from None
    return data.model_dump(mode="json")


@app.get("/report/{session_id}/preview", response_class=HTMLResponse)
def preview_report(session_id: str) -> HTMLResponse:
    try:
        data = build_report_data(session_id)
    except LookupError:
        raise HTTPException(404, "Session not found") from None
    return HTMLResponse(content=render_report_html(data))
