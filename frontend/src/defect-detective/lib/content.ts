export const DEMO_PRESET = {
  sample_image: "under_dispense__solder_paste__dot.png",
  material: "solder_paste",
  pattern: "dot",
  amount: "too_small",
  frequency: "continuous",
  recent_change: "nozzle",
  location: "multiple",
  powder_type: "T6",
  nozzle_id_um: 60,
  onset: "from_start",
} as const;

export const FEATURES = [
  {
    title: "Photo defect detection",
    bonus: "Bonus 1",
    desc: "Upload a top-down dispense photo. MobileNetV2 suggests one of 6 defect classes with a confidence score.",
    icon: "📷",
  },
  {
    title: "Guided Q&A with dynamic follow-ups",
    bonus: "Step 1",
    desc: "Five diagnostic dimensions. The next question adapts — occasional under-dispense asks restart vs runtime.",
    icon: "💬",
  },
  {
    title: "Fuzzy likelihood scoring",
    bonus: "Core AI",
    desc: "Score = baseline + Σ (evidence × μ). Crisp answers μ=1; “not sure” and overlapping looks get partial membership.",
    icon: "🎯",
  },
  {
    title: "WHY reasoning chain",
    bonus: "Step 4",
    desc: "Explains why #1 scored highest — not just a percentage.",
    icon: "🧠",
  },
  {
    title: "Troubleshooting checklist",
    bonus: "Step 5",
    desc: "Cheapest checks first (syringe bubbles) before expensive equipment inspection.",
    icon: "✅",
  },
  {
    title: "Quality score",
    bonus: "Bonus 2",
    desc: "0–100 quality score plus shape / size / defect-risk from the detected class.",
    icon: "⭐",
  },
  {
    title: "Similar case lookup",
    bonus: "Bonus 3",
    desc: "SQLite: how often this material × defect showed up, and what caused it.",
    icon: "📚",
  },
  {
    title: "PDF engineer report",
    bonus: "Bonus 4",
    desc: "Download ranked causes, action plan, and an engineer notes field.",
    icon: "📄",
  },
];

export const FOLLOWUP_KEYS = [
  "powder_type",
  "nozzle_id_um",
  "uv_barrel",
  "timing",
  "mix_state",
  "onset",
  "retract_stringing",
  "visible_bubbles",
];

export function pretty(value: unknown) {
  return String(value ?? "").replace(/_/g, " ");
}
