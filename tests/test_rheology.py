"""Unit tests for Physics-Based Rheology & Thermal Offset Calculator and Safety Boundary Guard."""

import math
from backend.app.reasoning.rheology import (
    BASELINE_TEMP_C,
    DEFAULT_BASELINE_PRESSURE_MPA,
    MAX_SAFE_PRESSURE_OFFSET_RATIO,
    calculate_rheology_offset,
)
from backend.app.reasoning.rank_causes import rank_causes


def test_rheology_baseline_nominal():
    res = calculate_rheology_offset("solder_paste", ambient_temp_c=23.0, pot_life_hours=0.5)
    assert res["delta_t_c"] == 0.0
    assert abs(res["viscosity_ratio"] - 1.0) < 0.001
    assert abs(res["viscosity_drift_pct"]) < 0.1
    assert res["pressure_offset_mpa"] == 0.0
    assert res["heater_offset_c"] == 0.0
    assert res["risk_level"] == "OPTIMAL"
    assert res["is_clamped"] is False


def test_rheology_warm_drift_solder_paste():
    # +3.0°C warm drift on solder paste
    res = calculate_rheology_offset("solder_paste", ambient_temp_c=26.0, pot_life_hours=1.0)
    assert res["delta_t_c"] == 3.0
    # Viscosity should drop (drift < 0)
    assert res["viscosity_drift_pct"] < -10.0
    assert res["viscosity_drift_pct"] > -15.0
    # Pressure should be reduced to compensate
    assert res["pressure_offset_mpa"] < 0.0
    assert res["heater_offset_c"] == -3.0
    assert res["primary_risk"] == "SPREADING_SLUMP"


def test_rheology_cold_drift_thickening():
    # Cold workshop (18°C -> -5°C drift)
    res = calculate_rheology_offset("solder_paste", ambient_temp_c=18.0, pot_life_hours=1.0)
    assert res["delta_t_c"] == -5.0
    # Viscosity increases
    assert res["viscosity_drift_pct"] > 15.0
    # Pressure offset should be positive to maintain volumetric flow
    assert res["pressure_offset_mpa"] > 0.0
    assert res["heater_offset_c"] == 5.0
    assert res["primary_risk"] == "CLOGGING_RESTRICTION"


def test_safety_boundary_guard_temperature_clamping():
    # Mistyped 230°C
    extreme_hot = calculate_rheology_offset("solder_paste", ambient_temp_c=230.0)
    assert extreme_hot["ambient_temp_c"] == 45.0
    assert extreme_hot["is_clamped"] is True
    assert not math.isnan(extreme_hot["viscosity_ratio"])
    assert not math.isinf(extreme_hot["viscosity_ratio"])

    # Mistyped -10°C
    extreme_cold = calculate_rheology_offset("solder_paste", ambient_temp_c=-10.0)
    assert extreme_cold["ambient_temp_c"] == 10.0
    assert extreme_cold["is_clamped"] is True


def test_safety_boundary_guard_pressure_cap():
    # Even under extreme conditions, pressure compensation must not exceed +/-30%
    extreme_hot = calculate_rheology_offset("silver_epoxy", ambient_temp_c=45.0)
    max_safe = DEFAULT_BASELINE_PRESSURE_MPA * MAX_SAFE_PRESSURE_OFFSET_RATIO
    assert abs(extreme_hot["pressure_offset_mpa"]) <= max_safe + 1e-6
    assert abs(extreme_hot["pressure_offset_pct"]) <= 30.0 + 1e-6

    extreme_cold = calculate_rheology_offset("silver_epoxy", ambient_temp_c=10.0)
    assert abs(extreme_cold["pressure_offset_mpa"]) <= max_safe + 1e-6
    assert abs(extreme_cold["pressure_offset_pct"]) <= 30.0 + 1e-6


def test_thixotropic_pot_life_alert():
    fresh = calculate_rheology_offset("solder_paste", ambient_temp_c=23.0, pot_life_hours=2.0)
    assert fresh["thixotropic_alert"] is None

    aged = calculate_rheology_offset("solder_paste", ambient_temp_c=23.0, pot_life_hours=8.0)
    assert aged["thixotropic_alert"] is not None
    assert "dummy purge shots" in aged["thixotropic_alert"].lower()
    assert aged["primary_risk"] == "POT_LIFE_EXPIRED"


def test_rank_causes_dynamic_thermal_integration():
    # Warm drift at 28°C causes thermal thinning and fires evidence
    symptoms = {
        "material": "solder_paste",
        "pattern": "dot",
        "defect_class": "spreading",
        "ambient_temp_c": 28.0,
        "pot_life_hours": 1.0,
    }
    res = rank_causes(symptoms)
    assert "rheology" in res
    assert res["rheology"]["delta_t_c"] == 5.0
    assert res["rheology"]["viscosity_drift_pct"] < -15.0

    # Viscosity temp humidity should have evidence fired
    top_cause_ids = [c["id"] for c in res["ranked_causes"]]
    assert "viscosity_temp_humidity" in top_cause_ids
    rule_ids = [f["id"] for f in res["fired_rules"]]
    assert "thermal_thinning_drift" in rule_ids
