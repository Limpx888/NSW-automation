import { useEffect, useState, type CSSProperties } from "react"
import {
  downloadReport,
  fetchCase,
  fetchHistory,
  fetchReportData,
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

function CasesWorkspace({
  title,
  subtitle,
  filterDiagnosed = false,
  onBack,
}: {
  title: string
  subtitle: string
  filterDiagnosed?: boolean
  onBack: () => void
}) {
  const [cases, setCases] = useState<HistoryCaseSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<HistoryCaseDetail | null>(null)
  const [report, setReport] = useState<ReportPayload | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)

  const load = async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchHistory(100)
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

  useEffect(() => {
    void load()
  }, [filterDiagnosed])

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
            onClick={() => void load()}
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

        {error && (
          <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 10, background: "rgba(239,68,68,0.1)", color: "#991B1B", fontSize: 13 }}>
            {error}
          </div>
        )}

        <div style={panel}>
          {loading ? (
            <p style={{ margin: 0, color: "rgba(22,32,42,0.55)" }}>Loading cases…</p>
          ) : cases.length === 0 ? (
            <p style={{ margin: 0, color: "rgba(22,32,42,0.55)" }}>
              No cases yet. Run a Solder Paste Scan to save history and generate reports.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {cases.map((c) => {
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

export function HistoryView({ onBack }: { onBack: () => void }) {
  return (
    <CasesWorkspace
      title="Case history"
      subtitle="Every solder-paste scan is saved here. Open a case to review evidence or regenerate its report."
      onBack={onBack}
    />
  )
}

export function ReportsView({ onBack }: { onBack: () => void }) {
  return (
    <CasesWorkspace
      title="Diagnostic reports"
      subtitle="View previous reports with cause charts and deep analysis, then download as PDF or Word."
      filterDiagnosed
      onBack={onBack}
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
