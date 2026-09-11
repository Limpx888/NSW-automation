import { useEffect, useState, type CSSProperties } from "react"
import {
  downloadReport,
  fetchCase,
  fetchHistory,
  fetchHistoryAnalytics,
  fetchReportData,
  type HistoryAnalytics,
  type HistoryCaseDetail,
  type HistoryCaseSummary,
  type ReportPayload,
} from "@/lib/api"
import ReportDocument from "@/ReportDocument"

const panel: CSSProperties = {
  background: "rgba(255,255,255,0.78)",
  borderRadius: 22,
  padding: 20,
  border: "1px solid rgba(16,42,67,0.08)",
  boxShadow: "0 16px 40px rgba(16,42,67,0.06)",
}

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function ReportActions({
  sessionId,
  onView,
}: {
  sessionId: string
  onView: () => void
}) {
  const [format, setFormat] = useState<"pdf" | "docx">("pdf")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  const handleDownload = async () => {
    setBusy(true)
    setError("")
    try {
      await downloadReport(sessionId, format)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
      <button
        type="button"
        onClick={onView}
        style={{
          background: "white",
          color: "#0B6873",
          border: "1px solid rgba(11,104,115,0.35)",
          borderRadius: 999,
          padding: "9px 16px",
          fontSize: 13,
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        View report
      </button>
      <select
        value={format}
        onChange={(e) => setFormat(e.target.value as "pdf" | "docx")}
        disabled={busy}
        style={{
          borderRadius: 999,
          border: "1px solid rgba(16,42,67,0.15)",
          padding: "9px 14px",
          fontSize: 13,
          background: "white",
        }}
      >
        <option value="pdf">PDF</option>
        <option value="docx">Word (.docx)</option>
      </select>
      <button
        type="button"
        onClick={() => void handleDownload()}
        disabled={busy}
        style={{
          background: busy ? "rgba(22,32,42,0.2)" : "#0B6873",
          color: "white",
          border: "none",
          borderRadius: 999,
          padding: "9px 16px",
          fontSize: 13,
          fontWeight: 700,
          cursor: busy ? "not-allowed" : "pointer",
        }}
      >
        {busy ? "Generating…" : "Download"}
      </button>
      {error && <span style={{ fontSize: 12, color: "#991B1B" }}>{error}</span>}
    </div>
  )
}

function CaseDetail({
  caseData,
  onClose,
  onViewReport,
}: {
  caseData: HistoryCaseDetail
  onClose: () => void
  onViewReport: () => void
}) {
  return (
    <div style={{ ...panel, marginTop: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#0B6873" }}>
            CASE DETAIL
          </div>
          <h2 style={{ margin: "6px 0 0", fontFamily: "'Barlow Condensed', sans-serif", fontSize: 28, color: "#102A43" }}>
            {caseData.defect_label || caseData.defect_class || "Untitled case"}
          </h2>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "rgba(22,32,42,0.55)" }}>
            {caseData.filename || "upload"} · {formatWhen(caseData.created_at)} · {caseData.status}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{ background: "none", border: "none", color: "#0B6873", fontWeight: 700, cursor: "pointer" }}
        >
          Close
        </button>
      </div>

      <ReportActions sessionId={caseData.session_id} onView={onViewReport} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.1fr) minmax(240px, 0.9fr)",
          gap: 16,
          marginTop: 18,
        }}
        className="scan-grid"
      >
        <div>
          {caseData.annotated_image_base64 ? (
            <img
              src={`data:image/jpeg;base64,${caseData.annotated_image_base64}`}
              alt="Annotated inspection"
              style={{ width: "100%", borderRadius: 16, border: "1px solid rgba(16,42,67,0.08)" }}
            />
          ) : (
            <div style={{ padding: 24, borderRadius: 16, background: "#EEF2F1", color: "rgba(22,32,42,0.5)" }}>
              No annotated image stored for this case.
            </div>
          )}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Metric label="Quality score" value={caseData.quality_score != null ? `${caseData.quality_score}` : "—"} />
          <Metric label="Confidence" value={formatConfidence(caseData.confidence)} />
          <Metric label="Detections" value={String(caseData.detection_count ?? 0)} />
          <Metric label="Top cause" value={caseData.top_cause || "Not diagnosed yet"} />
        </div>
      </div>

      {(caseData.causes?.length || 0) > 0 && (
        <div style={{ marginTop: 18 }}>
          <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 10 }}>
            CAUSES
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {caseData.causes!.map((c) => (
              <div
                key={c.cause_id || c.name}
                style={{
                  background: "white",
                  borderRadius: 12,
                  padding: "10px 12px",
                  border: "1px solid rgba(16,42,67,0.08)",
                }}
              >
                <strong style={{ color: "#102A43" }}>
                  {c.name} · {Number(c.likelihood_pct).toFixed(0)}%
                </strong>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "rgba(22,32,42,0.65)" }}>{c.reasoning}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "white", borderRadius: 14, padding: "12px 14px", border: "1px solid rgba(16,42,67,0.08)" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: "rgba(22,32,42,0.45)", textTransform: "uppercase" }}>
        {label}
      </div>
      <div style={{ marginTop: 4, fontSize: 18, fontWeight: 800, color: "#102A43" }}>{value}</div>
    </div>
  )
}

