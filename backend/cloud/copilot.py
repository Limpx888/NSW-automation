"""
backend/cloud/copilot.py
Vector search against Supabase failure_logs using cosine similarity.

Replaces the original cloud_copilot.py — now properly integrated into
the backend module structure and using Settings for credentials.
"""

from __future__ import annotations

from typing import Any

from backend.cloud.embeddings import embed
from backend.cloud.supabase_client import get_client

# Name of the SQL function deployed in Supabase (see setup SQL below)
MATCH_FUNCTION = "match_failure_logs"


def search_similar_incidents(
    defect_type: str,
    *,
    problem: str = "",
    size_um: float | None = None,
    pressure: float | None = None,
    viscosity: float | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Find similar past incidents in the Supabase cloud knowledge base.

    Returns a list of matching rows (similarity score included).
    Returns [] gracefully if Supabase is not configured or unavailable.
    """
    client = get_client()
    if client is None:
        return []

    parts = [f"Defect: {defect_type}"]
    if problem:
        parts.append(f"Problem: {problem}")
    if size_um is not None:
        parts.append(f"Size: {size_um:.1f}µm")
    if pressure is not None:
        parts.append(f"Pressure: {pressure:.2f} bar")
    if viscosity is not None:
        parts.append(f"Viscosity: {viscosity:.1f} cps")
    query_str = ". ".join(parts)

    query_vector = embed(query_str)
    if query_vector is None:
        return []

    try:
        response = client.rpc(
            MATCH_FUNCTION,
            {"query_embedding": query_vector, "match_count": top_k},
        ).execute()
        return response.data or []
    except Exception as exc:  # noqa: BLE001
        print(f"[cloud.copilot] Vector search failed: {exc}")
        return []
