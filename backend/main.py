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
from backend.reasoning import MultimodalEvidenceFusion, QuestionOption
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
    user_email: str | None = None


class FusionDiagnoseRequest(BaseModel):
    questionnaire: list[dict[str, Any]] = Field(default_factory=list)
    vision: list[dict[str, Any]] = Field(default_factory=list)
    process_parameters: list[dict[str, Any]] = Field(default_factory=list)
    historical_cases: list[dict[str, Any]] = Field(default_factory=list)
    cause_ids: list[str] | None = None
    questions: list[dict[str, Any]] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)


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
        import warnings
        from sklearn.exceptions import InconsistentVersionWarning
        import sklearn.compose._column_transformer
        if not hasattr(sklearn.compose._column_transformer, "_RemainderColsList"):
            class _RemainderColsList(list):
                pass
            sklearn.compose._column_transformer._RemainderColsList = _RemainderColsList
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
            ml_pipeline = joblib.load("backend/weights/aoi_diagnostic_model.pkl")
    except Exception as e:
        print(f"Error loading ML model: {e}")
        ml_pipeline = None

@app.post("/diagnose")
async def run_diagnostics(
    yolo_defect: str = Form("inconsistent_size"),
    material: str = Form(""),
    amount: str = Form(""),
    frequency: str = Form(""),
    recent_change: str = Form(""),
    location: str = Form(""),
    session_id: str = Form(None),
    user_email: str = Form(None),
):
    # 1. Calculate Dynamic Confidence based on known answers
    known_count = sum(1 for v in [material, amount, frequency, recent_change, location] if v and "unknown" not in v.lower())
    dynamic_confidence = round(0.65 + (known_count * 0.05), 2)  # Scales from 65% up to 90%

    wf = PostInspectionWorkflow(defect_class=yolo_defect, confidence=dynamic_confidence)

    answers = {
        "amount": amount,
        "frequency": frequency,
        "recent_change": recent_change,
        "location": location,
        "material": material
    }
    result = wf.run(answers)

    # Inject Thixotropic override for idle machines
    # UPDATE THIS LINE to catch both the strict keyword and the raw UI label:
    if frequency == "after_idle" or "After Idle" in frequency: 
        from backend.workflow import CauseRow, ActionStep
        
        thixotropic_cause = CauseRow(
            cause_id="thixotropic_thickening",
            name="Thixotropic Paste Thickening",
            likelihood_pct=92.0,
            reasoning="Paste viscosity increased while resting during the break."
        )
        result.causes.insert(0, thixotropic_cause)
        
        dummy_action = ActionStep(
            step=1,
            title="Execute Dummy Shots", 
            related_cause="Thixotropic Paste Thickening",
            detail="Run 5-10 dummy shots to apply shear stress and condition paste viscosity before resuming production.",
            status="pending"
        )
        
        # 1. Insert the dummy action at the very top of the list
        result.action_plan.insert(0, dummy_action)
        
        # 2. Re-number all steps sequentially so they render as 1, 2, 3, 4...
        for idx, action in enumerate(result.action_plan):
            action.step = idx + 1

    # Inject override for Stringing / Tailing (Case-insensitive)
    amount_lower = str(amount).lower()
    if "stringing" in amount_lower or "tailing" in amount_lower or "inconsistent" in amount_lower:
        from backend.workflow import CauseRow, ActionStep
        
        # Override the defect label for the UI
        result.defect_label = "STRINGING / TAILING"
        
        # Remove any generic stringing causes the ML might have guessed to avoid duplicates
        result.causes = [c for c in result.causes if "stringing" not in c.name.lower() and "tailing" not in c.name.lower()]
        
        stringing_cause = CauseRow(
            cause_id="incorrect_parameter",
            name="Incorrect Retract / Vacuum Parameter",
            likelihood_pct=88.0,
            reasoning="Tailing and dog-ears occur when the nozzle pulls away before the material snaps cleanly. This indicates insufficient suck-back (vacuum) or improper Z-axis retract speed."
        )
        result.causes.insert(0, stringing_cause)
        
        stringing_action = ActionStep(
            step=1,
            title="Adjust Z-Retract and Vacuum", 
            related_cause="Incorrect Retract / Vacuum Parameter",
            detail="Increase the vacuum (suck-back) slightly, or adjust the Z-axis retract speed and height to ensure a clean break off the dot before XY movement.",
            status="pending"
        )
        result.action_plan.insert(0, stringing_action)
        
        # Re-number all steps sequentially
        for idx, action in enumerate(result.action_plan):
            action.step = idx + 1

    # Inject override for Progressive Viscosity Drop (Afternoon Slumping)
    frequency_lower = str(frequency).lower()
    
    if "progressive" in frequency_lower and ("large" in amount_lower or "excess" in amount_lower):
        from backend.workflow import CauseRow, ActionStep
        
        viscosity_cause = CauseRow(
            cause_id="material_viscosity",
            name="Material Viscosity Drop (Ambient Temperature)",
            likelihood_pct=89.0,
            reasoning="Paste slumping and bridging that worsens over a few hours (especially in the afternoon) is a classic symptom of ambient temperature rising, which causes solder paste to thin out."
        )
        result.causes.insert(0, viscosity_cause)
        
        viscosity_action = ActionStep(
            step=1,
            title="Check Ambient Temperature", 
            related_cause="Material Viscosity Drop (Ambient Temperature)",
            detail="Check the shop floor/machine temperature. If it is warm, replace the paste with a fresh, cooler batch and verify booth climate controls.",
            status="pending"
        )
        result.action_plan.insert(0, viscosity_action)
        
        # Re-number all steps sequentially
        for idx, action in enumerate(result.action_plan):
            action.step = idx + 1

    top_cause = result.causes[0] if result.causes else None
    reasoning_text = ""
    
    if top_cause:
        reasoning_text = f"{top_cause.name} is ranked as the highest possible cause because "
        # Connect idle time to thixotropic thickening
        if top_cause.cause_id == "thixotropic_thickening":
            reasoning_text += "solder paste is a non-Newtonian fluid that thickens when idle. The first few shots lack the shear stress needed to achieve proper flow."
        # Connect the hardware swap to the blockage
        elif top_cause.cause_id == "nozzle_blockage" and "nozzle" in answers.get("recent_change", "").lower():
            reasoning_text += "the missing dots occurred continuously immediately after the hardware setup was swapped."
        # Connect occasional frequency to air bubbles
        elif top_cause.cause_id == "air_bubble" and "occasional" in answers.get("frequency", "").lower():
            reasoning_text += "the dispensing volume changes occasionally rather than continuously."
        # Connect progressive failure to viscosity
        elif top_cause.cause_id == "material_viscosity" and "progressive" in answers.get("frequency", "").lower():
            reasoning_text += "the defect starts normal and worsens over runtime, indicating a material temperature or viscosity shift."
        else:
            reasoning_text += "it strongly aligns with the identified defect and reported symptoms."

    # 2. Map the Defect to Possible Symptoms
    symptoms_map = {
        "missing_deposit": ["No solder paste on pad", "Broken lines or skipped shots"],
        "missing_dot": ["No solder paste on pad", "Broken lines or skipped shots"],
        "excess_volume": ["Paste spreading beyond pad", "Bridges between pads", "Slumping"],
        "too_much": ["Paste spreading beyond pad", "Bridges between pads", "Slumping"],
        "insufficient_volume": ["Starved joints", "Incomplete pad coverage"],
        "too_little": ["Starved joints", "Incomplete pad coverage"],
        "STRINGING / TAILING": ["Material pulls up into a string", "Dog-ears on deposit peaks", "Paste smearing between pads"],
        "inconsistent_size": ["Some dispensing dots are larger", "Some dispensing dots are smaller", "Dispensing results are not repeatable"]
    }
    
    # Update the lookup to check the overridden label first
    symptoms = symptoms_map.get(result.defect_label) or symptoms_map.get(result.defect_class) or symptoms_map.get(yolo_defect) or symptoms_map["inconsistent_size"]

    # 1. Format the causes and action plan for the database
    formatted_causes = [
        {
            "cause_id": c.cause_id,
            "name": c.name,
            "likelihood_pct": c.likelihood_pct,
            "reasoning": c.reasoning 
        } for c in result.causes
    ]
    
    formatted_actions = [
        {
            "step": a.step,
            "cause": a.related_cause,
            "action": a.detail,
            "status": a.status
        } for a in result.action_plan
    ]

    # 2. Build the core database payload
    payload = {
        "user_email": user_email,
        "defect_class": result.defect_class,
        "defect_label": result.defect_label,
        "confidence": result.confidence,
        "answers": answers,
        "causes": formatted_causes,
        "action_plan": formatted_actions,
        "status": "diagnosed",
        "user_email": user_email or None,
    }

    # 3. Route correctly depending on Text vs Image workflow
    if session_id and session_id != "null":
        # IMAGE WORKFLOW: Fetch existing data so we don't overwrite the image with blanks
        existing = history.get_case(session_id) or {}
        payload["session_id"] = session_id
        payload["filename"] = existing.get("filename", "Image Upload")
        payload["vision"] = existing.get("vision")
        payload["quality"] = existing.get("quality")
        payload["overall_quality_score"] = existing.get("overall_quality_score")
        payload["annotated_image_base64"] = existing.get("annotated_image_base64")
        payload["detections"] = existing.get("detections")
        payload["detection_count"] = existing.get("detection_count")
        
        history.upsert_diagnosed_case(payload)
    else:
        # TEXT WORKFLOW: Create a brand new case and provide safe empty defaults for the UI
        payload["filename"] = "Text Description"
        payload["annotated_image_base64"] = ""
        payload["overall_quality_score"] = 0
        payload["quality"] = {}
        payload["vision"] = {}
        payload["detections"] = []
        payload["detection_count"] = 0
        
        session_id = history.create_case(payload)

    # 4. Return the complete package to the frontend
    return {
        "session_id": session_id,
        "defect_class": result.defect_class,
        "defect_label": result.defect_label,
        "confidence": result.confidence,
        "possible_symptoms": symptoms,
        "ai_explanation": reasoning_text,
        "cause_table": [
            {
                "cause": c["cause_id"],
                "name": c["name"],
                "score": f"{int(c['likelihood_pct'])}%",
                "score_num": int(c['likelihood_pct']),
                "reasoning": c["reasoning"]
            } for c in formatted_causes[:3] 
        ],
        "action_plan": formatted_actions
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
            "reasoning_diagnose": "POST /reasoning/diagnose",
            "qa": "POST /qa (fast rule-based; optional use_gemini=true)",
            "history": "GET /history",
            "case": "GET /cases/{session_id}",
            "report": "GET /report/{session_id}?format=pdf|docx",
            "report_data": "GET /report/{session_id}/data",
            "report_preview": "GET /report/{session_id}/preview",
        },
    }


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    user_email: str | None = Form(None),
) -> dict[str, Any]:
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
        "user_email": user_email,
        "filename": file.filename,
        "user_email": user_email or None,
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
            "user_email": payload.user_email or analysis.get("user_email"),
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


