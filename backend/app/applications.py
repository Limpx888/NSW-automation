"""NSW Automation application / pasting catalog for the worker-facing UI.

Aligned with https://nswautomation.com/NSW/ Application & Solutions:
Solder Paste Dispensing, Liquid Metal Dispensing, Adaptive Micro-Dam,
plus materials from What Can We Dispense.
"""

from __future__ import annotations

from typing import Any

# Worker picks an application first; that locks material (and often pattern).
APPLICATIONS: list[dict[str, Any]] = [
    {
        "id": "solder_paste_dispensing",
        "title": "Solder Paste Dispensing",
        "tagline": "Micro-bump, fine line, T3–T6 paste",
        "description": (
            "NSW micro-soldering for BGA dots, fine streaks, and 008004/01005 work. "
            "Supports Type 3–6 paste; T6 dots/lines down to ~80 µm with SynchroPULSE-MICRO."
        ),
        "material": "solder_paste",
        "default_pattern": "dot",
        "patterns": ["dot", "line", "dam_fill"],
        "accent": "#e85d04",
        "source": "https://nswautomation.com/NSW/micro-dispensing-application-solutions/",
        "hints": [
            "Nozzle ID ≥ 5× largest powder particle (T6 floor: 80 µm)",
            "Store syringe tip-down; keep pressure low to avoid flux–metal separation",
        ],
    },
    {
        "id": "liquid_metal_dispensing",
        "title": "Liquid Metal Dispensing",
        "tagline": "Gallium TIM, cavity fill, high surface tension",
        "description": (
            "Liquid-metal TIM / cavity fill (Ga, In, Sn alloys). High surface tension needs "
            "corrosive-protected jetting or contact dispense — not generic paste recipes."
        ),
        "material": "liquid_metal",
        "default_pattern": "dot",
        "patterns": ["dot", "line", "dam_fill"],
        "accent": "#4cc9f0",
        "source": "https://nswautomation.com/NSW/liquid-metal-dispensing/",
        "hints": [
            "Expect wetting / surface-tension failures more than powder clog",
            "Use dam walls when containing metal in cavities",
        ],
    },
    {
        "id": "adaptive_micro_dam",
        "title": "Adaptive Micro-Dam",
        "tagline": "Dam-and-fill barriers & high-standoff walls",
        "description": (
            "Micro-DAM / dam-and-fill for phosphor, underfill containment, and liquid-metal "
            "dams. Pattern defaults to dam_fill; pick the wall material next."
        ),
        "material": None,
        "material_choices": ["uv_glue", "silicone_gel", "silver_epoxy"],
        "default_pattern": "dam_fill",
        "patterns": ["dam_fill", "line"],
        "accent": "#2a9d8f",
        "source": "https://nswautomation.com/NSW/micro-dispensing-application-solutions/",
        "hints": [
            "Watch dam collapse, overflow fill, and void-in-fill defects",
            "Z-gap and viscosity drift dominate height consistency",
        ],
    },
    {
        "id": "uv_glue_adhesive",
        "title": "UV Glue / Adhesive",
        "tagline": "Microdots ≥40 µm, lid attach, bonding",
        "description": (
            "UV-cure adhesives for microdots (NSW cites ~40 µm) and bonding. "
            "Clear barrels cause premature cure in the fluid path."
        ),
        "material": "uv_glue",
        "default_pattern": "dot",
        "patterns": ["dot", "line", "dam_fill"],
        "accent": "#9b5de5",
        "source": "https://nswautomation.com/NSW/micro-dispensing-application-solutions/",
        "hints": ["Use UV-blocking (amber/black) syringes and tips"],
    },
    {
        "id": "silver_epoxy",
        "title": "Silver Epoxy",
        "tagline": "Conductive die-attach & sinter-like pastes",
        "description": (
            "Filled conductive adhesives / silver epoxy. Filler settling and nozzle clog "
            "are the usual under-dispense drivers."
        ),
        "material": "silver_epoxy",
        "default_pattern": "dot",
        "patterns": ["dot", "line"],
        "accent": "#adb5bd",
        "source": "https://nswautomation.com/NSW/micro-dispensing-application-solutions/",
        "hints": ["Agitate / remix if filler settles during idle"],
    },
    {
        "id": "silicone_gel_phosphor",
        "title": "Silicone Gel / Phosphor",
        "tagline": "LED encapsulation & gel fill",
        "description": (
            "Silicone gels and phosphor-loaded fills for LED encapsulation. "
            "Temperature-driven viscosity and stringing are common."
        ),
        "material": "silicone_gel",
        "default_pattern": "dam_fill",
        "patterns": ["dot", "line", "dam_fill"],
        "accent": "#f4a261",
        "source": "https://nswautomation.com/NSW/micro-dispensing-application-solutions/",
        "hints": ["Control booth temperature; gels thin when warm"],
    },
]

DIAGNOSIS_MODES = [
    {
        "id": "photo",
        "title": "Upload a photo",
        "description": "Classify the defect from a top-down dispense image, then refine with a short Q&A.",
    },
    {
        "id": "questions",
        "title": "Answer questions",
        "description": "No photo — guided interview on look, frequency, changes, and location.",
    },
    {
        "id": "both",
        "title": "Photo + questions",
        "description": "Best accuracy: vision class plus full process interview.",
    },
]


def list_applications() -> list[dict[str, Any]]:
    return APPLICATIONS


def get_application(app_id: str | None) -> dict[str, Any] | None:
    if not app_id:
        return None
    for app in APPLICATIONS:
        if app["id"] == app_id:
            return app
    return None


def resolve_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """Apply application defaults onto symptom answers before ranking."""
    out = dict(answers)
    app = get_application(out.get("application"))
    if not app:
        return out
    out["application_title"] = app["title"]
    if app.get("material") and not out.get("material"):
        out["material"] = app["material"]
    if app.get("default_pattern") and not out.get("pattern"):
        out["pattern"] = app["default_pattern"]
    return out
