"""Validated API intake models for dispensing diagnosis."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SolderPasteDiagnosisRequest(BaseModel):
    """Machine state and dynamic interview answers for a solder-paste diagnosis."""

    # Keep this endpoint explicitly scoped to solder-paste physics.
    material: str = Field(default="solder_paste", pattern="^solder_paste$")

    # Parameters consumed by the 5x nozzle rule and rheology scoring.
    powder_type: str = Field(default="T6", pattern="^(T3|T4|T5|T6)$")
    nozzle_id_um: int = Field(default=80, ge=1, description="Nozzle inner diameter in microns")
    ambient_temp_c: float = Field(default=24.5, description="Current cleanroom temperature in Celsius")
    pot_life_hours: float = Field(default=1.0, ge=0, description="Hours the syringe has been at room temperature")

    # Core and dynamic interview answers, such as amount, frequency, and timing.
    answers: dict[str, Any] = Field(default_factory=dict)

    def to_engine_input(self) -> dict[str, Any]:
        """Flatten the intake into the dictionary contract used by rank_causes."""
        return {
            **self.answers,
            "material": self.material,
            "powder_type": self.powder_type,
            "nozzle_id_um": self.nozzle_id_um,
            "ambient_temp_c": self.ambient_temp_c,
            "pot_life_hours": self.pot_life_hours,
        }
