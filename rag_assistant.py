"""
rag_assistant.py  — project-root convenience wrapper
=====================================================
This file is kept for reference only.
The actual implementation lives in:   backend/cloud/rag_assistant.py

Usage:
    from backend.cloud.rag_assistant import generate_technician_guidance
    result = generate_technician_guidance("missing_dot", problem="skipped deposits after nozzle swap")
    print(result["guidance"])

Or call it through the FastAPI endpoint:
    POST /cloud/rag
    { "defect_type": "missing_dot", "problem": "...", "pressure": 1.1, "viscosity": 360 }
"""
from backend.cloud.rag_assistant import generate_technician_guidance  # re-export

__all__ = ["generate_technician_guidance"]