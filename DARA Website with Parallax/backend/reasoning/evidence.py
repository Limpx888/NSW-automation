from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evidence:
    """Single item of evidence supporting or contradicting a root cause."""

    id: str
    feature_name: str
    value: Any
    source: str
    reliability: float = 1.0
    supporting_causes: dict[str, float] = field(default_factory=dict)
    contradicting_causes: dict[str, float] = field(default_factory=dict)
    strength: float = 1.0
    explanation: str = ""
    timestamp: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reliability", max(0.0, min(1.0, float(self.reliability))))
        object.__setattr__(self, "strength", max(0.0, float(self.strength)))
        object.__setattr__(
            self,
            "supporting_causes",
            {str(k): max(0.0, float(v)) for k, v in (self.supporting_causes or {}).items()},
        )
        object.__setattr__(
            self,
            "contradicting_causes",
            {str(k): max(0.0, float(v)) for k, v in (self.contradicting_causes or {}).items()},
        )

    def supporting_for(self, cause_id: str) -> float:
        return float(self.supporting_causes.get(cause_id, 0.0))

    def contradicting_for(self, cause_id: str) -> float:
        return float(self.contradicting_causes.get(cause_id, 0.0))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "feature_name": self.feature_name,
            "value": self.value,
            "source": self.source,
            "reliability": self.reliability,
            "supporting_causes": dict(self.supporting_causes),
            "contradicting_causes": dict(self.contradicting_causes),
            "strength": self.strength,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
        }
