"""Shared label vocab for generator, trainer, and predictor."""

DEFECT_CLASSES = [
    "under_dispense",
    "over_dispense",
    "missing",
    "inconsistent_volume",
    "spreading",
    "air_bubble_irregular",
]

MATERIALS = ["solder_paste", "silver_epoxy", "uv_glue", "silicone_gel"]
PATTERNS = ["dot", "line", "dam_fill"]
BACKGROUNDS = ["pcb", "ceramic", "metal"]

PATTERN_NAMES = {
    "under_dispense": {
        "dot": "undersized_dot",
        "line": "thin_or_broken_line",
        "dam_fill": "low_dam_or_incomplete_fill",
    },
    "over_dispense": {
        "dot": "oversized_dot",
        "line": "thick_line",
        "dam_fill": "overflow_fill",
    },
    "missing": {
        "dot": "missing_dot",
        "line": "missing_segment",
        "dam_fill": "missing_dam_or_fill",
    },
    "inconsistent_volume": {
        "dot": "inconsistent_dots",
        "line": "inconsistent_width",
        "dam_fill": "inconsistent_height",
    },
    "spreading": {
        "dot": "dot_slump_bleed",
        "line": "line_bleed",
        "dam_fill": "dam_collapse",
    },
    "air_bubble_irregular": {
        "dot": "satellite_or_voided_dot",
        "line": "voids_or_ragged_edge",
        "dam_fill": "void_in_fill",
    },
}
