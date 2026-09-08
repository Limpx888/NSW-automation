"""FastAPI entrypoint for DARA solder-paste scan."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.qa import answer_question
from backend.quality import assess_quality
from backend.vision import analyze_image, decode_image, load_model, model_status
from backend.workflow import PostInspectionWorkflow

app = FastAPI(
    title="DARA Solder Paste Scan",
    description="YOLO defect analysis + rule-based cause ranking + fast Q&A",
    version="0.2.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QaMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class QaRequest(BaseModel):
    question: str = Field(min_length=1)
    analysis: dict[str, Any] | None = None
    history: list[QaMessage] = Field(default_factory=list)
    # Default fast (rule-based). Set use_gemini=true only when you want the slower LLM path.
    use_gemini: bool = False


class DiagnoseRequest(BaseModel):
    defect_class: str
    confidence: float = 0.8
    detection_count: int = 0
    answers: dict[str, str] = Field(default_factory=dict)
    analysis: dict[str, Any] | None = None


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
    load_model()


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
        "endpoints": {
            "analyze": "POST /analyze",
            "questions": "POST /workflow/questions",
            "diagnose": "POST /workflow/diagnose",
            "qa": "POST /qa (fast rule-based; optional use_gemini=true)",
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
    return {
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
    if payload.analysis:
        d2, c2, n2 = _defect_from_analysis(payload.analysis)
        defect = defect or d2
        conf = conf or c2
        count = count or n2

    wf = PostInspectionWorkflow(defect, conf, count)
    if len(payload.answers) < 2:
        raise HTTPException(400, "Provide answers for both follow-up questions (frequency, recent_change).")

    result = wf.run(payload.answers)
    return result.as_dict()


@app.post("/qa")
def qa(payload: QaRequest) -> dict[str, Any]:
    """Fast rule-based Q&A by default. Optional Gemini via use_gemini=true."""
    analysis = payload.analysis
    defect, conf, count = _defect_from_analysis(analysis)
    wf = PostInspectionWorkflow(defect, conf, count)

    # Prefer ranked causes if client already ran diagnose
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

    # Slow optional path
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
