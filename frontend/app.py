"""Streamlit app: Dashboard + Troubleshoot workflow."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import streamlit as st

from backend.app.db.cases import connect, recent_cases, seed_if_empty
from backend.app.pipeline import run_session
from backend.app.reasoning.discover import followups_for
from backend.app.reasoning.rank_causes import load_rules
from backend.app.reports.pdf import build_pdf
from backend.app.vision.predict import load_model

DEMO_PRESET = {
    "sample_image": "under_dispense__solder_paste__dot.png",
    "material": "solder_paste",
    "pattern": "dot",
    "amount": "too_small",
    "frequency": "continuous",
    "recent_change": "nozzle",
    "location": "multiple",
    "powder_type": "T6",
    "nozzle_id_um": 60,
}

FEATURES = [
    {
        "title": "Photo defect detection",
        "bonus": "Bonus 1",
        "desc": "Upload a top-down dispense photo. MobileNetV2 suggests one of 6 defect classes with a confidence score.",
        "icon": "📷",
    },
    {
        "title": "Smart discovery questions",
        "bonus": "Step 1",
        "desc": "Answer what material, pattern, and symptom you see. The app asks follow-ups (e.g. solder powder type T3–T6).",
        "icon": "💬",
    },
    {
        "title": "Material-aware cause ranking",
        "bonus": "Core AI",
        "desc": "Deterministic rules rank root causes with %. Type 6 paste + fine nozzle triggers NSW’s 5× particle rule — not generic advice.",
        "icon": "🎯",
    },
    {
        "title": "Why explanation",
        "bonus": "Step 4",
        "desc": "Shows which rules fired (occasional → air bubble, continuous → clog, etc.) so judges see logical reasoning.",
        "icon": "🧠",
    },
    {
        "title": "Troubleshooting checklist",
        "bonus": "Step 5",
        "desc": "Ordered action plan: cheapest checks first (syringe bubbles) before expensive ones (equipment inspection).",
        "icon": "✅",
    },
    {
        "title": "Dispensing quality score",
        "bonus": "Bonus 2",
        "desc": "Simple 0–100 quality score plus shape/size/defect-risk stars from the detected defect.",
        "icon": "⭐",
    },
    {
        "title": "Similar case lookup",
        "bonus": "Bonus 3",
        "desc": "SQLite database: “12 similar cases — 8 were caused by air in the syringe.” Learns from past sessions.",
        "icon": "📚",
    },
    {
        "title": "PDF engineer report",
        "bonus": "Bonus 4",
        "desc": "Download a troubleshooting PDF with defect, ranked causes, action plan, and engineer notes field.",
        "icon": "📄",
    },
]


def _fmt(s: str) -> str:
    return s.replace("_", " ").title()


def render_dashboard(rules: dict, model_ok: bool, case_count: int, sample_count: int) -> None:
    st.title("Dashboard")
    st.markdown(
        "Welcome to **AI Dispensing Defect Detective** — an assistant that helps factory "
        "technicians **find why a dispense went wrong** and **what to check first**. "
        "It does **not** replace engineers; it speeds up preliminary troubleshooting."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Defect classes", len(rules["defect_classes"]))
    c2.metric("Materials covered", len(rules["materials"]))
    c3.metric("Cases in database", case_count)
    c4.metric("Vision model", "Ready" if model_ok else "Heuristic fallback")

    st.divider()
    st.subheader("How the website works")
    st.markdown(
        """
Think of it as **three layers** working together:

```
  YOU                          THE APP                         OUTPUT
  ───                          ───────                         ──────
  Upload photo        ──►      Vision AI guesses defect
  Answer questions    ──►      Rule engine ranks causes   ──►   Bar chart + explanation
  Click Analyse       ──►      Database finds similar cases      Checklist + PDF report
```

**Step-by-step (Troubleshoot page):**

