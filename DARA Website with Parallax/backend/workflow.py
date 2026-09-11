"""
Post-inspection workflow for YOLO micro-dispensing defects.

STEP 2 — Interactive Q&A (2 dynamic follow-ups)
STEP 4 — Cause likelihood scoring (5 industrial causes)
STEP 5 — Prioritized troubleshooting action plan

Deterministic / rule-based — no LLM round-trip required for speed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# YOLO class → internal defect key
YOLO_TO_DEFECT = {
    "too_little": "too_little",
    "too_much": "too_much",
    "inconsistent_size": "inconsistent_size",
    "missing_dot": "missing_dot",
    "spreading": "spreading",
    "air_bubble": "air_bubble",
    "no_defect_detected": "no_defect_detected",
    # aliases from older classifiers
    "under_dispense": "too_little",
    "over_dispense": "too_much",
    "inconsistent_volume": "inconsistent_size",
    "missing": "missing_dot",
    "air_bubble_irregular": "air_bubble",
    "excess_volume": "too_much",
    "insufficient_volume": "too_little",
    "insufficient_paste": "too_little",
    "missing_deposit": "missing_dot",
}

DISPLAY_DEFECT = {
    "too_little": "UNDER DISPENSE",
    "too_much": "OVER DISPENSE",
    "inconsistent_size": "INCONSISTENT DISPENSING VOLUME",
    "missing_dot": "MISSING DOT",
    "spreading": "SPREADING",
    "air_bubble": "AIR BUBBLE / IRREGULAR",
    "no_defect_detected": "NO DEFECT DETECTED",
}

# Five shop-floor causes requested for the ranking table
CAUSES = {
    "air_bubble": {
        "name": "Air Bubble",
        "check": "Inspect syringe for trapped air / piston tunneling; purge until a solid bead appears. Store tip-down and avoid overfilling (>2/3).",
    },
    "nozzle_blockage": {
        "name": "Nozzle Blockage",
        "check": "Inspect tip under magnification; purge or replace nozzle. NSW: clean with IPA ultrasonic; confirm ID ≥ 5× largest powder particle.",
    },
    "viscosity_change": {
        "name": "Material Viscosity Change",
        "check": "Check booth temp/humidity, paste age, fridge-to-floor warmup, and whether warm paste has thinned or cold paste thickened.",
    },
    "incorrect_parameter": {
        "name": "Incorrect Parameter",
        "check": "Compare pressure, on-time, Z-gap, and retract against the last known-good recipe. High pressure separates flux/metal (NSW clog guide).",
    },
    "equipment_wear": {
        "name": "Equipment Wear",
        "check": "Check valve/pump seals, regulator drift, and shot-weight consistency on a scale after cheaper checks are cleared.",
    },
}

# Baseline weights (sum ~100) per YOLO defect — grounded in NSW / AIM / NPL guidance
BASELINES: dict[str, dict[str, float]] = {
    "too_little": {
        "nozzle_blockage": 32,
        "incorrect_parameter": 22,
        "air_bubble": 18,
        "viscosity_change": 16,
        "equipment_wear": 12,
    },
    "too_much": {
        "incorrect_parameter": 34,
        "viscosity_change": 26,
        "equipment_wear": 16,
        "air_bubble": 14,
        "nozzle_blockage": 10,
    },
    "inconsistent_size": {
        "air_bubble": 30,
        "nozzle_blockage": 24,
        "incorrect_parameter": 18,
        "viscosity_change": 16,
        "equipment_wear": 12,
    },
    "missing_dot": {
        "nozzle_blockage": 36,
        "air_bubble": 22,
        "incorrect_parameter": 20,
        "viscosity_change": 12,
        "equipment_wear": 10,
    },
    "spreading": {
        "viscosity_change": 34,
        "incorrect_parameter": 28,
        "air_bubble": 12,
        "equipment_wear": 14,
        "nozzle_blockage": 12,
    },
    "air_bubble": {
        "air_bubble": 40,
        "incorrect_parameter": 20,
        "nozzle_blockage": 14,
        "viscosity_change": 14,
        "equipment_wear": 12,
    },
    "no_defect_detected": {
        "equipment_wear": 20,
        "incorrect_parameter": 20,
        "viscosity_change": 20,
        "air_bubble": 20,
        "nozzle_blockage": 20,
    },
}

REASONING_TEMPLATES = {
    "air_bubble": {
        "too_little": "Trapped air compresses then expands → intermittent under-volume shots.",
        "too_much": "Air pocket near tip can surge paste volume just before a void.",
        "inconsistent_size": "Classic signature of syringe air / piston tunneling (variable shot size).",
        "missing_dot": "Air void at tip leaves a skip where paste should deposit.",
        "spreading": "Unstable flow from air can wet pads unevenly after contact.",
        "air_bubble": "Vision class matches trapped-air / satellite morphology.",
        "no_defect_detected": "Low priority unless operators report occasional skips.",
    },
    "nozzle_blockage": {
        "too_little": "Partial clog restricts orifice — NSW #1 cause of under-dispense.",
        "too_much": "Less likely; clog usually reduces volume unless pressure was raised to compensate.",
        "inconsistent_size": "Intermittent particle jam produces size scatter across dots.",
        "missing_dot": "Full or near-full tip blockage → missing deposits.",
        "spreading": "Unlikely primary; clog rarely causes pad bleed.",
        "air_bubble": "Dried residue can also create irregular break-off.",
        "no_defect_detected": "Routine tip inspection still recommended on changeover.",
    },
    "viscosity_change": {
        "too_little": "Cold / aged paste thickens and under-flows through fine tips.",
        "too_much": "Warm booth thins paste → over-volume and slump risk.",
        "inconsistent_size": "Viscosity drift across a shift creates progressive size change.",
        "missing_dot": "Severely thickened paste may fail to wet the pad.",
        "spreading": "Low viscosity / warm paste is the lead cause of bleed and slump.",
        "air_bubble": "Over-mixing or warm paste can also introduce micro-bubbles.",
        "no_defect_detected": "Monitor booth temp/RH against the process window.",
    },
    "incorrect_parameter": {
        "too_little": "Low pressure/time or high Z-gap prevents wetting (NSW gap guidance).",
        "too_much": "High pressure/time or low Z-gap floods the pad.",
        "inconsistent_size": "Unstable regulator / on-time jitter shows as volume scatter.",
        "missing_dot": "Z too high or on-time too short → no deposit.",
        "spreading": "Excess dwell / pressure drives bleed beyond the pad.",
        "air_bubble": "Excess suck-back pulls air into the fluid path (Dymax guidance).",
        "no_defect_detected": "Recipe audit vs last known-good is still good practice.",
    },
    "equipment_wear": {
        "too_little": "Worn seals/pump starve the tip — check after cheaper causes.",
        "too_much": "Leaking valve or drifting regulator can overshoot volume.",
        "inconsistent_size": "Wear often shows as slow drift in shot weight over hours.",
        "missing_dot": "Intermittent valve failure can drop entire shots.",
        "spreading": "Secondary; verify after viscosity and parameters.",
        "air_bubble": "Leaking fittings can pull air into the path.",
        "no_defect_detected": "Schedule preventive shot-weight verification.",
    },
}


@dataclass
class FollowUpQuestion:
    id: str
    prompt: str
    options: list[dict[str, str]]


@dataclass
class CauseRow:
    cause_id: str
    name: str
    likelihood_pct: float
    reasoning: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "name": self.name,
            "likelihood_pct": round(self.likelihood_pct, 1),
            "reasoning": self.reasoning,
        }


@dataclass
class ActionStep:
    step: int
    title: str
    detail: str
    status: str  # In progress | Pending | Done
    related_cause: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "title": self.title,
            "detail": self.detail,
            "status": self.status,
            "related_cause": self.related_cause,
        }


@dataclass
class WorkflowResult:
    defect_class: str
    defect_label: str
    confidence: float
    answers: dict[str, str]
    causes: list[CauseRow] = field(default_factory=list)
    action_plan: list[ActionStep] = field(default_factory=list)
    markdown_table: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "defect_class": self.defect_class,
            "defect_label": self.defect_label,
            "confidence": self.confidence,
            "answers": self.answers,
            "causes": [c.as_dict() for c in self.causes],
            "action_plan": [a.as_dict() for a in self.action_plan],
            "markdown_table": self.markdown_table,
        }


class PostInspectionWorkflow:
    """
    3-step post-YOLO workflow for VS Code / FastAPI integration.

    Typical API usage:
        wf = PostInspectionWorkflow(defect_class="inconsistent_size", confidence=0.91)
        questions = wf.get_followup_questions()
        result = wf.run({"frequency": "continuous", "recent_change": "nozzle"})
    """

    def __init__(
        self,
        defect_class: str,
        confidence: float = 0.8,
        detection_count: int = 0,
    ) -> None:
        raw = (defect_class or "no_defect_detected").strip().lower()
        self.defect_class = YOLO_TO_DEFECT.get(raw, raw if raw in BASELINES else "inconsistent_size")
        self.defect_label = DISPLAY_DEFECT.get(self.defect_class, self.defect_class.upper())
        self.confidence = float(max(0.0, min(1.0, confidence)))
        self.detection_count = int(detection_count)

    # ── STEP 2: Interactive Q&A ────────────────────────────────────────────────
    def get_followup_questions(self) -> list[dict[str, Any]]:
        """Return 2 dynamic follow-ups tailored to the vision defect."""
        q_frequency = FollowUpQuestion(
            id="frequency",
            prompt=self._frequency_prompt(),
            options=[
                {"value": "continuous", "label": "Continuous (every board / most deposits)"},
                {"value": "occasional", "label": "Occasional (intermittent / random)"},
                {"value": "from_start", "label": "From the start of this job"},
                {"value": "after_hours", "label": "Started after running for a while"},
            ],
        )
        q_change = FollowUpQuestion(
            id="recent_change",
            prompt=self._change_prompt(),
            options=[
                {"value": "nozzle", "label": "Nozzle / tip was changed"},
                {"value": "syringe", "label": "Syringe / material was changed"},
                {"value": "parameters", "label": "Pressure / time / Z was adjusted"},
                {"value": "none", "label": "No recent change"},
            ],
        )
        return [
            {
                "id": q.id,
                "prompt": q.prompt,
                "options": q.options,
            }
            for q in (q_frequency, q_change)
        ]

    def _frequency_prompt(self) -> str:
        if self.defect_class in {"inconsistent_size", "air_bubble", "missing_dot"}:
            return (
                f"Vision flagged {self.defect_label} ({self.confidence:.0%}). "
                "Does this defect appear continuously or only occasionally?"
            )
        if self.defect_class == "spreading":
            return (
                f"Vision flagged {self.defect_label} ({self.confidence:.0%}). "
                "Is the spreading continuous across pads, or only on some deposits?"
            )
        return (
            f"Vision flagged {self.defect_label} ({self.confidence:.0%}). "
            "How often does this defect occur on the line?"
        )

    def _change_prompt(self) -> str:
        if self.defect_class in {"too_little", "missing_dot", "inconsistent_size"}:
            return "Was a syringe or nozzle recently changed before this issue appeared?"
        if self.defect_class in {"too_much", "spreading"}:
            return "Were dispense parameters (pressure/time/Z) or material recently changed?"
        return "Was anything recently changed on the dispenser (syringe, nozzle, or parameters)?"

    def ask_console(self) -> dict[str, str]:
        """Interactive console capture for VS Code / CLI demos."""
        answers: dict[str, str] = {}
        print("\n=== STEP 2: Interactive Q&A ===")
        print(f"Defect: {self.defect_label} | Confidence: {self.confidence:.0%}\n")
        for q in self.get_followup_questions():
            print(q["prompt"])
            for i, opt in enumerate(q["options"], start=1):
                print(f"  [{i}] {opt['label']}")
            while True:
                raw = input("Select option number: ").strip()
                if raw.isdigit() and 1 <= int(raw) <= len(q["options"]):
                    answers[q["id"]] = q["options"][int(raw) - 1]["value"]
                    break
                print("Invalid selection — try again.")
            print()
        return answers

    # ── STEP 4: Cause scoring ──────────────────────────────────────────────────
    def score_causes(self, answers: dict[str, str]) -> list[CauseRow]:
        weights = dict(BASELINES.get(self.defect_class, BASELINES["inconsistent_size"]))
        freq = (answers.get("frequency") or "").lower()
        change = (answers.get("recent_change") or "").lower()

        # Frequency multipliers
        if freq == "continuous":
            self._mul(weights, "nozzle_blockage", 1.35)
            self._mul(weights, "incorrect_parameter", 1.25)
            self._mul(weights, "viscosity_change", 1.15)
            self._mul(weights, "air_bubble", 0.75)
        elif freq == "occasional":
            self._mul(weights, "air_bubble", 1.45)
            self._mul(weights, "equipment_wear", 1.15)
            self._mul(weights, "nozzle_blockage", 0.85)
        elif freq == "from_start":
            self._mul(weights, "incorrect_parameter", 1.4)
            self._mul(weights, "viscosity_change", 1.2)
            self._mul(weights, "nozzle_blockage", 1.1)
        elif freq == "after_hours":
            self._mul(weights, "nozzle_blockage", 1.4)
            self._mul(weights, "viscosity_change", 1.25)
            self._mul(weights, "equipment_wear", 1.2)
            self._mul(weights, "air_bubble", 1.1)

        # Recent-change multipliers
        if change == "nozzle":
            self._mul(weights, "nozzle_blockage", 1.55)
            self._mul(weights, "incorrect_parameter", 1.15)  # wrong tip size / Z after change
        elif change == "syringe":
            self._mul(weights, "air_bubble", 1.5)
            self._mul(weights, "viscosity_change", 1.25)
        elif change == "parameters":
            self._mul(weights, "incorrect_parameter", 1.6)
            self._mul(weights, "viscosity_change", 0.9)
        elif change == "none":
            self._mul(weights, "equipment_wear", 1.2)
            self._mul(weights, "viscosity_change", 1.1)

        # Vision confidence: low confidence softens extremes slightly
        if self.confidence < 0.45:
            for k in weights:
                weights[k] = 0.7 * weights[k] + 0.3 * 20.0

        # Many detections of inconsistent_size → stronger air/clog signal
        if self.detection_count >= 5 and self.defect_class == "inconsistent_size":
            self._mul(weights, "air_bubble", 1.15)
            self._mul(weights, "nozzle_blockage", 1.1)

        total = sum(max(v, 0.0) for v in weights.values()) or 1.0
        rows: list[CauseRow] = []
        for cause_id, w in weights.items():
            pct = 100.0 * max(w, 0.0) / total
            meta = CAUSES[cause_id]
            reason = REASONING_TEMPLATES[cause_id].get(
                self.defect_class,
                "Ranked from vision class + operator answers.",
            )
            # Append answer-specific note
            note = self._answer_note(cause_id, freq, change)
            if note:
                reason = f"{reason} {note}"
            rows.append(
                CauseRow(
                    cause_id=cause_id,
                    name=meta["name"],
                    likelihood_pct=pct,
                    reasoning=reason,
                )
            )
        rows.sort(key=lambda r: r.likelihood_pct, reverse=True)
        return rows

    @staticmethod
    def _mul(weights: dict[str, float], key: str, factor: float) -> None:
        if key in weights:
            weights[key] *= factor

    @staticmethod
    def _answer_note(cause_id: str, freq: str, change: str) -> str:
        bits: list[str] = []
        if cause_id == "air_bubble" and freq == "occasional":
            bits.append("Occasional pattern strongly supports trapped air.")
        if cause_id == "nozzle_blockage" and freq in {"continuous", "after_hours"}:
            bits.append("Continuous / late-onset pattern supports progressive clog.")
        if cause_id == "nozzle_blockage" and change == "nozzle":
            bits.append("Recent tip change raises install/size mismatch risk.")
        if cause_id == "air_bubble" and change == "syringe":
            bits.append("Fresh syringe changes often introduce air if not purged.")
        if cause_id == "incorrect_parameter" and change == "parameters":
            bits.append("Operator confirmed a recent parameter edit.")
        if cause_id == "equipment_wear" and change == "none" and freq == "after_hours":
            bits.append("No change + late onset → wear / drift candidate.")
        return " ".join(bits)

    def format_markdown_table(self, causes: list[CauseRow]) -> str:
        lines = [
            "| Possible Cause | AI Likelihood Score | Reasoning |",
            "|---|---|---|",
        ]
        for row in causes:
            reason = row.reasoning.replace("|", "/")
            lines.append(f"| {row.name} | {row.likelihood_pct:.1f}% | {reason} |")
        return "\n".join(lines)

    def format_ascii_table(self, causes: list[CauseRow]) -> str:
        headers = ("Possible Cause", "AI Likelihood Score", "Reasoning")
        col0 = max(len(headers[0]), max(len(c.name) for c in causes))
        col1 = max(len(headers[1]), 8)
        # Truncate reasoning for console width
        rows = []
        for c in causes:
            reason = c.reasoning if len(c.reasoning) <= 72 else c.reasoning[:69] + "..."
            rows.append((c.name, f"{c.likelihood_pct:.1f}%", reason))
        col2 = max(len(headers[2]), max(len(r[2]) for r in rows))

        def fmt(a: str, b: str, c: str) -> str:
            return f"| {a:<{col0}} | {b:^{col1}} | {c:<{col2}} |"

        sep = f"|{'-'*(col0+2)}|{'-'*(col1+2)}|{'-'*(col2+2)}|"
        out = [fmt(*headers), sep]
        out.extend(fmt(*r) for r in rows)
        return "\n".join(out)

    # ── STEP 5: Action plan ────────────────────────────────────────────────────
    def build_action_plan(self, causes: list[CauseRow]) -> list[ActionStep]:
        """5-step checklist ordered by highest likelihood (cheapest checks first within top causes)."""
        # Prefer top causes but keep industrial cost order: air → nozzle → params → viscosity → wear
        cost_order = {
            "air_bubble": 1,
            "nozzle_blockage": 2,
            "incorrect_parameter": 3,
            "viscosity_change": 4,
            "equipment_wear": 5,
        }
        ranked = sorted(
            causes,
            key=lambda c: (-c.likelihood_pct, cost_order.get(c.cause_id, 9)),
        )

        steps: list[ActionStep] = []
        # Always start with verify vision finding
        steps.append(
            ActionStep(
                step=1,
                title="Confirm vision finding on the board",
                detail=(
                    f"Re-inspect the flagged deposit ({self.defect_label}, "
                    f"{self.confidence:.0%} conf). Mark NCR location before adjusting hardware."
                ),
                status="In progress",
                related_cause="vision",
            )
        )

        for cause in ranked[:4]:
            meta = CAUSES[cause.cause_id]
            steps.append(
                ActionStep(
                    step=len(steps) + 1,
                    title=f"Check: {meta['name']} ({cause.likelihood_pct:.0f}%)",
                    detail=meta["check"],
                    status="Pending",
                    related_cause=cause.cause_id,
                )
            )

        # Pad to 5 with a verify/close step
        while len(steps) < 5:
            steps.append(
                ActionStep(
                    step=len(steps) + 1,
                    title="Verify corrective action with a short dispense trial",
                    detail="Run 10–20 test deposits, re-scan with YOLO, and confirm quality score recovery before releasing the line.",
                    status="Pending",
                    related_cause="verification",
                )
            )
        return steps[:5]

    # ── Orchestrator ───────────────────────────────────────────────────────────
    def run(self, answers: dict[str, str]) -> WorkflowResult:
        causes = self.score_causes(answers)
        plan = self.build_action_plan(causes)
        table = self.format_markdown_table(causes)
        return WorkflowResult(
            defect_class=self.defect_class,
            defect_label=self.defect_label,
            confidence=self.confidence,
            answers=answers,
            causes=causes,
            action_plan=plan,
            markdown_table=table,
        )

    def run_console(self) -> WorkflowResult:
        answers = self.ask_console()
        result = self.run(answers)
        print("=== STEP 4: Cause Analysis ===")
        print(self.format_ascii_table(result.causes))
        print("\n=== STEP 5: Troubleshooting Action Plan ===")
        for step in result.action_plan:
            marker = {
                "In progress": "[>>]",
                "Pending": "[  ]",
                "Done": "[OK]",
            }.get(step.status, "[  ]")
            print(f"{marker} Step {step.step}: {step.title}")
            print(f"         {step.detail}")
            print(f"         Status: {step.status}\n")
        return result

    # ── Fast free-text answers (no Gemini) ─────────────────────────────────────
    def answer_fast(self, question: str, causes: list[CauseRow] | None = None) -> str:
        """Instant rule-based reply for UI chat — avoids LLM latency."""
        q = (question or "").strip().lower()
        causes = causes or self.score_causes({})
        top = causes[0] if causes else None

        if any(k in q for k in ("top cause", "most likely", "root cause", "what cause")):
            if not top:
                return f"No ranked causes yet for {self.defect_label}."
            return (
                f"Most likely cause for {self.defect_label}: {top.name} "
                f"({top.likelihood_pct:.0f}%). {top.reasoning}"
            )

        if any(k in q for k in ("what should i", "next", "fix", "action", "troubleshoot", "check first")):
            plan = self.build_action_plan(causes)
            lines = [f"Prioritized plan for {self.defect_label}:"]
            for s in plan:
                lines.append(f"{s.step}. [{s.status}] {s.title} — {s.detail}")
            return "\n".join(lines)

        if "nozzle" in q or "clog" in q:
            row = next((c for c in causes if c.cause_id == "nozzle_blockage"), None)
            pct = f"{row.likelihood_pct:.0f}%" if row else "n/a"
            return (
                f"Nozzle blockage likelihood is {pct}. NSW guidance: keep nozzle ID ≥ 5× largest "
                "powder particle, avoid excessive pressure (separates flux/metal), and clean tips with IPA ultrasonic."
            )

        if "air" in q or "bubble" in q:
            row = next((c for c in causes if c.cause_id == "air_bubble"), None)
            pct = f"{row.likelihood_pct:.0f}%" if row else "n/a"
            return (
                f"Air-bubble likelihood is {pct}. Purge until a solid bead appears, store syringes tip-down, "
                "avoid >2/3 fill, and reduce excess suck-back that pulls air into the path."
            )

        if "viscos" in q or "temp" in q or "humid" in q or "warm" in q:
            return (
                "Viscosity shifts with booth temperature/humidity and paste warmup. "
                "Warm paste thins (spread/over-dispense); cold/aged paste thickens (under-dispense/clog)."
            )

        if "score" in q or "quality" in q or "likelihood" in q:
            bits = ", ".join(f"{c.name} {c.likelihood_pct:.0f}%" for c in causes[:3])
            return f"Top likelihoods for {self.defect_label}: {bits}."

        if top:
            return (
                f"For {self.defect_label} ({self.confidence:.0%}), start with {top.name} "
                f"({top.likelihood_pct:.0f}%). Ask about 'top cause', 'nozzle', 'air bubble', or 'action plan' for specifics."
            )
        return f"Analysis context: {self.defect_label}. Ask about causes or the action plan."


if __name__ == "__main__":
    # Quick VS Code demo
    demo = PostInspectionWorkflow(defect_class="inconsistent_size", confidence=0.91, detection_count=7)
    demo.run_console()
