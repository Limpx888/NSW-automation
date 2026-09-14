"""
backend/cloud/ingest.py
Uploads a resolved learning case (with vector embedding) to Supabase.

Called automatically by backend/learning.py after a new learning case is
created or updated, so every diagnosis that produces a confirmed fix is
mirrored to the cloud knowledge base.

Can also be run directly as a one-off:
    python -m backend.cloud.ingest
"""

from __future__ import annotations

import json
from typing import Any

from backend.cloud.embeddings import embed
from backend.cloud.supabase_client import get_client


# ── Supabase table name ──────────────────────────────────────────────────────
FAILURE_LOGS_TABLE = "failure_logs"


def _build_context_str(
    defect_type: str,
    problem: str,
    root_cause: str,
    action: str,
    defect_label: str = "",
    pressure: float | None = None,
    viscosity: float | None = None,
    size_um: float | None = None,
) -> str:
    """Build a rich natural-language string for vectorisation."""
    parts = [f"Defect: {defect_type}"]
    if defect_label and defect_label != defect_type:
        parts.append(f"Label: {defect_label}")
    if size_um is not None:
        parts.append(f"Size: {size_um:.1f}µm")
    if pressure is not None:
        parts.append(f"Pressure: {pressure:.2f} bar")
    if viscosity is not None:
        parts.append(f"Viscosity: {viscosity:.1f} cps")
    if problem:
        parts.append(f"Problem: {problem}")
    if root_cause:
        parts.append(f"Root Cause: {root_cause}")
    if action:
        parts.append(f"Action: {action}")
    return ". ".join(parts)


def upload_learning_case(
    case: dict[str, Any],
    *,
    pressure: float | None = None,
    viscosity: float | None = None,
    size_um: float | None = None,
) -> dict[str, Any]:
    """
    Sync a local learning case to Supabase failure_logs.

    Parameters
    ----------
    case : dict from learning.upsert_from_diagnosis / learning.mark_successful_solution
    pressure, viscosity, size_um : optional process telemetry from the inspection run

    Returns a dict with status (ok|skipped|error) and optional Supabase response.
    """
    client = get_client()
    if client is None:
        return {"status": "skipped", "reason": "Supabase client not configured"}

    defect_type = case.get("defect_class") or ""
    defect_label = case.get("defect_label") or ""
    problem = case.get("dispensing_problem") or ""
    root_cause = case.get("successful_cause") or ""
    action = case.get("successful_solution") or ""

    # Only sync when a successful resolution is known
    if not root_cause and not action:
        return {"status": "skipped", "reason": "No confirmed resolution to sync yet"}

    context_str = _build_context_str(
        defect_type=defect_type,
        defect_label=defect_label,
        problem=problem,
        root_cause=root_cause,
        action=action,
        pressure=pressure,
        viscosity=viscosity,
        size_um=size_um,
    )

    embedding = embed(context_str)
    if embedding is None:
        return {"status": "error", "reason": "Embedding model unavailable"}

    row = {
        "case_id": case.get("case_id"),
        "session_id": case.get("session_id"),
        "defect_type": defect_type,
        "defect_label": defect_label,
        "dispensing_problem": problem,
        "root_cause": root_cause,
        "resolution_action": action,
        "possible_causes": json.dumps(case.get("possible_causes") or []),
        "recommended_solutions": json.dumps(case.get("recommended_solutions") or []),
        "embedding": embedding,
    }
    if pressure is not None:
        row["pressure_bar"] = pressure
    if viscosity is not None:
        row["viscosity_cps"] = viscosity
    if size_um is not None:
        row["measured_size_um"] = size_um

    try:
        response = (
            client.table(FAILURE_LOGS_TABLE)
            .upsert(row, on_conflict="case_id")
            .execute()
        )
        return {"status": "ok", "data": response.data}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": str(exc)}


def upload_incident_to_cloud(
    defect_type: str,
    size_um: float,
    pressure: float,
    viscosity: float,
    root_cause: str,
    action: str,
) -> None:
    """Legacy helper matching the original cloud_ingest.py API surface."""
    case = {
        "defect_class": defect_type,
        "dispensing_problem": f"Defect: {defect_type}",
        "successful_cause": root_cause,
        "successful_solution": action,
    }
    result = upload_learning_case(
        case,
        pressure=pressure,
        viscosity=viscosity,
        size_um=size_um,
    )
    print("Cloud ingest result:", result)
