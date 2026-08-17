from backend.app.reasoning.rank_causes import explain_rules, rank_causes


def test_occasional_inconsistent_ranks_air_first():
    result = rank_causes(
        {
            "material": "solder_paste",
            "pattern": "dot",
            "defect_class": "inconsistent_volume",
            "frequency": "occasional",
            "recent_change": "none",
            "location": "multiple",
            "powder_type": "T4",
        }
    )
    assert result["ranked_causes"][0]["id"] == "air_trapped_syringe"
    assert any(rule["id"] == "occasional_points_to_air" for rule in result["fired_rules"])


def test_type6_fine_nozzle_underdispense_ranks_clog_and_five_x():
    result = rank_causes(
        {
            "material": "solder_paste",
            "pattern": "dot",
            "amount": "too_small",
            "frequency": "continuous",
            "recent_change": "nozzle",
            "location": "multiple",
            "powder_type": "T6",
            "nozzle_id_um": 60,
        }
    )
    top_ids = [c["id"] for c in result["ranked_causes"][:2]]
    assert "powder_nozzle_mismatch" in top_ids
    assert "nozzle_partial_clog" in top_ids
    assert any(rule["id"] == "five_x_nozzle_violation" for rule in result["fired_rules"])
    assert result["pattern_specific_name"] == "undersized_dot"
    text = explain_rules(result)
    assert "5×" in text or "5x" in text or "80" in text


def test_uv_glue_spreading_does_not_mention_powder():
    result = rank_causes(
        {
            "material": "uv_glue",
            "pattern": "dam_fill",
            "defect_class": "spreading",
            "frequency": "continuous",
            "recent_change": "none",
            "location": "multiple",
            "uv_barrel": "clear",
            "timing": "after_runtime",
        }
    )
    ids = [c["id"] for c in result["ranked_causes"]]
    assert "powder_nozzle_mismatch" not in ids
    assert result["pattern_specific_name"] == "dam_collapse"
    assert result["ranked_causes"][0]["id"] in {
        "viscosity_temp_humidity",
        "premature_uv_cure",
        "dam_flow_geometry",
        "pressure_time_high",
    }


def test_low_vision_confidence_flags_manual_review():
    result = rank_causes(
        {
            "material": "silicone_gel",
            "pattern": "line",
            "defect_class": "missing",
            "frequency": "occasional",
            "location": "single",
            "vision_confidence": 0.31,
        }
    )
    assert result["manual_review"] is True
    assert result["pattern_specific_name"] == "missing_segment"
