from __future__ import annotations

from pathlib import Path

from backend import learning


def test_insights_match_assignment_example(tmp_path: Path) -> None:
    db = tmp_path / "learn.db"
    learning.connect(db).close()
    insights = learning.get_insights(defect_class="inconsistent_size", db_path=db)
    assert insights["similar_count"] == 12
    assert insights["top_cause_count"] == 8
    assert insights["top_cause"] == "Air trapped inside the syringe"
    assert "Similar problems occurred 12 times previously" in insights["insight"]
    assert "In 8 cases, the main cause was Air trapped inside the syringe" in insights["insight"]


def test_manual_case_and_success(tmp_path: Path) -> None:
    db = tmp_path / "learn.db"
    row = learning.create_manual_case(
        {
            "dispensing_problem": "Starved dots after lunch break",
            "possible_causes": ["Air trapped inside the syringe", "Thixotropic thickening"],
            "recommended_solutions": ["Purge the syringe", "Run dummy shots"],
            "defect_class": "insufficient_volume",
        },
        db_path=db,
    )
    assert row["dispensing_problem"].startswith("Starved")
    assert row["successful_solution"] is None

    updated = learning.mark_successful_solution(
        case_id=row["case_id"],
        successful_solution="Run dummy shots",
        successful_cause="Thixotropic thickening",
        db_path=db,
    )
    assert updated is not None
    assert updated["successful_solution"] == "Run dummy shots"
    assert updated["successful_cause"] == "Thixotropic thickening"


def test_diagnosis_upsert_then_insights_exclude_self(tmp_path: Path) -> None:
    db = tmp_path / "learn.db"
    bundle = learning.attach_to_diagnosis(
        {
            "session_id": "sess-1",
            "dispensing_problem": "Inconsistent dispensing volume; first dots after a break are starved or skipped.",
            "defect_class": "inconsistent_size",
            "defect_label": "Inconsistent size",
            "causes": [{"name": "Air trapped inside the syringe"}],
            "action_plan": [{"detail": "Purge the syringe barrel"}],
        },
        db_path=db,
    )
    assert bundle["learning_case"]["session_id"] == "sess-1"
    assert bundle["insights"]["similar_count"] == 12
    again = learning.upsert_from_diagnosis(
        {
            "session_id": "sess-1",
            "dispensing_problem": "Inconsistent dispensing volume updated",
            "defect_class": "inconsistent_size",
            "causes": [{"name": "Nozzle blockage"}],
            "action_plan": [{"detail": "Clean nozzle"}],
        },
        db_path=db,
    )
    assert again["case_id"] == bundle["learning_case"]["case_id"]
    assert "updated" in again["dispensing_problem"]
