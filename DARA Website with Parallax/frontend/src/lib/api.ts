const API_BASE = import.meta.env.VITE_API_BASE || "/api"

export type Detection = {
  id: number
  class_id: number
  label: string
  display_label: string
  confidence: number
  box: {
    x1: number
    y1: number
    x2: number
    y2: number
    width: number
    height: number
    cx: number
    cy: number
  }
}

export type FollowUpQuestion = {
  id: string
  prompt: string
  options: { value: string; label: string }[]
}

export type CauseRow = {
  cause_id: string
  name: string
  likelihood_pct: number
  reasoning: string
}

export type ActionStep = {
  step: number
  title: string
  detail: string
  status: string
  related_cause: string
}

export type AnalyzeResponse = {
  filename?: string
  defect_label: string
  defect_class?: string
  confidence?: number
  overall_quality_score: number
  shape_consistency: number
  size_consistency: number
  dispensing_position: number
  defect_risk: number
  annotated_image_base64: string
  detections: Detection[]
  vision: Record<string, unknown>
  quality: Record<string, unknown>
  followup_questions?: FollowUpQuestion[]
  causes?: CauseRow[]
  action_plan?: ActionStep[]
}

export type DiagnoseResponse = {
  defect_class: string
  defect_label: string
  confidence: number
  answers: Record<string, string>
  causes: CauseRow[]
  action_plan: ActionStep[]
  markdown_table: string
}

export type QaResponse = {
  answer: string
  provider: string
  model: string | null
  gemini_configured: boolean
  error?: string
}

async function readError(res: Response) {
  try {
    const data = await res.json()
    return data.detail || data.message || res.statusText
  } catch {
    return res.statusText
  }
}

export async function analyzeImage(file: File): Promise<AnalyzeResponse> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form })
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function diagnoseWorkflow(
  analysis: AnalyzeResponse,
  answers: Record<string, string>,
): Promise<DiagnoseResponse> {
  const res = await fetch(`${API_BASE}/workflow/diagnose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      defect_class: analysis.defect_class || analysis.vision?.defect_class,
      confidence: analysis.confidence ?? analysis.vision?.confidence ?? 0.8,
      detection_count: analysis.detections?.length ?? 0,
      answers,
      analysis,
    }),
  })
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function askQuestion(
  question: string,
  analysis: AnalyzeResponse | null,
  history: { role: string; content: string }[],
): Promise<QaResponse> {
  const res = await fetch(`${API_BASE}/qa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, analysis, history, use_gemini: false }),
  })
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function fetchMeta() {
  const res = await fetch(`${API_BASE}/meta`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}
