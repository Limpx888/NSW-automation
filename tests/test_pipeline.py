from backend.app.db.cases import seed_if_empty, similar_cases
from backend.app.pipeline import run_session
from backend.app.reasoning.discover import is_complete, next_question
from backend.app.reports.pdf import build_pdf
from model.synthesize import render_image


def test_discovery_then_followup():
    answers = {}
    q = next_question(answers)
    assert q["id"] == "material"
    answers["material"] = "solder_paste"
    answers["pattern"] = "dot"
    answers["amount"] = "too_small"
    answers["frequency"] = "continuous"
    answers["recent_change"] = "nozzle"
    answers["location"] = "multiple"
    q = next_question(answers)
    assert q["id"] == "powder_type"
    answers["powder_type"] = "T6"
    q = next_question(answers, include_optional=False)
    assert q is not None
    assert q["id"] == "onset"
    answers["onset"] = "from_start"
    assert is_complete(answers)


def test_pdf_and_similar_cases(tmp_path):
    db = tmp_path / "cases.db"
    seed_if_empty(db)
    similar = similar_cases("solder_paste", "under_dispense", db)
    assert similar["total"] >= 2
    img, _ = render_image("under_dispense", "solder_paste", "dot", seed=3, do_augment=False)
    result = run_session(
        {
            "material": "solder_paste",
            "pattern": "dot",
            "amount": "too_small",
            "frequency": "continuous",
            "recent_change": "nozzle",
            "location": "multiple",
            "powder_type": "T6",
            "nozzle_id_um": 60,
        },
        image_bgr=img,
    )
    pdf = build_pdf(result, dest=tmp_path / "report.pdf")
    assert pdf[:4] == b"%PDF"
    assert result["ranked_causes"][0]["id"] in {"powder_nozzle_mismatch", "nozzle_partial_clog"}
    assert "similar" in result
