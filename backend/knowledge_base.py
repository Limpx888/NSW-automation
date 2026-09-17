"""
backend/knowledge_base.py
Structured Knowledge Graph & Relational Mapping for DARA.

Provides industrial-grade defect-cause-solution relational mapping to avoid
one-size-fits-all default templates.
"""

from __future__ import annotations

from typing import Any

# Industrial-grade structured knowledge mapping table
DEFECT_KNOWLEDGE_MAP: dict[str, dict[str, list[str]]] = {
    "insufficient_volume": {
        "causes": [
            "Partial nozzle tip clogging with dried flux",
            "Squeegee / dispensing fluid pressure too low",
            "Cold solder paste dispensed before full room temperature warmup",
        ],
        "solutions": [
            "Clean stencil apertures and nozzle tip thoroughly using IPA ultrasonic cleaning.",
            "Increase squeegee/dispense pressure by 1-2 kg (approx. +0.05 MPa).",
            "Check solder paste lot number and replace with fresh material from cold storage.",
        ],
    },
    "too_little": {
        "causes": [
            "Partial nozzle tip clogging with dried flux",
            "Squeegee / dispensing fluid pressure too low",
            "Cold solder paste dispensed before full room temperature warmup",
        ],
        "solutions": [
            "Clean stencil apertures and nozzle tip thoroughly using IPA ultrasonic cleaning.",
            "Increase squeegee/dispense pressure by 1-2 kg (approx. +0.05 MPa).",
            "Check solder paste lot number and replace with fresh material from cold storage.",
        ],
    },
    "excess_volume": {
        "causes": [
            "Excessive stencil aperture size or prolonged dispense pulse on-time",
            "Squeegee pressure too low or slumping from elevated shop temperature (>26°C)",
            "Nozzle standoff Z-height clearance too small against pad",
        ],
        "solutions": [
            "Optimize stencil design by reducing aperture area by 10-15% (or reduce on-time pulse by 10%).",
            "Adjust climate control to maintain shop floor at 22-25°C and 50% RH.",
            "Increase print speed and decrease separation snap-off speed.",
        ],
    },
    "too_much": {
        "causes": [
            "Excessive stencil aperture size or prolonged dispense pulse on-time",
            "Squeegee pressure too low or slumping from elevated shop temperature (>26°C)",
            "Nozzle standoff Z-height clearance too small against pad",
        ],
        "solutions": [
            "Optimize stencil design by reducing aperture area by 10-15% (or reduce on-time pulse by 10%).",
            "Adjust climate control to maintain shop floor at 22-25°C and 50% RH.",
            "Increase print speed and decrease separation snap-off speed.",
        ],
    },
    "tombstoning": {
        "causes": [
            "Asymmetrical thermal transfer across unequal copper trace heat sinks",
            "Uneven pad size distribution or asymmetric paste deposit volume",
            "Pick-and-place component placement coordinate offset",
        ],
        "solutions": [
            "Modify reflow profile to slow preheat ramp rate to < 1.5°C/sec.",
            "Balance copper distribution and pad design symmetry.",
            "Recalibrate pick-and-place component placement pressure and coordinates.",
        ],
    },
    "voiding": {
        "causes": [
            "Volatiles outgassing too fast during peak reflow",
            "Trapped moisture in PCB substrate or hygroscopic component packages",
            "Incorrect soak time in reflow thermal profile",
        ],
        "solutions": [
            "Extend the soak zone duration by 30 seconds to allow volatile gases to escape safely.",
            "Pre-bake PCBs at 125°C for 4 hours prior to SMT line assembly.",
            "Switch to an ultra-low voiding IPC Class 3 solder paste formulation.",
        ],
    },
    "solder_balling": {
        "causes": [
            "Rapid preheat ramp causing volatile solvent spattering",
            "Oxidized solder paste powder past expiration date",
            "Excessive component placement pressure squeezing paste onto mask",
        ],
        "solutions": [
            "Soften the thermal profile ramp rate in the preheat zone.",
            "Inspect and verify solder paste storage life and proper thawing procedure.",
            "Reduce component placement impact force to prevent paste squeezing.",
        ],
    },
    "shifting": {
        "causes": [
            "Conveyor belt vibration and mechanical shock in reflow oven",
            "Improper pad design or terminal pitch mismatch",
            "Imbalanced surface tension during paste melting phase",
        ],
        "solutions": [
            "Inspect and service the reflow oven transport rails, chain tension, and mesh conveyor.",
            "Redesign land patterns strictly according to IPC-7351 guidelines.",
            "Ensure uniform paste deposition across both component terminations.",
        ],
    },
    "stringing": {
        "causes": [
            "Incorrect suck-back / vacuum retract parameter on dispenser valve",
            "Nozzle orifice outer tip contamination with dried paste crust",
            "High dispensing speed causing paste shear-thinning separation",
        ],
        "solutions": [
            "Increase nozzle suck-back distance and lower Z-axis retract acceleration.",
            "Wipe and clean nozzle tip with lint-free solvent wipe before every shift.",
            "Optimize dispense pressure and cycle speed to prevent paste rheology breakdown.",
        ],
    },
    "cold_joint": {
        "causes": [
            "Peak reflow temperature below solder alloy liquidus threshold",
            "Oxidized component leads or contaminated PCB copper pads",
            "Mechanical vibration or movement of the board during solder solidification",
        ],
        "solutions": [
            "Verify thermocouple profile: ensure peak reflow is 20-30°C above liquidus.",
            "Inspect component lead solderability and store in moisture barrier bags.",
            "Eliminate conveyor vibrations during the cooling zone transition.",
        ],
    },
    "missing_deposit": {
        "causes": [
            "Nozzle tip orifice completely blocked by hardened solder paste plug",
            "Trapped air pocket in syringe barrel causing pneumatic compressibility",
            "Dispense valve solenoid actuator misfire or electrical disconnect",
        ],
        "solutions": [
            "Replace nozzle tip and flush fluid path with pressurized solvent purge.",
            "Purge syringe barrel tip-down until solid continuous bead appears.",
            "Test valve drive signal and inspect solenoid actuator coil resistance.",
        ],
    },
    "missing_dot": {
        "causes": [
            "Nozzle tip orifice completely blocked by hardened solder paste plug",
            "Trapped air pocket in syringe barrel causing pneumatic compressibility",
            "Dispense valve solenoid actuator misfire or electrical disconnect",
        ],
        "solutions": [
            "Replace nozzle tip and flush fluid path with pressurized solvent purge.",
            "Purge syringe barrel tip-down until solid continuous bead appears.",
            "Test valve drive signal and inspect solenoid actuator coil resistance.",
        ],
    },
    "air_bubble": {
        "causes": [
            "Piston tunneling inside syringe during high-frequency dispensing",
            "Air entrained during syringe decanting or paste cartridge transfer",
            "Fluctuating pneumatic pressure regulator supply",
        ],
        "solutions": [
            "Centrifuge syringe barrels at 2000 RPM for 3 minutes before mounting on line.",
            "Install double-wiper pistons to prevent paste blow-by along syringe walls.",
            "Calibrate pneumatic regulator and verify stable main plant air supply.",
        ],
    },
}


def get_mapped_knowledge(defect_class: str | None) -> dict[str, list[str]]:
    """Return causes and solutions mapped to defect_class, with domain-safe fallback."""
    if not defect_class:
        key = "insufficient_volume"
    else:
        key = str(defect_class).lower().strip().replace("-", "_").replace(" ", "_")

    if key in DEFECT_KNOWLEDGE_MAP:
        return DEFECT_KNOWLEDGE_MAP[key]

    # Partial keyword matching fallback
    for known_key, data in DEFECT_KNOWLEDGE_MAP.items():
        if known_key in key or key in known_key:
            return data

    return {
        "causes": [
            "Dispensing parameter drift from standard recipe",
            "Material viscosity variance due to ambient temperature change",
            "Nozzle standoff Z-height clearance misalignment",
        ],
        "solutions": [
            "Inspect current machine setup and verify against standard golden recipe.",
            "Check ambient booth temperature and humidity (target: 22-25°C, 50% RH).",
            "Clean and re-zero nozzle dispense tip against substrate calibration datum.",
        ],
    }
