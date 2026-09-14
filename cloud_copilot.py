"""
cloud_copilot.py  — project-root convenience wrapper
=====================================================
This file is kept for reference only.
The actual implementation lives in:   backend/cloud/copilot.py

Usage:
    from backend.cloud.copilot import search_similar_incidents
    results = search_similar_incidents("missing_dot", pressure=1.10, viscosity=360.0)
"""
from backend.cloud.copilot import search_similar_incidents  # re-export

__all__ = ["search_similar_incidents"]