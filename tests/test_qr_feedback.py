"""Tests for Interactive Maintenance Sheet with Feedback QR Code & Mobile Feedback."""

import pytest
from fastapi.testclient import TestClient
from backend.app.db.cases import get_case_by_session_id, log_case, update_case_feedback
from backend.app.main import app
from backend.app.reports.pdf import build_pdf, get_feedback_url, get_local_ip


def test_local_ip_and_feedback_url():
    ip = get_local_ip()
    assert ip is not None
    assert len(ip) >= 7

    url = get_feedback_url("session-abc-123")
    assert "session-abc-123" in url
    assert "/quick-feedback?session_id=" in url


def test_pdf_generation_with_qr_code():
    session = {
        "session_id": "test-qr-session-999",
        "material": "solder_paste",
        "pattern": "dot",
        "defect_class": "under_dispense",
        "ranked_causes": [{"id": "nozzle_partial_clog", "name": "Partial Nozzle Clog", "likelihood_pct": 55.0}],
    }
    pdf_bytes = build_pdf(session)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")


import uuid

def test_db_feedback_operations():
    # 1. Create a test session
    session_id = f"test-feedback-{uuid.uuid4().hex[:10]}"
    log_case({
        "session_id": session_id,
        "material": "solder_paste",
        "pattern": "dot",
        "defect_class": "under_dispense",
        "ranked_causes": [{"id": "nozzle_partial_clog", "name": "Partial Nozzle Clog", "likelihood_pct": 60.0}],
        "explanation": "Test explanation",
    })

    # 2. Retrieve case
    case = get_case_by_session_id(session_id)
    assert case is not None
    assert case["session_id"] == session_id
    assert case["material"] == "solder_paste"
    assert case["is_resolved"] == 0

    # 3. Update feedback
    updated = update_case_feedback(
        session_id=session_id,
        status="RESOLVED",
        confirmed_cause="nozzle_partial_clog",
        operator_notes="Swapped nozzle tip on shop floor in 2 mins.",
    )
    assert updated is True

    # 4. Verify updated state in DB
    updated_case = get_case_by_session_id(session_id)
    assert updated_case["is_resolved"] == 1
    assert updated_case["confirmed_cause"] == "nozzle_partial_clog"
    assert "Swapped nozzle tip" in updated_case["operator_notes"]


def test_api_case_endpoints():
    client = TestClient(app)
    session_id = f"test-api-session-{uuid.uuid4().hex[:10]}"
    log_case({
        "session_id": session_id,
        "material": "silver_epoxy",
        "pattern": "line",
        "defect_class": "inconsistent_volume",
        "ranked_causes": [{"id": "filler_settling", "name": "Filler Settling", "likelihood_pct": 50.0}],
    })

    # GET /cases/{session_id}
    res_get = client.get(f"/cases/{session_id}")
    assert res_get.status_code == 200
    assert res_get.json()["session_id"] == session_id

    # POST /cases/feedback
    res_post = client.post(
        "/cases/feedback",
        json={
            "session_id": session_id,
            "status": "RESOLVED",
            "confirmed_cause": "filler_settling",
            "operator_notes": "Rolled syringe on 10 RPM roller for 3 minutes.",
        },
    )
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["status"] == "ok"
    assert data["is_resolved"] is True
    assert data["confirmed_cause"] == "filler_settling"

    # Verify via GET again
    res_verify = client.get(f"/cases/{session_id}")
    assert res_verify.json()["is_resolved"] == 1
    assert res_verify.json()["confirmed_cause"] == "filler_settling"
