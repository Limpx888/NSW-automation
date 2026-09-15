"""
Single source of truth for what a report contains.
Both the DOCX and PDF renderers consume this SAME object — this is what
keeps the two formats from drifting apart as you add features.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Cause(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    explanation: str


class QualitySubScore(BaseModel):
    label: str
    stars: int = Field(ge=0, le=5)
    value: float | None = None


class ChartSlice(BaseModel):
    label: str
    value: float


class DetectionRow(BaseModel):
    id: int | str
    defect_class: str
    confidence_pct: float
    area_px: float | None = None


class ReportData(BaseModel):
    session_id: str
    generated_at: datetime
    title: str = "AI DISPENSING DEFECT DETECTOR"
    subtitle: str = "REPORT SUMMARY"
    brand: str = "DARA"
    footer: str = "Precision Automation Technology"
    problem_description: str
    defect: str
    defect_confidence_stars: int = Field(ge=0, le=5)
    defect_confidence_pct: float = 0
    severity: str = "MODERATE"
    yield_pct: float = 0
    detection_count: int = 0
    causes: list[Cause]
    quality_subscores: list[QualitySubScore]
    overall_quality_score: int = Field(ge=0, le=100)
    defect_distribution: list[ChartSlice] = Field(default_factory=list)
    analysis_statistics: list[ChartSlice] = Field(default_factory=list)
    detections: list[DetectionRow] = Field(default_factory=list)
    executive_summary: str = ""
    process_insight: str = ""
    diagnostic_findings: list[str] = Field(default_factory=list)
    maintenance_items: list[str] = Field(default_factory=list)
    action_plan: list[str]
    engineer_notes: str | None = None
    similar_case_note: str | None = None
    deep_analysis: str | None = None
    methodology_note: str = (
        "Automated analysis combines quantitative vision metrics (mask pixel areas, "
        "defect counts, confidence levels) with qualitative Q&A inputs to calculate "
        "defect distributions, assess process yield, and generate natural language "
        "maintenance insights."
    )
