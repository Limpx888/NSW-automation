"""Physics-Based Rheology & Thermal Offset Calculator.

Applies the Arrhenius viscosity equation and Poiseuille flow approximation
to quantify temperature-induced viscosity drift and compute machine parameter offsets.
"""

from __future__ import annotations

import math
from typing import Any

# Standard cleanroom baseline temperature
BASELINE_TEMP_C = 23.0
BASELINE_TEMP_K = 273.15 + BASELINE_TEMP_C  # 296.15 K

# Standard pneumatic dispensing baseline pressure
DEFAULT_BASELINE_PRESSURE_MPA = 0.20  # 0.20 MPa (2.0 bar)

# Universal gas constant in J/(mol·K)
R_GAS_CONSTANT = 8.314

# Activation energy (Ea in J/mol) for common electronics dispensing fluids
# Source: IPC-TM-650, AIM Solder & Nordson EFD Rheology Application Notes
MATERIAL_ACTIVATION_ENERGY: dict[str, float] = {
    "solder_paste": 32000.0,    # Solder paste (thixotropic, medium-high sensitivity)
    "silver_epoxy": 38000.0,    # Filled silver epoxy (high thermal sensitivity, slump prone)
    "uv_glue": 28000.0,         # UV acrylic/epoxy adhesive
    "silicone_gel": 22000.0,    # Silicone encapsulant / gel (lower thermal sensitivity)
}
DEFAULT_ACTIVATION_ENERGY = 30000.0

# Safety boundary limits
MIN_SAFE_TEMP_C = 10.0
MAX_SAFE_TEMP_C = 45.0
MAX_SAFE_PRESSURE_OFFSET_RATIO = 0.30  # Capped at +/-30% max offset for hardware safety
MAX_POT_LIFE_HOURS = 72.0


def calculate_rheology_offset(
    material: str,
    ambient_temp_c: float | int | None = None,
    pot_life_hours: float | int | None = None,
    baseline_pressure_mpa: float = DEFAULT_BASELINE_PRESSURE_MPA,
) -> dict[str, Any]:
    """Calculate dynamic viscosity drift and recommended machine offsets.
    
    Uses Arrhenius equation:
        eta(T) = eta_0 * exp( (Ea / R) * (1/T - 1/T_0) )
    and Poiseuille flow compensation:
        Delta_P = P_baseline * (eta(T)/eta_0 - 1)
    """
    raw_temp = float(ambient_temp_c if ambient_temp_c is not None else BASELINE_TEMP_C)
    raw_pot_life = float(pot_life_hours if pot_life_hours is not None else 0.5)

    # 1. Safety boundary clamping
    clamped_temp_c = max(MIN_SAFE_TEMP_C, min(MAX_SAFE_TEMP_C, raw_temp))
    clamped_pot_life = max(0.0, min(MAX_POT_LIFE_HOURS, raw_pot_life))

    temp_k = 273.15 + clamped_temp_c
    delta_t_c = clamped_temp_c - BASELINE_TEMP_C

    # 2. Arrhenius viscosity ratio calculation
    mat_key = (material or "solder_paste").lower().replace(" ", "_")
    ea = MATERIAL_ACTIVATION_ENERGY.get(mat_key, DEFAULT_ACTIVATION_ENERGY)

    # Exponent: (Ea / R) * (1/T - 1/T_0)
    exponent = (ea / R_GAS_CONSTANT) * ((1.0 / temp_k) - (1.0 / BASELINE_TEMP_K))
    viscosity_ratio = math.exp(exponent)
    viscosity_drift_pct = (viscosity_ratio - 1.0) * 100.0

    # 3. Poiseuille flow pressure compensation (Delta_P)
    # Q proportional to Delta_P / eta -> to keep Q constant: P_new = P_0 * (eta / eta_0)
    # Delta_P = P_new - P_0 = P_0 * (viscosity_ratio - 1)
    computed_pressure_offset = baseline_pressure_mpa * (viscosity_ratio - 1.0)
    max_offset_mpa = baseline_pressure_mpa * MAX_SAFE_PRESSURE_OFFSET_RATIO
    clamped_pressure_offset_mpa = max(-max_offset_mpa, min(max_offset_mpa, computed_pressure_offset))
    pressure_offset_pct = (clamped_pressure_offset_mpa / baseline_pressure_mpa) * 100.0

    # Thermal heater offset (offset the ambient drift if dispenser has nozzle heater)
    heater_offset_c = -round(delta_t_c, 1)

    # 4. Risk classification
    abs_drift = abs(viscosity_drift_pct)
    if abs_drift < 5.0 and clamped_pot_life <= 6.0:
        risk_level = "OPTIMAL"
        primary_risk = "NOMINAL"
    elif abs_drift < 12.0 and clamped_pot_life <= 8.0:
        risk_level = "MODERATE_DRIFT"
        primary_risk = "SPREADING_SLUMP" if delta_t_c > 0 else "CLOGGING_RESTRICTION"
    else:
        risk_level = "HIGH_DRIFT"
        primary_risk = "SPREADING_SLUMP" if delta_t_c > 0 else "CLOGGING_RESTRICTION"

    if clamped_pot_life > 6.0:
        risk_level = "HIGH_DRIFT" if risk_level == "HIGH_DRIFT" else "MODERATE_DRIFT"
        primary_risk = "POT_LIFE_EXPIRED"

    # 5. Diagnostic Alert & Recommendations
    thixotropic_alert = None
    if clamped_pot_life > 6.0:
        thixotropic_alert = (
            f"Fluid open lifetime ({clamped_pot_life:.1f}h) exceeds standard 6h window. "
            "Execute 3 continuous dummy purge shots to re-homogenize fluid structure."
        )

    if delta_t_c > 0.5:
        alert_message = (
            f"Ambient temperature +{delta_t_c:.1f}°C above nominal (23°C) causes an estimated "
            f"viscosity drop of {viscosity_drift_pct:.1f}%. Spreading and slump risk increased."
        )
    elif delta_t_c < -0.5:
        alert_message = (
            f"Ambient temperature {delta_t_c:.1f}°C below nominal (23°C) causes an estimated "
            f"viscosity rise of +{viscosity_drift_pct:.1f}%. Risk of flow restriction or partial clog."
        )
    else:
        alert_message = (
            f"Ambient workshop temperature ({clamped_temp_c:.1f}°C) is within nominal standard operating window (±0.5°C)."
        )

    return {
        "material": mat_key,
        "ambient_temp_c": round(clamped_temp_c, 1),
        "raw_temp_c": raw_temp,
        "delta_t_c": round(delta_t_c, 1),
        "viscosity_ratio": round(viscosity_ratio, 3),
        "viscosity_drift_pct": round(viscosity_drift_pct, 1),
        "pot_life_hours": round(clamped_pot_life, 1),
        "risk_level": risk_level,
        "primary_risk": primary_risk,
        "alert_message": alert_message,
        "pressure_offset_mpa": round(clamped_pressure_offset_mpa, 4),
        "pressure_offset_pct": round(pressure_offset_pct, 1),
        "heater_offset_c": heater_offset_c,
        "thixotropic_alert": thixotropic_alert,
        "is_clamped": raw_temp != clamped_temp_c or raw_pot_life != clamped_pot_life,
    }
