"""
cloud_ingest.py  — project-root convenience wrapper
====================================================
This file is kept for reference only.
The actual implementation lives in:   backend/cloud/ingest.py

Usage from the terminal:
    python -c "from backend.cloud.ingest import upload_incident_to_cloud; upload_incident_to_cloud(...)"

Or import directly in your scripts:
    from backend.cloud.ingest import upload_learning_case, upload_incident_to_cloud
"""
from backend.cloud.ingest import upload_incident_to_cloud  # re-export

__all__ = ["upload_incident_to_cloud"]