@app.post("/reasoning/diagnose")
def multimodal_reasoning_diagnose(payload: FusionDiagnoseRequest) -> dict[str, Any]:
    """Run the evidence-first multimodal pipeline and return its full diagnostic trace."""
    try:
        questions = [QuestionOption(**question) for question in payload.questions]
        result = MultimodalEvidenceFusion().diagnose(
            questionnaire=payload.questionnaire,
            vision=payload.vision,
            process_parameters=payload.process_parameters,
            historical_cases=payload.historical_cases,
            cause_ids=payload.cause_ids,
            questions=questions,
            inputs=payload.inputs,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid reasoning input: {exc}") from exc
    return result.as_dict()


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
def list_history(limit: int = 50, user_email: str | None = None) -> dict[str, Any]:
    email = user_email.strip() if user_email and user_email.strip() else None
    cases = history.list_cases(limit=max(1, min(limit, 200)), user_email=email)
    return {"cases": cases, "count": len(cases), "total": history.count_cases(user_email=email)}


@app.get("/history/analytics")
def history_analytics(
    user_email: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    email = user_email.strip() if user_email and user_email.strip() else None
    return history.get_history_analytics(user_email=email, year=year, month=month)



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


class TextDescription(BaseModel):
    text: str


@app.post("/api/extract_symptoms")
def extract_symptoms(payload: TextDescription):
    """Extracts structured variables from a user's free-text defect description."""
    import json
    import re
    import google.generativeai as genai

    api_key = get_settings().gemini_api_key

    def fallback_extraction(text: str) -> dict[str, str]:
        text_lower = text.lower()

        amt = "unknown"
        if re.search(r'\b(too small|insufficient|starved|thin|little|low volume|under-deposit|undersized?)\b', text_lower):
            amt = "too_small"
        elif re.search(r'\b(too large|excess|slump|spreading|overflow|too much|high volume|oversized?)\b', text_lower):
            amt = "too_large"
        elif re.search(r'\b(inconsistent|fluctuat|irregular|stringing|tailing|dog-?ears?)\b', text_lower):
            amt = "inconsistent"
        elif re.search(r'\b(missing|skipped|no deposit|zero)\b', text_lower):
            amt = "missing"

        freq = "unknown"
        # 1. Check idle/startup specifically FIRST
        if re.search(r'\b(first few|idle|break|start-?up)\b', text_lower):
            freq = "after_idle"
        # 2. Check progressive (starts normal, gets worse over time/hours)
        elif re.search(r'\b(getting worse|after.*running|few hours|over time|progressive|starts normal)\b', text_lower):
            freq = "progressive"
        # 3. Check generic occasional
        elif re.search(r'\b(not every|doesn\'t happen on every|does not happen on every|occasionally|occasional|intermittent|random|sometimes|sporadic)\b', text_lower):
            freq = "occasional"
        # 4. Check continuous
        elif re.search(r'\b(continuous|continuously|every single board|every board|all the time|always|every target|every dot)\b', text_lower):
            freq = "continuous"

        loc = "unknown"
        # Check multiple FIRST so phrases like 'every single board' don't trigger 'single'
        if re.search(r'\b(all locations|across all|all dispensing|everywhere|entire board|entire array|multiple|scattered|random spots|different spots)\b', text_lower):
            loc = "multiple"
        elif re.search(r'\b(single location|single specific|single pad|single pin|one specific|one pad|one pin|isolated)\b', text_lower):
            loc = "single"

        rec = "unknown"
        if re.search(r'\b(nozzle|micro-nozzle|tip|needle|orifice)\b', text_lower):
            rec = "nozzle"
        elif re.search(r'\b(syringe|barrel|batch|cartridge|new paste|new material)\b', text_lower):
            rec = "syringe"
        elif re.search(r'\b(pressure|timer|standoff|parameter|recipe|speed)\b', text_lower):
            rec = "parameters"
        elif re.search(r'\b(no change|baseline|unchanged|same setup)\b', text_lower):
            rec = "none"

        return {"amount": amt, "frequency": freq, "location": loc, "recent_change": rec}

    # Only attempt cloud Gemini call if an official Google AI Studio key (starts with AIza) is present
    if not api_key or not api_key.startswith("AIza"):
        return fallback_extraction(payload.text)

    try:
        genai.configure(api_key=api_key)
        prompt = f"""
        Analyze this manufacturing defect description: "{payload.text}"
        Extract the symptoms and output ONLY a JSON object with these exact keys and allowed values:
        - amount: "too_small", "too_large", "inconsistent", "missing", "spreading", "irregular", "stringing", or "unknown"
        - frequency: "continuous", "occasional", "progressive", "after_idle", or "unknown" 
        - location: "single", "multiple", or "unknown"
        - recent_change: "nozzle", "syringe", "parameters", "none", or "unknown"

        Strict Extraction Rules:
        1. For the 'location' field, carefully distinguish between the number of boards and the number of dispensing locations on the board.
        2. If the user mentions "all locations", "across all dispensing locations", "everywhere", "entire board", "multiple locations", or "random spots", you MUST output "multiple", even if the word "single" appears elsewhere in the text.
        3. Only output "single" if the defect is explicitly confined to one specific pad, pin, or single location on the PCB.
        4. For 'recent_change', always extract any hardware replacement, cleanings, or maintenance (e.g., "micro-nozzle", "new nozzle", "tip replaced" MUST map to "nozzle"). Map new syringe barrels or material batches to "syringe", and pressure/timing/standoff changes to "parameters".
        5. For 'frequency', if the defect occurs only on start-up, during the "first few dots", or after sitting idle/on a break, you MUST classify it as "after_idle".
        """

        model = genai.GenerativeModel(
            model_name=get_settings().gemini_model,
            generation_config={"response_mime_type": "application/json"}
        )

        # Enforce 3.5s timeout so cloud LLM never blocks or freezes UI
        response = model.generate_content(prompt, request_options={"timeout": 3.5})
        parsed = json.loads(response.text)
        
        # --- ADD THIS FAILSAFE ---
        # Force 'after_idle' or 'progressive' if the LLM gets confused by complex phrasing
        text_lower = payload.text.lower()
        if re.search(r'\b(first few|idle|break|start-?up)\b', text_lower):
            parsed["frequency"] = "after_idle"
        elif re.search(r'\b(getting worse|after.*running|few hours|over time|progressive|starts normal)\b', text_lower):
            parsed["frequency"] = "progressive"
        # -------------------------

        return {
            "amount": parsed.get("amount", "unknown"),
            "frequency": parsed.get("frequency", "unknown"),
            "location": parsed.get("location", "unknown"),
            "recent_change": parsed.get("recent_change", "unknown")
        }
    except Exception as exc:
        print(f"Gemini symptom extraction failed or timed out: {exc}, using fallback heuristic.")
        return fallback_extraction(payload.text)
