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
  possible_symptoms?: string[]
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
  possible_symptoms?: string[]
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
  annotated_image_base64?: string | null
  status: string
  created_at: string
  updated_at: string
}

export type HistoryCaseDetail = HistoryCaseSummary & {
  problem_description?: string | null
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

export async function analyzeImage(file: File, userEmail?: string): Promise<AnalyzeResponse> {
  const form = new FormData()
  form.append("file", file)
  if (userEmail) form.append("user_email", userEmail)
  const res = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form })
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function diagnoseWorkflow(
  analysis: AnalyzeResponse,
  answers: Record<string, string>,
  userEmail?: string,
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
      user_email: userEmail || (analysis as any).user_email,
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

export async function fetchHistory(limit = 50, userEmail?: string): Promise<{
  cases: HistoryCaseSummary[]
  count: number
  total: number
}> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (userEmail) params.set("user_email", userEmail)
  const res = await fetch(`${API_BASE}/history?${params.toString()}`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export type HistoryAnalytics = {
  total_scans: number
  diagnosed_count: number
  top_defect: string | null
  defect_distribution: { label: string; count: number; pct: number }[]
  available_years: number[]
  available_months: string[]
}

export async function fetchHistoryAnalytics(
  userEmail?: string,
  year?: number,
  month?: number,
): Promise<HistoryAnalytics> {
  const params = new URLSearchParams()
  if (userEmail) params.set("user_email", userEmail)
  if (year !== undefined && year !== null) params.set("year", String(year))
  if (month !== undefined && month !== null) params.set("month", String(month))

  const res = await fetch(`${API_BASE}/history/analytics?${params.toString()}`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export type CaseVolumeData = {
  labels: string[]   // e.g. ["Apr","May","Jun","Jul","Aug","Sep"]
  values: number[]   // scan counts per month
  trend_pct: number | null  // % change vs previous month, null if no prior data
  current_month_total: number
}

export async function fetchRealtimeCaseVolume(
  userEmail?: string,
  monthsBack = 6,
): Promise<CaseVolumeData> {
  const params = new URLSearchParams({ months_back: String(monthsBack) })
  if (userEmail) params.set("user_email", userEmail)
  const res = await fetch(`${API_BASE}/realtime/case-volume?${params.toString()}`)
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

export type LearningCauseSlice = { name: string; count: number; pct: number }

export type LearningInsights = {
  similar_count: number
  top_cause: string | null
  top_cause_count: number
  top_solution: string | null
  top_solution_count: number
  insight: string | null
  cause_breakdown: LearningCauseSlice[]
  solution_breakdown: LearningCauseSlice[]
}

export type LearningCase = {
  id: number
  case_id: string
  session_id?: string | null
  user_email?: string | null
  dispensing_problem: string
  defect_class?: string | null
  defect_label?: string | null
  possible_causes: string[]
  recommended_solutions: string[]
  successful_solution?: string | null
  successful_cause?: string | null
  source: string
  created_at: string
  updated_at: string
}

export type LearningStats = {
  total_cases: number
  resolved_count: number
  top_cause: string | null
  cause_breakdown: LearningCauseSlice[]
}

export async function fetchLearning(limit = 100): Promise<{
  cases: LearningCase[]
  count: number
  stats: LearningStats
}> {
  const res = await fetch(`${API_BASE}/learning?limit=${limit}`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function createLearningCase(payload: {
  dispensing_problem: string
  possible_causes: string[]
  recommended_solutions: string[]
  successful_solution?: string
  successful_cause?: string
  defect_class?: string
  defect_label?: string
  user_email?: string
}): Promise<{ case: LearningCase; insights: LearningInsights }> {
  const res = await fetch(`${API_BASE}/learning`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function markLearningSuccess(payload: {
  case_id?: string
  session_id?: string
  successful_solution: string
  successful_cause?: string
}): Promise<{ case: LearningCase; insights: LearningInsights }> {
  const res = await fetch(`${API_BASE}/learning/success`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export type CloudRagResult = {
  guidance: string
  past_cases: {
    id?: number
    case_id?: string
    defect_type?: string
    defect_label?: string
    dispensing_problem?: string
    root_cause?: string
    resolution_action?: string
    similarity?: number
    source?: string
  }[]
  case_count: number
  source: "cloud" | "local_db" | "deterministic"
  provider: "gemini" | "rule_based"
}

export async function fetchCloudRag(
  defect_type: string,
  opts: { defect_label?: string; problem?: string; top_k?: number } = {},
): Promise<CloudRagResult> {
  const res = await fetch(`${API_BASE}/cloud/rag`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ defect_type, ...opts }),
  })
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}

export async function fetchCloudStatus(): Promise<{
  supabase: { ready: boolean; url: string; error: string | null }
  embedder: { model: string; dim: number; ready: boolean; error: string | null }
}> {
  const res = await fetch(`${API_BASE}/cloud/status`)
  if (!res.ok) throw new Error(await readError(res))
  return res.json()
}
