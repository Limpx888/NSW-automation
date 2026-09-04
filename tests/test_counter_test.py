"""Unit tests for Hypothesis-Testing & Counter-Test Loop."""

import pytest
from backend.app.reasoning.counter_test import (
    apply_counter_test_feedback,
    get_verification_test_for_cause,
    select_next_verification_action,
)


def test_get_verification_test_for_cause():
    action = get_verification_test_for_cause("air_trapped_syringe")
    assert action["action_id"] == "purge_air_test"
    assert "Purge" in action["title"]
    assert action["penalty_factor"] < 1.0


def test_apply_feedback_unresolved_degrades_hypothesis():
    causes = [
        {"id": "air_trapped_syringe", "name": "Air Trapped in Syringe", "likelihood_pct": 70.0},
        {"id": "nozzle_partial_clog", "name": "Partial Nozzle Clog", "likelihood_pct": 20.0},
        {"id": "viscosity_temp_humidity", "name": "Viscosity Drift", "likelihood_pct": 10.0},
    ]

    res = apply_counter_test_feedback(causes, "purge_air_test", "unresolved", [])
    updated = res["ranked_causes"]

    # Air trapped should now be degraded, and nozzle clog should escalate
    air_cause = next(c for c in updated if c["id"] == "air_trapped_syringe")
    clog_cause = next(c for c in updated if c["id"] == "nozzle_partial_clog")

    assert air_cause["likelihood_pct"] < 30.0
    assert clog_cause["likelihood_pct"] > 40.0
    assert res["resolved"] is False
    assert len(res["elimination_pathway"]) == 1
    assert res["elimination_step"]["status"] == "ELIMINATED"


def test_apply_feedback_resolved_confirms_root_cause():
    causes = [
        {"id": "powder_nozzle_mismatch", "name": "5x Rule Mismatch", "likelihood_pct": 65.0},
        {"id": "nozzle_partial_clog", "name": "Partial Nozzle Clog", "likelihood_pct": 35.0},
    ]

    res = apply_counter_test_feedback(causes, "five_x_gauge_check", "resolved", [])
    assert res["resolved"] is True
    assert res["confirmed_cause"] == "powder_nozzle_mismatch"
    assert res["elimination_step"]["status"] == "CONFIRMED"


def test_fae_escalation_after_three_unresolved():
    causes = [
        {"id": "air_trapped_syringe", "name": "Air Trapped in Syringe", "likelihood_pct": 50.0},
        {"id": "nozzle_partial_clog", "name": "Partial Nozzle Clog", "likelihood_pct": 30.0},
        {"id": "pressure_time_low", "name": "Pressure Low", "likelihood_pct": 20.0},
    ]

    # Test 1
    res1 = apply_counter_test_feedback(causes, "purge_air_test", "unresolved", [])
    # Test 2
    res2 = apply_counter_test_feedback(res1["ranked_causes"], res1["next_test"]["action_id"], "unresolved", res1["elimination_pathway"])
    # Test 3
    res3 = apply_counter_test_feedback(res2["ranked_causes"], res2["next_test"]["action_id"], "unresolved", res2["elimination_pathway"])

    assert len(res3["elimination_pathway"]) == 3
    assert res3["next_test"]["action_type"] == "ESCALATE"
    assert "Escalate to Field Application Engineer" in res3["next_test"]["title"]


def test_api_counter_test_endpoints():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    causes = [
        {"id": "air_trapped_syringe", "name": "Air Trapped in Syringe", "likelihood_pct": 70.0},
        {"id": "nozzle_partial_clog", "name": "Partial Nozzle Clog", "likelihood_pct": 20.0},
    ]

    # Verify step
    resp = client.post(
        "/counter-test/verify",
        json={
            "current_causes": causes,
            "test_id": "purge_air_test",
            "feedback": "unresolved",
            "test_history": [],
            "session_id": "test-session-123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved"] is False
    assert len(data["elimination_pathway"]) == 1

    # Confirm step
    resp_confirm = client.post(
        "/counter-test/confirm",
        json={
            "session_id": "test-session-123",
            "confirmed_cause": "nozzle_partial_clog",
            "elimination_pathway": data["elimination_pathway"],
        },
    )
    assert resp_confirm.status_code == 200
    assert resp_confirm.json()["status"] == "ok"