1. **Photo (optional)** — Show the dispense result. The camera/vision layer labels it (e.g. undersized dot).
2. **Discovery questions** — Tell the app material (solder paste vs UV glue), pattern (dot/line/dam), and what looks wrong.
3. **Follow-ups** — Solder paste asks powder type (T3–T6) and nozzle size. UV glue asks about UV-blocking barrels.
4. **Analyse** — The ranking engine combines your answers with NSW industry rules and outputs ranked causes (%).
5. **Results** — You get an explanation, bar chart, “check first” list, similar past cases, and a downloadable PDF.
        """
    )

    st.subheader("Features at a glance")
    cols = st.columns(2)
    for i, feat in enumerate(FEATURES):
        with cols[i % 2]:
            st.markdown(f"### {feat['icon']} {feat['title']}")
            st.caption(feat["bonus"])
            st.write(feat["desc"])

    st.divider()
    st.subheader("What makes this different from a chatbot?")
    st.info(
        "**Material matters.** A small dot in UV glue is a viscosity/cure problem. "
        "The same look in Type 6 solder paste is a powder/nozzle clog problem. "
        "The app uses different cause tables per material and cites NSW’s rule: "
        "**nozzle ID ≥ 5× largest powder particle.**"
    )

    st.subheader("Try the judge demo")
    st.markdown(
        "Pre-filled scenario: **Type 6 solder paste**, **60 µm nozzle** (below NSW 80 µm floor), "
        "**continuous under-dispense** after a nozzle change → expect **5× rule + clog** on top."
    )
    if st.button("Load demo on Troubleshoot page", type="primary"):
        st.session_state["demo_preset"] = DEMO_PRESET.copy()
        st.session_state["page"] = "Troubleshoot"
        st.rerun()

    with st.expander("Scope covered in this project"):
        st.markdown(
            f"- **Materials:** {', '.join(_fmt(m) for m in rules['materials'])}\n"
            f"- **Patterns:** {', '.join(_fmt(p) for p in rules['patterns'])}\n"
            f"- **Defects:** {', '.join(_fmt(d) for d in rules['defect_classes'])}\n"
            f"- **Demo images:** {sample_count} samples in `data/samples/`"
        )


def render_troubleshoot(rules: dict) -> None:
    preset = st.session_state.pop("demo_preset", None)

    st.title("Troubleshoot")
    st.caption("Upload a photo, answer questions, then click Analyse.")

    left, right = st.columns([1, 1.15])

    samples = sorted((ROOT / "data" / "samples").glob("*.png"))
    sample_names = ["(none)"] + [p.name for p in samples]
    default_sample = preset.get("sample_image", "(none)") if preset else "(none)"
    default_sample_idx = sample_names.index(default_sample) if default_sample in sample_names else 0

    with left:
        st.subheader("1. Dispense photo")
        upload = st.file_uploader("Upload a top-down photo", type=["png", "jpg", "jpeg"])
        sample_pick = None
        if samples:
            sample_pick = st.selectbox(
                "Or pick a synthetic demo image",
                sample_names,
                index=default_sample_idx,
            )
        image = None
        if upload:
            data = np.frombuffer(upload.getvalue(), dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption="Uploaded frame", width="stretch")
        elif sample_pick and sample_pick != "(none)":
            path = ROOT / "data" / "samples" / sample_pick
            image = cv2.imread(str(path))
            if image is not None:
                st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption=sample_pick, width="stretch")

        st.subheader("2. Discovery questions")
        mat_idx = rules["materials"].index(preset["material"]) if preset and preset.get("material") in rules["materials"] else 0
        pat_idx = rules["patterns"].index(preset["pattern"]) if preset and preset.get("pattern") in rules["patterns"] else 0
        amount_opts = ["too_small", "too_large", "missing", "inconsistent", "spreading", "irregular"]
        amt_idx = amount_opts.index(preset["amount"]) if preset and preset.get("amount") in amount_opts else 0

        material = st.selectbox(
            "Material", rules["materials"], index=mat_idx, format_func=lambda x: x.replace("_", " ")
        )
        pattern = st.selectbox(
            "Pattern", rules["patterns"], index=pat_idx, format_func=lambda x: x.replace("_", " ")
        )
        amount = st.selectbox(
            "What does the dispense look like?",
            amount_opts,
            index=amt_idx,
            format_func=lambda x: {
                "too_small": "Too small / under-dispense",
                "too_large": "Too large / over-dispense",
                "missing": "Missing",
                "inconsistent": "Inconsistent volume",
                "spreading": "Spreading beyond the area",
                "irregular": "Air bubble / irregular shape",
            }[x],
        )
        freq_default = preset.get("frequency", "occasional") if preset else "occasional"
        frequency = st.radio(
            "Frequency",
            ["occasional", "continuous"],
            index=0 if freq_default == "occasional" else 1,
            horizontal=True,
        )
        change_opts = ["none", "material", "nozzle", "settings"]
        ch_idx = change_opts.index(preset["recent_change"]) if preset and preset.get("recent_change") in change_opts else 0
        recent_change = st.selectbox("Recent change", change_opts, index=ch_idx)
        loc_default = preset.get("location", "single") if preset else "single"
        location = st.radio(
            "Where?",
            ["single", "multiple"],
            index=0 if loc_default == "single" else 1,
            horizontal=True,
            format_func=lambda x: "One location" if x == "single" else "Multiple locations",
        )

        extras: dict = {}
        for q in followups_for(material):
            if q["id"] == "nozzle_id_um":
                default_nozzle = int(preset.get("nozzle_id_um", 0)) if preset else 0
                extras["nozzle_id_um"] = st.number_input(
                    "Nozzle inner diameter (um) — optional NSW 5x check",
                    min_value=0,
                    max_value=400,
                    value=default_nozzle,
                )
                if extras["nozzle_id_um"] == 0:
                    extras.pop("nozzle_id_um")
            elif q["options"] == "number_or_skip":
                continue
            else:
                opts = q["options"]
                idx = opts.index(preset[q["id"]]) if preset and preset.get(q["id"]) in opts else 0
                extras[q["id"]] = st.selectbox(q["prompt"], opts, index=idx)

        run = st.button("Analyse", type="primary", use_container_width=True)

    with right:
        st.subheader("3. Live analysis")
        if not run:
            st.info(
                "Fill in the form on the left and click **Analyse**. "
                "Tip: use **Dashboard → Load demo** for a pre-filled judge scenario."
            )
        else:
            answers = {
                "material": material,
                "pattern": pattern,
                "amount": amount,
                "frequency": frequency,
                "recent_change": recent_change,
                "location": location,
                **extras,
            }
            with st.spinner("Running vision + cause ranking…"):
                result = run_session(answers, image_bgr=image)
            st.session_state["last_result"] = result

            vis = result.get("vision") or {}
            q = result.get("quality") or {}
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Defect", result["pattern_specific_name"].replace("_", " "))
            m2.metric("Vision confidence", f"{(vis.get('confidence') or 0):.0%}" if vis else "n/a")
            m3.metric("Quality score", f"{q.get('overall_quality_score', '–')}/100")
            m4.metric("Review", "Manual" if result.get("manual_review") else "OK")

            if answers.get("vision_disagreement"):
                st.warning(
                    "Your symptom answer and the photo classifier disagree. "
                    "The ranking uses **your answers** — trust what you see on the line."
                )

            st.markdown("**Why this ranking**")
            st.write(result["explanation"])

            st.markdown("**Ranked causes**")
            chart = {c["name"]: c["likelihood_pct"] for c in result["ranked_causes"][:6]}
            st.bar_chart(chart)

            st.markdown("**Check first**")
            for step in result["action_plan"]:
                st.markdown(f"{step['step']}. {step['instruction']}")

            similar = result.get("similar") or {}
            st.success(similar.get("summary", ""))

            if result.get("downstream_warnings"):
                st.warning("Downstream risk: " + ", ".join(result["downstream_warnings"]))

            pdf = build_pdf(result)
            st.download_button(
                "Download PDF report",
                data=pdf,
                file_name="dispense-troubleshooting-report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    if "last_result" in st.session_state:
        with st.expander("Raw session JSON (for developers)"):
            st.json(st.session_state["last_result"])


def render_history() -> None:
    st.title("Case history")
    st.caption("Past troubleshooting sessions stored in SQLite (Bonus 3).")

    rows = recent_cases(25)
    if not rows:
        st.info("No cases logged yet. Run an analysis on the Troubleshoot page first.")
        return

    for row in rows:
        defect = (row.get("defect_class") or "").replace("_", " ")
        material = (row.get("material") or "").replace("_", " ")
        cause = (row.get("confirmed_cause") or "not confirmed").replace("_", " ")
        with st.expander(f"{row.get('created_at', '')[:19]} · {material} · {defect}"):
            st.write(f"**Session:** `{row.get('session_id')}`")
            st.write(f"**Pattern:** {row.get('pattern', 'n/a')}")
            st.write(f"**Confirmed cause:** {cause}")
            if row.get("explanation"):
                st.write(row["explanation"])


def main() -> None:
    st.set_page_config(
        page_title="AI Dispensing Defect Detective",
        page_icon="🏭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    seed_if_empty()
    rules = load_rules()
    model_ok = load_model() is not None
    try:
        case_count = connect().execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    except Exception:
        case_count = 0
    sample_count = len(list((ROOT / "data" / "samples").glob("*.png")))

    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem;}
        h1 {color: #0B3D5C;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "page" not in st.session_state:
        st.session_state["page"] = "Dashboard"

    with st.sidebar:
        st.markdown("## 🏭 Defect Detective")
        st.caption("NSW Automation · AI Horizon 2026")
        page = st.radio(
            "Navigation",
            ["Dashboard", "Troubleshoot", "Case history"],
            index=["Dashboard", "Troubleshoot", "Case history"].index(st.session_state["page"]),
            label_visibility="collapsed",
        )
        st.session_state["page"] = page
        st.divider()
        st.markdown("**Quick stats**")
        st.markdown(f"- Vision: {'✅ model loaded' if model_ok else '⚠️ heuristic'}")
        st.markdown(f"- Cases logged: **{case_count}**")
        st.markdown(f"- Sample images: **{sample_count}**")
        st.divider()
        st.markdown(
            "**NSW rule:** nozzle ID ≥ 5× largest powder size  \n"
            "Ranking is rule-based, not a generic chatbot."
        )

    if page == "Dashboard":
        render_dashboard(rules, model_ok, case_count, sample_count)
    elif page == "Troubleshoot":
        render_troubleshoot(rules)
    else:
        render_history()


if __name__ == "__main__":
    main()