function formatConfidence(confidence?: number | null) {
  if (confidence == null) return "—"
  const pct = confidence <= 1 ? confidence * 100 : confidence
  return `${pct.toFixed(0)}%`
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
]

function CasesWorkspace({
  title,
  subtitle,
  filterDiagnosed = false,
  onBack,
  userEmail,
}: {
  title: string
  subtitle: string
  filterDiagnosed?: boolean
  onBack: () => void
  userEmail?: string
}) {
  const [cases, setCases] = useState<HistoryCaseSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<HistoryCaseDetail | null>(null)
  const [report, setReport] = useState<ReportPayload | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)

  // Analytics & Filtering state
  const [viewMode, setViewMode] = useState<"monthly" | "annual">("monthly")
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear())
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1)
  const [analytics, setAnalytics] = useState<HistoryAnalytics | null>(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchHistory(200, userEmail)
      const list = filterDiagnosed
        ? data.cases.filter((c) => c.status === "diagnosed" || (c.top_cause && c.top_cause.length > 0))
        : data.cases
      setCases(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history")
    } finally {
      setLoading(false)
    }
  }

  const loadAnalytics = async () => {
    if (!userEmail) return
    setAnalyticsLoading(true)
    try {
      const yr = selectedYear
      const mo = viewMode === "monthly" ? selectedMonth : undefined
      const res = await fetchHistoryAnalytics(userEmail, yr, mo)
      setAnalytics(res)
      if (res.available_years.length > 0 && !res.available_years.includes(selectedYear)) {
        setSelectedYear(res.available_years[0])
      }
    } catch (err) {
      console.error("Analytics fetch error:", err)
    } finally {
      setAnalyticsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [filterDiagnosed, userEmail])

  useEffect(() => {
    void loadAnalytics()
  }, [userEmail, viewMode, selectedYear, selectedMonth])

  // Filter cases displayed based on selected time window
  const filteredCases = cases.filter((c) => {
    if (!c.created_at) return true
    try {
      const d = new Date(c.created_at)
      if (d.getFullYear() !== selectedYear) return false
      if (viewMode === "monthly" && (d.getMonth() + 1) !== selectedMonth) return false
      return true
    } catch {
      return true
    }
  })

  const openCase = async (sessionId: string) => {
    setSelectedId(sessionId)
    setReport(null)
    setError("")
    try {
      const data = await fetchCase(sessionId)
      setDetail(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load case")
      setDetail(null)
    }
  }

  const openPreview = async (sessionId: string) => {
    setPreviewBusy(true)
    setError("")
    try {
      setReport(await fetchReportData(sessionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed")
    } finally {
      setPreviewBusy(false)
    }
  }

  return (
    <section style={{ minHeight: "100vh", padding: "96px 28px 64px", background: "linear-gradient(160deg, #EAF2F0 0%, #F5F8F7 45%, #EEF2F1 100%)" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <button
          type="button"
          onClick={onBack}
          style={{ background: "none", border: "none", color: "#0B6873", fontSize: 13, fontWeight: 600, cursor: "pointer", marginBottom: 20, padding: 0 }}
        >
          ← Back to dashboard
        </button>

        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 22 }}>
          <div>
            <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#0B6873", marginBottom: 8 }}>
              {filterDiagnosed ? "Reports" : "History"}
            </p>
            <h1
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: "clamp(2rem, 4vw, 2.8rem)",
                fontWeight: 800,
                color: "#102A43",
                margin: "0 0 8px",
              }}
            >
              {title}
            </h1>
            <p style={{ margin: 0, color: "rgba(22,32,42,0.6)", fontSize: 15 }}>{subtitle}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              void load()
              void loadAnalytics()
            }}
            style={{
              alignSelf: "flex-start",
              background: "white",
              border: "1px solid rgba(11,104,115,0.25)",
              borderRadius: 999,
              padding: "10px 18px",
              color: "#0B6873",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Refresh
          </button>
        </div>

        {/* ── Timeframe & Analytics Bar ── */}
        <div style={{ ...panel, marginBottom: 20, background: "white" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16, marginBottom: 18, borderBottom: "1px solid rgba(16,42,67,0.08)", paddingBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#102A43" }}>Timeframe:</span>
              <div style={{ display: "inline-flex", background: "#F1F5F9", borderRadius: 999, padding: 3 }}>
                <button
                  type="button"
                  onClick={() => setViewMode("monthly")}
                  style={{
                    border: "none",
                    borderRadius: 999,
                    padding: "6px 14px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    background: viewMode === "monthly" ? "#0B6873" : "transparent",
                    color: viewMode === "monthly" ? "white" : "#64748B",
                    transition: "all 0.2s",
                  }}
                >
                  Monthly
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("annual")}
                  style={{
                    border: "none",
                    borderRadius: 999,
                    padding: "6px 14px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    background: viewMode === "annual" ? "#0B6873" : "transparent",
                    color: viewMode === "annual" ? "white" : "#64748B",
                    transition: "all 0.2s",
                  }}
                >
                  Annual
                </button>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {viewMode === "monthly" && (
                <select
                  value={selectedMonth}
                  onChange={(e) => setSelectedMonth(Number(e.target.value))}
                  style={{
                    padding: "7px 14px",
                    borderRadius: 10,
                    border: "1px solid rgba(16,42,67,0.15)",
                    background: "#F8FAFC",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "#102A43",
                  }}
                >
                  {MONTH_NAMES.map((m, idx) => (
                    <option key={m} value={idx + 1}>
                      {m}
                    </option>
                  ))}
                </select>
              )}

              <select
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                style={{
                  padding: "7px 14px",
                  borderRadius: 10,
                  border: "1px solid rgba(16,42,67,0.15)",
                  background: "#F8FAFC",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#102A43",
                }}
              >
                {(analytics?.available_years?.length ? analytics.available_years : [2026, 2025]).map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Analytics KPI & Defect Chart */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            {/* KPI Card 1: Top Defect Detected */}
            <div style={{ background: "linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%)", borderRadius: 16, padding: "16px 18px", border: "1px solid rgba(16,185,129,0.2)" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#166534", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>
                MOST COMMON DEFECT ({viewMode === "monthly" ? `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}` : selectedYear})
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#064E3B", lineHeight: 1.2 }}>
                {analyticsLoading ? "Loading..." : analytics?.top_defect || "None Detected"}
              </div>
              <p style={{ margin: "6px 0 0", fontSize: 12, color: "#15803D" }}>
                {analytics?.defect_distribution?.[0]
                  ? `${analytics.defect_distribution[0].count} scan(s) · ${analytics.defect_distribution[0].pct}% of period total`
                  : "No defects logged in this period"}
              </p>
            </div>

            {/* KPI Card 2: Period Total Scans */}
            <div style={{ background: "linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%)", borderRadius: 16, padding: "16px 18px", border: "1px solid rgba(56,189,248,0.2)" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#0369A1", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>
                TOTAL SCANS ({viewMode === "monthly" ? `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}` : selectedYear})
              </div>
              <div style={{ fontSize: 28, fontWeight: 900, color: "#0C4A6E" }}>
                {analyticsLoading ? "…" : analytics?.total_scans ?? 0}
              </div>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: "#0284C7" }}>
                {analytics?.diagnosed_count ?? 0} diagnosed with root-cause analysis
              </p>
            </div>
          </div>

          {/* Defect Distribution Chart */}
          {analytics?.defect_distribution && analytics.defect_distribution.length > 0 && (
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px dashed rgba(16,42,67,0.12)" }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: "#102A43", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 12 }}>
                DEFECT FREQUENCY BREAKDOWN CHART
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {analytics.defect_distribution.map((item, idx) => (
                  <div key={item.label}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: 700, color: "#102A43", marginBottom: 4 }}>
                      <span>{idx + 1}. {item.label}</span>
                      <span>{item.count} scan{item.count > 1 ? "s" : ""} ({item.pct}%)</span>
                    </div>
                    <div style={{ height: 10, background: "#E2E8F0", borderRadius: 999, overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${item.pct}%`,
                          background: idx === 0 ? "#D66A2C" : idx === 1 ? "#0B6873" : "#F2A65A",
                          borderRadius: 999,
                          transition: "width 0.5s ease-out",
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {error && (
          <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 10, background: "rgba(239,68,68,0.1)", color: "#991B1B", fontSize: 13 }}>
            {error}
          </div>
        )}

        {/* ── Case History List ── */}
        <div style={panel}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 800, color: "#102A43", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              RECORDS ({filteredCases.length})
            </span>
            <span style={{ fontSize: 12, color: "rgba(22,32,42,0.5)" }}>
              {viewMode === "monthly" ? `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}` : selectedYear}
            </span>
          </div>

          {loading ? (
            <p style={{ margin: 0, color: "rgba(22,32,42,0.55)" }}>Loading cases…</p>
          ) : filteredCases.length === 0 ? (
            <p style={{ margin: 0, color: "rgba(22,32,42,0.55)" }}>
              No cases found for {viewMode === "monthly" ? `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}` : selectedYear}. Run a Solder Paste Scan to add records.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {filteredCases.map((c) => {
                const active = selectedId === c.session_id
                return (
                  <button
                    key={c.session_id}
                    type="button"
                    onClick={() => void openCase(c.session_id)}
                    style={{
                      textAlign: "left",
                      background: active ? "rgba(11,104,115,0.08)" : "white",
                      border: active ? "1px solid rgba(11,104,115,0.35)" : "1px solid rgba(16,42,67,0.08)",
                      borderRadius: 16,
                      padding: "14px 16px",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                      <div>
                        <div style={{ fontWeight: 800, color: "#102A43", fontSize: 15 }}>
                          {c.defect_label || c.defect_class || "Unknown defect"}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 12, color: "rgba(22,32,42,0.55)" }}>
                          {c.filename || "upload"} · {formatWhen(c.created_at)}
                        </div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div
                          style={{
                            display: "inline-block",
                            fontSize: 11,
                            fontWeight: 700,
                            padding: "3px 8px",
                            borderRadius: 999,
                            background: c.status === "diagnosed" ? "rgba(16,185,129,0.12)" : "rgba(16,42,67,0.08)",
                            color: c.status === "diagnosed" ? "#047857" : "#4B5563",
                            textTransform: "uppercase",
                          }}
                        >
                          {c.status}
                        </div>
                        <div style={{ marginTop: 6, fontSize: 12, color: "rgba(22,32,42,0.6)" }}>
                          {c.top_cause
                            ? `${c.top_cause}${c.top_cause_pct != null ? ` (${Number(c.top_cause_pct).toFixed(0)}%)` : ""}`
                            : "Awaiting diagnosis"}
                        </div>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {detail && (
          <CaseDetail
            caseData={detail}
            onClose={() => {
              setDetail(null)
              setSelectedId(null)
              setReport(null)
            }}
            onViewReport={() => void openPreview(detail.session_id)}
          />
        )}

        {(previewBusy || report) && (
          <div style={{ ...panel, marginTop: 18, background: "transparent", border: "none", boxShadow: "none", padding: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12, alignItems: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43" }}>
                REPORT PREVIEW
              </div>
              <button
                type="button"
                onClick={() => setReport(null)}
                style={{ background: "none", border: "none", color: "#0B6873", fontWeight: 700, cursor: "pointer" }}
              >
                Hide preview
              </button>
            </div>
            {previewBusy ? (
              <p style={{ margin: 0, color: "rgba(22,32,42,0.55)" }}>Generating charts and analysis…</p>
            ) : (
              report && <ReportDocument data={report} />
            )}
          </div>
        )}
      </div>
    </section>
  )
}

export function HistoryView({ onBack, userEmail }: { onBack: () => void; userEmail?: string }) {
  return (
    <CasesWorkspace
      title="Case history"
      subtitle="Every solder-paste scan is saved here. Open a case to review evidence or regenerate its report."
      onBack={onBack}
      userEmail={userEmail}
    />
  )
}

export function ReportsView({ onBack, userEmail }: { onBack: () => void; userEmail?: string }) {
  return (
    <CasesWorkspace
      title="Diagnostic reports"
      subtitle="View previous reports with cause charts and deep analysis, then download as PDF or Word."
      filterDiagnosed
      onBack={onBack}
      userEmail={userEmail}
    />
  )
}

export function ReportDownloadBar({ sessionId }: { sessionId: string }) {
  const [format, setFormat] = useState<"pdf" | "docx">("pdf")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [report, setReport] = useState<ReportPayload | null>(null)

  const download = async () => {
    setBusy(true)
    setError("")
    try {
      await downloadReport(sessionId, format)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed")
    } finally {
      setBusy(false)
    }
  }

  const preview = async () => {
    setBusy(true)
    setError("")
    try {
      setReport(await fetchReportData(sessionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ ...panel, marginTop: 20 }}>
      <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 8 }}>
        SAVE & REPORT
      </div>
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "rgba(22,32,42,0.55)" }}>
        NSW-style report with Chart.js defect distribution, analysis statistics, and maintenance insights. Download as PDF or Word.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        <select
          value={format}
          onChange={(e) => setFormat(e.target.value as "pdf" | "docx")}
          disabled={busy}
          style={{
            borderRadius: 999,
            border: "1px solid rgba(16,42,67,0.15)",
            padding: "10px 14px",
            fontSize: 13,
            background: "white",
          }}
        >
          <option value="pdf">PDF</option>
          <option value="docx">Word (.docx)</option>
        </select>
        <button
          type="button"
          onClick={() => void preview()}
          disabled={busy}
          style={{
            background: "white",
            color: "#0B6873",
            border: "1px solid rgba(11,104,115,0.35)",
            borderRadius: 999,
            padding: "10px 16px",
            fontWeight: 700,
            cursor: busy ? "not-allowed" : "pointer",
          }}
        >
          View report
        </button>
        <button
          type="button"
          onClick={() => void download()}
          disabled={busy}
          style={{
            background: busy ? "rgba(22,32,42,0.2)" : "#D66A2C",
            color: "white",
            border: "none",
            borderRadius: 999,
            padding: "10px 16px",
            fontWeight: 700,
            cursor: busy ? "not-allowed" : "pointer",
          }}
        >
          {busy ? "Working…" : "Download report"}
        </button>
        {report && (
          <button
            type="button"
            onClick={() => setReport(null)}
            style={{ background: "none", border: "none", color: "#0B6873", fontWeight: 700, cursor: "pointer" }}
          >
            Hide preview
          </button>
        )}
      </div>
      {error && <p style={{ margin: "10px 0 0", color: "#991B1B", fontSize: 13 }}>{error}</p>}
      {report && (
        <div style={{ marginTop: 16 }}>
          <ReportDocument data={report} />
        </div>
      )}
    </div>
  )
}
