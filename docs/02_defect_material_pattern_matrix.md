# Day 1 deliverable — Defect × Material × Pattern matrix

This table is the backbone of cause ranking. Vision still outputs **one of six defect classes**. Pattern only **renames** the defect and slightly shifts which causes are plausible. Material (and solder powder type) **changes the weights**.

Likelihood in the CSV: `HIGH` / `MED` / `LOW` = how often that combo is a realistic production complaint. No cell is truly impossible; we never drop a class, we down-weight silly pairings.

## Six vision classes (locked)

| ID | Brief language | Dot name | Line name | Dam-and-fill name |
| --- | --- | --- | --- | --- |
| `under_dispense` | Too little | Undersized dot | Thin / broken line | Low dam or incomplete fill |
| `over_dispense` | Too much | Oversized dot | Thick line | Overflow / overbuilt dam |
| `missing` | Nothing there | Missing dot | Missing segment | Missing dam or fill |
| `inconsistent_volume` | Size not repeatable | Inconsistent dots | Inconsistent width | Inconsistent height |
| `spreading` | Beyond the area | Dot slump / bleed | Line bleed | Dam collapse |
| `air_bubble_irregular` | Bubble or odd shape | Satellite / voided dot | Voids / ragged edge | Void in fill |

## What the matrix says (the differentiator)

1. **T5/T6 + under-dispense / missing** are HIGH. Powder clogging dominates. T3 is MED (forgiving, and NSW prefers T5+ for dispensing anyway).
2. **UV glue + silicone + spreading / overflow** are HIGH. Viscosity and flow dominate; powder size does not apply.
3. **T6 + spreading** is LOW. Fine paste holds a bump. If the photo shows slump on T6, prefer pressure/time/Z-gap or wrong material ID over “paste is too wet.”
4. **Inconsistent volume is HIGH everywhere.** It is the brief’s hero example and the class where Q&A (continuous vs occasional) does the most work.
5. **Dam collapse** is a silicone/UV problem, not a Type 6 powder problem.
6. **Do not ask a line operator about a “missing dot.”** Same class, different words.

Full grid: `research/defect_material_pattern_matrix.csv`.

## Downstream terms we attach as warnings (not extra vision classes)

| If we see | Warn about |
| --- | --- |
| Over-dispense or spreading on fine-pitch dots/lines | **Bridging** after reflow / cure |
| Inconsistent or under dots on two-pad chips | **Tombstoning** after reflow |
| Air-bubble / incomplete fill | **Voiding** in the joint or encapsulant |
| Irregular extra blobs | **Satellites** from stringing (dispensing), not stencil smear |
