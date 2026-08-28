from backend.app.reasoning.discover import is_complete, next_question, when_matches
from backend.app.reasoning.rank_causes import rank_causes


def test_discovery_walks_cores_then_material_followup():
    answers = {}
    q = next_question(answers)
    assert q["id"] == "material"
    seen = []
    while q:
        seen.append(q["id"])
        if q.get("options") == "number_or_skip":
            answers["_skipped"] = answers.get("_skipped", []) + [q["id"]]
        else:
            answers[q["id"]] = q["options"][0]
        q = next_question(answers)
    assert seen[0] == "material"
    assert "pattern" in seen
    assert "amount" in seen
    assert "powder_type" in seen


def test_occasional_underdispense_asks_restart_vs_runtime():
    answers = {
        "material": "solder_paste",
        "pattern": "dot",
        "amount": "too_small",
        "frequency": "occasional",
        "recent_change": "none",
        "location": "multiple",
        "powder_type": "T4",
    }
    q = next_question(answers, include_optional=False)
    assert q is not None
    assert q["id"] == "timing"
    assert "restart" in q["prompt"].lower()
    assert q["selected_by"] == "information_gain"
    answers["timing"] = "after_restart"
    assert is_complete(answers)


def test_when_matches_lists():
    assert when_matches({"amount": ["too_small", "missing"]}, {"amount": "too_small"})
    assert not when_matches({"amount": ["too_small", "missing"]}, {"amount": "too_large"})


def test_random_underdispense_plus_visible_bubbles():
    """Spec example: random under-dispense + visible syringe bubbles → air #1 with +35/+50."""
    result = rank_causes(
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
    air = next(c for c in result["ranked_causes"] if c["id"] == "air_trapped_syringe")
    clog = next(c for c in result["ranked_causes"] if c["id"] == "nozzle_partial_clog")
    assert result["ranked_causes"][0]["id"] == "air_trapped_syringe"
    assert air["match_score"] == 85
    assert clog["match_score"] == 30  # +40 under-dispense, -10 not continuous
    deltas = {item["rule_id"]: item["delta"] for item in air["evidence"]}
    assert deltas["random_volume"] == 35
    assert deltas["visible_syringe_bubbles"] == 50
    chain = result["reasoning_chain"]
    assert "Air bubble" in chain
    assert "85%" in chain
    assert "occasionally" in chain.lower() or "occasional" in chain.lower()
    assert "bubbles" in chain.lower()
    assert "no process parameters" in chain.lower()
    assert "trapped air" in chain.lower()
    assert result["action_plan"]
    assert result["family_ranked"][0]["id"] == "air_bubble"


def test_after_restart_boosts_air():
    result = rank_causes(
        {
            "material": "solder_paste",
            "pattern": "dot",
            "amount": "too_small",
            "frequency": "occasional",
            "recent_change": "none",
            "location": "multiple",
            "powder_type": "T4",
            "timing": "after_restart",
        }
    )
    assert any(rule["id"] == "after_restart_air" for rule in result["fired_rules"])
    assert result["ranked_causes"][0]["id"] == "air_trapped_syringe"
