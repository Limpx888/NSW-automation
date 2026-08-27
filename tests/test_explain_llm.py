from backend.app.reasoning.explain_llm import explain_with_llm
from backend.app.reasoning.rank_causes import rank_causes


def test_explain_llm_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = rank_causes(
        {
            "material": "solder_paste",
            "pattern": "dot",
            "defect_class": "under_dispense",
            "frequency": "continuous",
            "recent_change": "nozzle",
            "location": "multiple",
            "powder_type": "T6",
            "nozzle_id_um": 60,
        }
    )
    text = explain_with_llm(result)
    assert "under_dispense" in text or "undersized" in text.lower()
    assert "5x" in text.lower() or "80" in text or "nozzle" in text.lower()
