from backend.app.reasoning.discover import eligible_followups, next_question
from backend.app.reasoning.fuzzy import membership, when_strength
from backend.app.reasoning.rank_causes import rank_causes


def test_unknown_is_partial_membership():
    assert membership("visible_bubbles", "unknown", "yes") == 0.45
    assert membership("visible_bubbles", "yes", "yes") == 1.0
    assert membership("visible_bubbles", "no", "yes") == 0.0


def test_overlapping_amount_has_partial_mu():
    mu = when_strength(
        {"frequency": "occasional", "amount": ["too_small", "inconsistent", "missing", "broken_line"]},
        {"frequency": "occasional", "amount": "irregular"},
    )
    assert 0.4 <= mu < 1.0


def test_fuzzy_followup_for_similar_appearance():
    answers = {
        "material": "solder_paste",
        "pattern": "dot",
        "amount": "irregular",
        "frequency": "occasional",
        "recent_change": "none",
        "location": "multiple",
        "powder_type": "T4",
    }
    q = next_question(answers, include_optional=False)
    assert q is not None
    assert q["id"] == "timing"
    assert q["fuzzy_strength"] < 1.0
    assert q["selected_by"] == "fuzzy_gain"
    ids = {item["id"] for item in eligible_followups(answers)}
    assert "timing" in ids


def test_unknown_bubbles_scales_air_evidence():
    crisp = rank_causes(
        {
            "material": "solder_paste",
            "pattern": "dot",
            "amount": "too_small",
            "frequency": "occasional",
            "recent_change": "none",
            "location": "multiple",
            "powder_type": "T4",
            "visible_bubbles": "yes",
        }
    )
    fuzzy = rank_causes(
        {
            "material": "solder_paste",
            "pattern": "dot",
            "amount": "too_small",
            "frequency": "occasional",
            "recent_change": "none",
            "location": "multiple",
            "powder_type": "T4",
            "visible_bubbles": "unknown",
        }
    )
    crisp_air = next(c for c in crisp["ranked_causes"] if c["id"] == "air_trapped_syringe")
    fuzzy_air = next(c for c in fuzzy["ranked_causes"] if c["id"] == "air_trapped_syringe")
    crisp_bubbles = next(e for e in crisp_air["evidence"] if e["rule_id"] == "visible_syringe_bubbles")
    fuzzy_bubbles = next(e for e in fuzzy_air["evidence"] if e["rule_id"] == "visible_syringe_bubbles")
    assert crisp_bubbles["delta"] == 50
    assert abs(fuzzy_bubbles["delta"] - 22.5) < 0.05
    assert fuzzy_bubbles["membership"] == 0.45
    assert fuzzy_air["likelihood_pct"] < crisp_air["likelihood_pct"]
    assert fuzzy["ranked_causes"][0]["id"] == "air_trapped_syringe"
