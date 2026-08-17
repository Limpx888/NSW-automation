# Day 1 — Domain research notes

Sources used (primary, citable):

- NSW Automation application page: https://nswautomation.com/NSW/micro-dispensing-application-solutions/
- NSW clog-prevention guide: https://nswautomation.com/NSW/prevent-solder-paste-dispensing-clog/
- AIM Solder, *Solder Paste Powder: When to Downsize*: https://www.aimsolder.com/white-paper/solder-paste-powder-when-to-downsize/
- IPC J-STD-005A particle-size table (quoted by AIM)
- Indium / Nordson EFD needle-gauge vs powder-type guidance
- NPL *Dispensing Code of Practice* (stringing / satellites)
- Dymax / ASSEMBLY magazine (UV adhesive dispensing defects)

## What NSW actually dispenses

NSW systems are **micro-dispensers**, not stencil printers. They apply:

| Material | NSW claim | Defect physics |
| --- | --- | --- |
| Solder paste (all types; T6 highlighted) | Down to **80 µm** dots/lines with Type 6 | Metal powder in flux. Particle size, oxidation, flux separation, nozzle ID. |
| UV glue / adhesive | Down to **40 µm** | Light-cure, viscosity-driven. Premature cure in clear barrels/tips. |
| Silver epoxy | Conductive die-attach / interconnect | Filled adhesive. Filler settling + same 5× particle vs tip rule. |
| Silicone gel | Encapsulation, dam-and-fill, sealing | Soft, flowable. Spreading, stringing, trapped air. |
| Also in catalog (out of 20-day scope) | Phosphor, liquid metal, TiO₂, underfill, general adhesives | Mention in slides; do not build deep rule sets yet. |

Pattern types NSW shows: micro-bump/dot, micro-line, micro-DAM, dam-and-fill, cavity filling, underfill.

**20-day scope lock:** materials = solder paste T3–T6 (deep) + silver epoxy, UV glue, silicone gel (lighter). Patterns = **dot / line / dam-and-fill**.

## Solder powder types (IPC J-STD-005A, via AIM)

Only **80%** of particles must sit in the nominal band. That variation matters for clog risk.

| Type | ≥80% between | Typical use | Defect tendency |
| --- | --- | --- | --- |
| Type 3 | 25–45 µm | 0603/0805 and larger | Forgiving, low clog |
| Type 4 | 20–38 µm | 0201, 0.5 mm BGA — SMT standard | Balanced |
| Type 5 | 15–25 µm | 01005, ultra-fine pitch | Higher clog + oxidation |
| Type 6 | 5–15 µm | microLED, chip-scale, SiP | Highest clog + oxidation |

Surface-area-to-volume for a sphere is `3/r`. Mid-band Type 4 (~29 µm) vs Type 6 (~10 µm) is about **3×** more surface per volume. AIM: finer powder oxidizes faster, shortens shelf life, and often needs nitrogen reflow at Type 6.

## The 5× rule — use NSW’s dispensing version, not the stencil version

AIM’s **5-ball rule** is for **stencil apertures**: smallest opening ≥ 5× largest powder diameter.

| Type | 5-ball stencil floor (AIM) |
| --- | --- |
| T3 | 225 µm |
| T4 | 190 µm |
| T5 | 125 µm |
| T6 | 75 µm |

NSW publishes the **same 5× idea for nozzle inner diameter** ([clog guide](https://nswautomation.com/NSW/prevent-solder-paste-dispensing-clog/)):

> “Make sure to use nozzle ID that is at least 5x the solder particle size.”

| Type | NSW particle range | Recommended nozzle ID | Typical dispensed size |
| --- | --- | --- | --- |
| Type 5 | 10–25 µm | ≥ 125 µm | 150–200 µm |
| Type 6 | 5–15 µm | ≥ 80 µm | 80–150 µm |
| Type 7 | 2–11 µm | ≥ 50 µm | < 80 µm |

NSW also says: use **Type 5 and finer** for general dispensing (T3/T4 are more print-oriented). Nordson/Indium often use **7× powder size** as a conservative needle rule. Our engine cites **NSW 5×** as the primary rule and notes 7× as the conservative industry check.

**Product line for judges:** not “check for clogging,” but “clogging risk is elevated because Type 6 paste is being pushed through a fine-pitch nozzle; Type 6 powder has ~3× the surface-area-to-volume of Type 4, so it oxidizes and agglomerates faster; NSW recommends nozzle ID ≥ 80 µm for T6 (5× the largest particle).”

## Five industry terms (dispensing-first, printing-second)

These are **not** our six vision classes. They are **cause / downstream** language the chatbot should use correctly.

### Clogging
Paste or cured adhesive blocks the nozzle/valve. NSW causes: non-dispensing-grade paste, wrong storage, flux/solder separation (syringe not tip-down), expired material, nozzle ID < 5× particle, **high** pressure (separates flux from metal), **Z-gap too low** (solder balls trapped in the tip), dirty nozzles. Result in our taxonomy: **under-dispense**, **missing**, **inconsistent volume**.

### Satelliting
Tiny extra deposits near the main one. In **dispensing** (NPL): a string of paste stretches as the needle lifts, then snaps and drops a satellite. Fix: higher retract / better break-off, not a “stencil wipe.” In **printing**: smear under a failed gasket. Our vision class: **air bubble / irregular shape** (extra blobs) or **spreading**. Do not tell a dispenser operator to clean a stencil.

### Tombstoning
A **reflow** defect: a chip-capacitor stands on one end because wetting forces are unequal. Dispensing causes it **indirectly** via uneven paste volume on the two pads (**inconsistent volume** / **under-dispense** on one pad). Our system can warn “this under-dispense pattern raises tombstone risk after reflow” — it should not classify a photo as tombstoning unless a standing component is visible (out of scope).

### Bridging
Unintended conductive path between pads. Dispensing causes: **over-dispense**, **spreading/slump**, satellites that coalesce. Fine-pitch T5/T6 + line/dot patterns are the high-risk cells.

### Voiding
Cavities inside a joint or fill. Dispensing-related: air in the syringe, tunneling, vacuum suck-back pulling bubbles, incomplete dam-and-fill (trapped air), silicone outgassing. Our vision class: **air bubble / irregular shape**. True internal voids after reflow may be invisible in a top-down photo — say that honestly.

## Material-specific physics (secondary materials)

**Silver epoxy:** silver-flake filled. Settling in the syringe, filler agglomeration, same 5× tip-vs-particle rule, piston mismatch. Looks metallic; defects often look like solder paste but causes are filler + mix, not powder type T3–T6.

**UV glue:** unfilled, viscosity-driven. Premature cure if barrels/tips are not UV-blocking. Excess pressure or suck-back → bubbles. Low viscosity → spreading. Clogs from **gelled adhesive in the tip**, not metal powder.

**Silicone gel:** semi-transparent, soft edge, stringing, dam collapse, trapped air in dam-and-fill. Temperature strongly changes flow.

## Design decisions locked on Day 1

1. **Material type** and **pattern type** are required discovery inputs (plus the original 5 questions).
2. Solder paste follow-up: **powder type T3–T6** (and optional nozzle ID). UV follow-up: **cure / lamp / barrel opacity**. Silicone: **temperature / dam height**. Silver epoxy: **mix / filler settling**.
3. Vision model predicts **6 defect classes**. Material + pattern are metadata (user input, optional second head later).
4. Ranking is **deterministic rules**. LLM only explains why those weights moved.
5. Cite NSW 5× nozzle rule and AIM powder table in every solder-paste clog explanation.
