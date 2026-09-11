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
  session_id?: string
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
  session_id?: string
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

export type HistoryCaseSummary = {
  session_id: string
  filename?: string | null
  defect_class?: string | null
  defect_label?: string | null
  confidence?: number | null
  detection_count?: number | null
  quality_score?: number | null
  top_cause?: string | null
  top_cause_pct?: number | null
  status: string
  created_at: string
  updated_at: string
}

export type HistoryCaseDetail = HistoryCaseSummary & {
  shape_consistency?: number | null
  size_consistency?: number | null
  dispensing_position?: number | null
  defect_risk?: number | null
  answers?: Record<string, string>
  causes?: CauseRow[]
  action_plan?: ActionStep[]
  detections?: Detection[]
  annotated_image_base64?: string | null
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
      session_id: analysis.session_id,
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

export async function fetchHistory(limit = 50): Promise<{
  cases: HistoryCaseSummary[]
  count: number
  total: number
}> {
  const res = await fetch(`${API_BASE}/history?limit=${limit}`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function fetchCase(sessionId: string): Promise<HistoryCaseDetail> {
  const res = await fetch(`${API_BASE}/cases/${sessionId}`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function downloadReport(
  sessionId: string,
  format: "pdf" | "docx" = "pdf",
): Promise<void> {
  const res = await fetch(`${API_BASE}/report/${sessionId}?format=${format}`)
  if (!res.ok) throw new Error(await readError(res))
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `dara-report-${sessionId.slice(0, 12)}.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export type ReportChartSlice = { label: string; value: number }
export type ReportCause = { name: string; score: number; explanation: string }
export type ReportDetection = {
  id: number | string
  defect_class: string
  confidence_pct: number
  area_px?: number | null
}

export type ReportPayload = {
  session_id: string
  generated_at: string
  title: string
  subtitle: string
  brand: string
  footer: string
  problem_description: string
  defect: string
  defect_confidence_pct: number
  severity: string
  yield_pct: number
  detection_count: number
  overall_quality_score: number
  causes: ReportCause[]
  defect_distribution: ReportChartSlice[]
  analysis_statistics: ReportChartSlice[]
  detections: ReportDetection[]
  executive_summary: string
  process_insight: string
  diagnostic_findings: string[]
  maintenance_items: string[]
  action_plan: string[]
  engineer_notes?: string | null
  similar_case_note?: string | null
  methodology_note: string
}

export async function fetchReportData(sessionId: string): Promise<ReportPayload> {
  const res = await fetch(`${API_BASE}/report/${sessionId}/data`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export function reportPreviewUrl(sessionId: string) {
  return `${API_BASE}/report/${sessionId}/preview`
}
