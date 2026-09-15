import { useEffect, useRef, useState, useCallback, type CSSProperties } from "react"
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  FileText,
  Eye,
  CheckCircle2,
  Clock,
  Target,
  Download,
  X,
  BarChart3,
} from "lucide-react"
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
  background: "rgba(255,255,255,0.85)",
  borderRadius: 22,
  padding: 24,
  border: "1px solid rgba(16,42,67,0.08)",
  boxShadow: "0 16px 40px rgba(16,42,67,0.06)",
}

function formatWhen(iso: string) {
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return d.toLocaleString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    })
  } catch {
    return iso
  }
}

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
]

// ============================================================================
// 1. HISTORY VIEW: Dedicated to Analytics, Defect Breakdown & Trends (Image 1)
// ============================================================================
export function HistoryView({ onBack, userEmail }: { onBack: () => void; userEmail?: string }) {
  const AUTO_REFRESH_MS = 30_000   // 30-second polling
  const [viewMode, setViewMode] = useState<"monthly" | "annual">("monthly")
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear())
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1)
  const [analytics, setAnalytics] = useState<HistoryAnalytics | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null)
  const [refreshPulse, setRefreshPulse] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadAnalytics = useCallback(async (silent = false) => {
    if (!userEmail) return
    if (!silent) setLoading(true)
    setError("")
    try {
      const yr = selectedYear
      const mo = viewMode === "monthly" ? selectedMonth : undefined
      const res = await fetchHistoryAnalytics(userEmail, yr, mo)
      setAnalytics(res)
      setLastRefreshed(new Date())
      // Brief flash to signal new data arrived
      setRefreshPulse(true)
      setTimeout(() => setRefreshPulse(false), 600)
      if (res.available_years.length > 0 && !res.available_years.includes(selectedYear)) {
        setSelectedYear(res.available_years[0])
      }
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : "Failed to load history analytics")
    } finally {
      if (!silent) setLoading(false)
    }
  }, [userEmail, viewMode, selectedYear, selectedMonth])

  // Initial load + dependency-driven reload
  useEffect(() => {
    void loadAnalytics()
  }, [loadAnalytics])

  // Auto-refresh every 30 s (silent — no spinner flicker)
  useEffect(() => {
    pollRef.current = setInterval(() => { void loadAnalytics(true) }, AUTO_REFRESH_MS)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [loadAnalytics])

  const prevMonth = () => {
    if (selectedMonth === 1) {
      setSelectedMonth(12)
      setSelectedYear((y) => y - 1)
    } else {
      setSelectedMonth((m) => m - 1)
    }
  }

  const nextMonth = () => {
    if (selectedMonth === 12) {
      setSelectedMonth(1)
      setSelectedYear((y) => y + 1)
    } else {
      setSelectedMonth((m) => m + 1)
    }
  }

  const periodLabel =
    viewMode === "monthly"
      ? `${MONTH_NAMES[selectedMonth - 1].toUpperCase()} ${selectedYear}`
      : `${selectedYear}`

  return (
    <section
      style={{
        minHeight: "100vh",
        padding: "96px 24px 64px",
        background: "linear-gradient(160deg, #EAF2F0 0%, #F5F8F7 45%, #EEF2F1 100%)",
      }}
    >
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        {/* Back Button */}
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            color: "#0B6873",
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            marginBottom: 20,
            padding: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          ← Back to dashboard
        </button>

        {/* 1. Header & Month Navigator (First Image Header) */}
        <div
          style={{
            ...panel,
            marginBottom: 24,
            display: "flex",
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: "rgba(11,104,115,0.12)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#0B6873",
                }}
              >
                <Calendar style={{ width: 20, height: 20 }} />
              </div>
              <h1
                style={{
                  margin: 0,
                  fontSize: 22,
                  fontWeight: 800,
                  color: "#102A43",
                  letterSpacing: "-0.02em",
                }}
              >
                History
              </h1>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "rgba(16,42,67,0.6)" }}>
              Every solder-paste scan is saved here. Review monthly defect trends, scan volumes, and historical analytics.
            </p>
          </div>

          {/* Auto-refresh status bar + Manual Refresh */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            {/* Live auto-refresh badge */}
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 999, background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
              <span style={{
                display: "inline-block", width: 7, height: 7, borderRadius: "50%",
                background: "#10B981", animation: "pulse-dot 2s infinite",
              }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: "#059669" }}>AUTO-REFRESH ON</span>
              {lastRefreshed && (
                <span style={{ fontSize: 10, color: "rgba(5,150,105,0.6)", marginLeft: 2 }}>
                  · {lastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </span>
              )}
            </div>
            {/* View Mode Toggle: Monthly / Annual */}
            <div style={{ display: "inline-flex", background: "#E2E8F0", borderRadius: 999, padding: 3 }}>
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

            {/* Month Navigator Controls */}
            {viewMode === "monthly" ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: "white",
                  borderRadius: 12,
                  border: "1px solid rgba(16,42,67,0.12)",
                  padding: "4px 8px",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
                }}
              >
                <button
                  type="button"
                  onClick={prevMonth}
                  title="Previous month"
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 6,
                    borderRadius: 6,
                    color: "#475569",
                    display: "flex",
                    alignItems: "center",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#F1F5F9")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                >
                  <ChevronLeft style={{ width: 16, height: 16 }} />
                </button>
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: "#102A43",
                    minWidth: 140,
                    textAlign: "center",
                    padding: "0 8px",
                  }}
                >
                  {MONTH_NAMES[selectedMonth - 1]} {selectedYear}
                </span>
                <button
                  type="button"
                  onClick={nextMonth}
                  title="Next month"
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 6,
                    borderRadius: 6,
                    color: "#475569",
                    display: "flex",
                    alignItems: "center",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#F1F5F9")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                >
                  <ChevronRight style={{ width: 16, height: 16 }} />
                </button>
              </div>
            ) : (
              <select
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                style={{
                  padding: "8px 16px",
                  borderRadius: 12,
                  border: "1px solid rgba(16,42,67,0.15)",
                  background: "white",
                  fontSize: 14,
                  fontWeight: 700,
                  color: "#102A43",
                  cursor: "pointer",
                }}
              >
                {(analytics?.available_years?.length ? analytics.available_years : [2026, 2025]).map((y) => (
                  <option key={y} value={y}>
                    Year {y}
                  </option>
                ))}
              </select>
            )}

            <button
              type="button"
              onClick={() => void loadAnalytics()}
              style={{
                background: "white",
                border: "1px solid rgba(11,104,115,0.25)",
                borderRadius: 999,
                padding: "8px 18px",
                color: "#0B6873",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div
            style={{
              marginBottom: 16,
              padding: "12px 16px",
              borderRadius: 12,
              background: "rgba(239,68,68,0.1)",
              color: "#991B1B",
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        {/* 2. Analytics & Top Defect Summary */}
        <div
          style={{
            ...panel,
            padding: "24px 28px",
            transition: "box-shadow 0.4s ease, border-color 0.4s ease",
            boxShadow: refreshPulse
              ? "0 0 0 2px rgba(16,185,129,0.5), 0 16px 40px rgba(16,42,67,0.06)"
              : undefined,
            borderColor: refreshPulse ? "rgba(16,185,129,0.4)" : undefined,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20 }}>
            {/* Top Defect Detected Card */}
            <div
              style={{
                background: "linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%)",
                borderRadius: 16,
                padding: "20px 24px",
                border: "1px solid rgba(16,185,129,0.25)",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                minHeight: 120,
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    color: "#166534",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 8,
                  }}
                >
                  <Target style={{ width: 15, height: 15 }} />
                  MOST DETECTED DEFECT ({periodLabel})
                </div>
                <div style={{ fontSize: 22, fontWeight: 900, color: "#064E3B", lineHeight: 1.2 }}>
                  {loading ? "…" : analytics?.top_defect || "NONE DETECTED"}
                </div>
              </div>
              <p style={{ margin: "10px 0 0", fontSize: 13, color: "#15803D", fontWeight: 600 }}>
                {analytics?.defect_distribution?.[0]
                  ? `${analytics.defect_distribution[0].count} scan(s) · ${analytics.defect_distribution[0].pct}% of period`
                  : "0 scan(s) · 0% of period"}
              </p>
            </div>

            {/* Total Period Scans Card */}
            <div
              style={{
                background: "linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%)",
                borderRadius: 16,
                padding: "20px 24px",
                border: "1px solid rgba(56,189,248,0.25)",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                minHeight: 120,
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    color: "#0369A1",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 8,
                  }}
                >
                  <BarChart3 style={{ width: 15, height: 15 }} />
                  TOTAL PERIOD SCANS
                </div>
                <div style={{ fontSize: 30, fontWeight: 900, color: "#0C4A6E", lineHeight: 1.1 }}>
                  {loading ? "…" : analytics?.total_scans ?? 0}
                </div>
              </div>
              <p style={{ margin: "10px 0 0", fontSize: 13, color: "#0284C7", fontWeight: 600 }}>
                {analytics?.diagnosed_count ?? 0} cases diagnosed with complete root cause
              </p>
            </div>
          </div>

          {/* Defect Frequency Breakdown Horizontal Bars */}
          <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px dashed rgba(16,42,67,0.12)" }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 800,
                color: "#102A43",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                marginBottom: 14,
              }}
            >
              DEFECT FREQUENCY BREAKDOWN
            </div>

            {analytics?.defect_distribution && analytics.defect_distribution.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {analytics.defect_distribution.map((item, idx) => (
                  <div key={item.label}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 13,
                        fontWeight: 700,
                        color: "#102A43",
                        marginBottom: 6,
                      }}
                    >
                      <span>
                        {idx + 1}. {item.label}
                      </span>
                      <span style={{ color: "#102A43", fontWeight: 700 }}>
                        {item.count} scan{item.count > 1 ? "s" : ""} ({item.pct}%)
                      </span>
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
            ) : (
              <div style={{ color: "rgba(16,42,67,0.45)", fontSize: 13, padding: "12px 0" }}>
                No defect data recorded for this period.
              </div>
            )}
          </div>
        </div>
      </div>
      <style>{`@keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.4;transform:scale(0.85)} }`}</style>
    </section>
  )
}

// ============================================================================
// 2. REPORTS VIEW: Dedicated to Monthly Case Cards & Diagnostic Inspection (Image 2)
// ============================================================================
export function ReportsView({
  onBack,
  userEmail,
  initialCaseId
}: {
  onBack: () => void;
  userEmail?: string;
  initialCaseId?: string | null
}) {
  const [cases, setCases] = useState<HistoryCaseSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [selectedCase, setSelectedCase] = useState<HistoryCaseDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [report, setReport] = useState<ReportPayload | null>(null)
  const [downloadFormat, setDownloadFormat] = useState<"pdf" | "docx">("pdf")
  const [downloadBusy, setDownloadBusy] = useState(false)

  // Month filtering state
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear())
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1)

  const load = async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchHistory(200, userEmail)
      setCases(data.cases)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [userEmail])

  // Automatically open report when initialCaseId or URL search changes
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const targetCaseId = initialCaseId || params.get("case_id")

    if (!targetCaseId) return

    const openTarget = async () => {
      const found = cases.find((c) => c.session_id === targetCaseId)
      if (found) {
        await openFullReport(found.session_id)
      } else if (!loading) {
        // Fallback: fetch directly if not found in current list
        setDetailLoading(true)
        try {
          const [caseData, reportData] = await Promise.all([
            fetchCase(targetCaseId),
            fetchReportData(targetCaseId).catch(() => null),
          ])
          setSelectedCase(caseData)
          setReport(reportData)
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to load report")
        } finally {
          setDetailLoading(false)
        }
      }
      window.history.replaceState({}, '', window.location.pathname)
    }

    void openTarget()
  }, [cases, loading, initialCaseId])

  // Filter cases strictly to the selected month & year
  const filteredCases = cases.filter((c) => {
    if (!c.created_at) return true
    try {
      const d = new Date(c.created_at)
      if (d.getFullYear() !== selectedYear) return false
      if (d.getMonth() + 1 !== selectedMonth) return false
      return true
    } catch {
      return true
    }
  })

  const prevMonth = () => {
    if (selectedMonth === 1) {
      setSelectedMonth(12)
      setSelectedYear((y) => y - 1)
    } else {
      setSelectedMonth((m) => m - 1)
    }
  }

  const nextMonth = () => {
    if (selectedMonth === 12) {
      setSelectedMonth(1)
      setSelectedYear((y) => y + 1)
    } else {
      setSelectedMonth((m) => m + 1)
    }
  }

  const openFullReport = async (sessionId: string) => {
    setDetailLoading(true)
    setError("")
    try {
      const [caseData, reportData] = await Promise.all([
        fetchCase(sessionId),
        fetchReportData(sessionId).catch(() => null),
      ])
      setSelectedCase(caseData)
      setReport(reportData)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report")
    } finally {
      setDetailLoading(false)
    }
  }

  const handleDownload = async (sessionId: string) => {
    setDownloadBusy(true)
    try {
      await downloadReport(sessionId, downloadFormat)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed")
    } finally {
      setDownloadBusy(false)
    }
  }

  const currentMonthLabel = `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}`

  return (
    <section
      style={{
        minHeight: "100vh",
        padding: "96px 24px 64px",
        background: "linear-gradient(160deg, #EAF2F0 0%, #F5F8F7 45%, #EEF2F1 100%)",
      }}
    >
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        {/* Back Link */}
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            color: "#0B6873",
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            marginBottom: 20,
            padding: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          ← Back to dashboard
        </button>

        {/* Header & Controls */}
        <div
          style={{
            ...panel,
            marginBottom: 24,
            display: "flex",
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: "rgba(11,104,115,0.12)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#0B6873",
                }}
              >
                <FileText style={{ width: 20, height: 20 }} />
              </div>
              <h1
                style={{
                  margin: 0,
                  fontSize: 22,
                  fontWeight: 800,
                  color: "#102A43",
                  letterSpacing: "-0.02em",
                }}
              >
                Monthly Case Reports
              </h1>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "rgba(16,42,67,0.6)" }}>
              Every solder-paste scan is saved here. Select any card to review full AI diagnostics and inspect reports.
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* Month Navigator */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: "white",
                borderRadius: 12,
                border: "1px solid rgba(16,42,67,0.12)",
                padding: "4px 8px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
              }}
            >
              <button
                type="button"
                onClick={prevMonth}
                title="Previous month"
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 6,
                  borderRadius: 6,
                  color: "#475569",
                  display: "flex",
                  alignItems: "center",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#F1F5F9")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
              >
                <ChevronLeft style={{ width: 16, height: 16 }} />
              </button>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 700,
                  color: "#102A43",
                  minWidth: 140,
                  textAlign: "center",
                  padding: "0 8px",
                }}
              >
                {currentMonthLabel}
              </span>
              <button
                type="button"
                onClick={nextMonth}
                title="Next month"
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 6,
                  borderRadius: 6,
                  color: "#475569",
                  display: "flex",
                  alignItems: "center",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#F1F5F9")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
              >
                <ChevronRight style={{ width: 16, height: 16 }} />
              </button>
            </div>

            <button
              type="button"
              onClick={() => void load()}
              style={{
                background: "white",
                border: "1px solid rgba(11,104,115,0.25)",
                borderRadius: 999,
                padding: "8px 18px",
                color: "#0B6873",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div
            style={{
              marginBottom: 16,
              padding: "12px 16px",
              borderRadius: 12,
              background: "rgba(239,68,68,0.1)",
              color: "#991B1B",
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        {/* Section Header: CASES LOGGED (count) - Matches Image 2 */}
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
              padding: "0 4px",
            }}
          >
            <h2
              style={{
                margin: 0,
                fontSize: 14,
                fontWeight: 800,
                color: "#102A43",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
              }}
            >
              CASES LOGGED ({filteredCases.length})
            </h2>
            <span style={{ fontSize: 13, color: "rgba(16,42,67,0.55)", fontWeight: 600 }}>
              {currentMonthLabel}
            </span>
          </div>

          {loading ? (
            <div style={{ ...panel, textAlign: "center", padding: 48, color: "rgba(16,42,67,0.5)" }}>
              Loading cases…
            </div>
          ) : filteredCases.length === 0 ? (
            <div style={{ ...panel, textAlign: "center", padding: 48, color: "rgba(16,42,67,0.5)" }}>
              <p style={{ margin: 0, fontSize: 15 }}>No cases found for {currentMonthLabel}.</p>
              <p style={{ margin: "6px 0 0", fontSize: 13, color: "rgba(16,42,67,0.4)" }}>
                Run a Solder Paste Scan to log defects and generate audit-ready reports.
              </p>
            </div>
          ) : (
            /* 3-column Visual Case Cards Grid (Image 2) */
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: 20,
              }}
            >
              {filteredCases.map((record) => {
                const label = (record.defect_label || record.defect_class || "UNKNOWN DEFECT").toUpperCase()
                const topCause = record.top_cause || "Awaiting diagnosis"
                const score = record.top_cause_pct != null ? `${Number(record.top_cause_pct).toFixed(0)}%` : null
                const timestamp = formatWhen(record.created_at)

                return (
                  <div
                    key={record.session_id}
                    onClick={() => void openFullReport(record.session_id)}
                    style={{
                      background: "white",
                      borderRadius: 18,
                      border: "1px solid rgba(16,42,67,0.1)",
                      boxShadow: "0 4px 20px rgba(16,42,67,0.04)",
                      overflow: "hidden",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = "translateY(-4px)"
                      e.currentTarget.style.borderColor = "#0B6873"
                      e.currentTarget.style.boxShadow = "0 12px 32px rgba(11,104,115,0.15)"
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = "none"
                      e.currentTarget.style.borderColor = "rgba(16,42,67,0.1)"
                      e.currentTarget.style.boxShadow = "0 4px 20px rgba(16,42,67,0.04)"
                    }}
                  >
                    {/* Card Header: Defect Name & Status */}
                    <div
                      style={{
                        padding: "14px 16px",
                        borderBottom: "1px solid rgba(16,42,67,0.06)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        background: "#F8FAFB",
                      }}
                    >
                      <h3
                        style={{
                          margin: 0,
                          fontSize: 14,
                          fontWeight: 800,
                          color: "#102A43",
                          letterSpacing: "0.02em",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          maxWidth: "65%",
                        }}
                      >
                        {label}
                      </h3>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          background:
                            record.status === "diagnosed" ? "rgba(16,185,129,0.12)" : "rgba(16,42,67,0.08)",
                          color: record.status === "diagnosed" ? "#047857" : "#4B5563",
                          fontSize: 11,
                          fontWeight: 700,
                          padding: "3px 8px",
                          borderRadius: 999,
                          border:
                            record.status === "diagnosed"
                              ? "1px solid rgba(16,185,129,0.25)"
                              : "1px solid rgba(16,42,67,0.1)",
                          textTransform: "uppercase",
                        }}
                      >
                        {record.status === "diagnosed" && <CheckCircle2 style={{ width: 12, height: 12 }} />}
                        {record.status}
                      </span>
                    </div>

                    {/* Card Body: Inspection Image Preview with Annotations */}
                    <div
                      style={{
                        position: "relative",
                        height: 180,
                        background: "#0F172A",
                        overflow: "hidden",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {record.annotated_image_base64 ? (
                        <img
                          src={`data:image/jpeg;base64,${record.annotated_image_base64}`}
                          alt={label}
                          style={{
                            width: "100%",
                            height: "100%",
                            objectFit: "cover",
                            transition: "transform 0.3s ease",
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            color: "#94A3B8",
                            fontSize: 12,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: 8,
                            padding: 16,
                            textAlign: "center",
                          }}
                        >
                          <FileText style={{ width: 32, height: 32, color: "#64748B" }} />
                          <span style={{ fontWeight: 600 }}>{record.filename || "Text Description"}</span>
                        </div>
                      )}

                      {/* Hover Overlay */}
                      <div
                        style={{
                          position: "absolute",
                          inset: 0,
                          background: "rgba(15,23,42,0.45)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          opacity: 0,
                          transition: "opacity 0.2s",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = "0")}
                      >
                        <span
                          style={{
                            background: "rgba(255,255,255,0.95)",
                            color: "#0F172A",
                            fontSize: 12,
                            fontWeight: 700,
                            padding: "6px 12px",
                            borderRadius: 8,
                            boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <Eye style={{ width: 14, height: 14, color: "#0B6873" }} />
                          Inspect Full Report
                        </span>
                      </div>
                    </div>

                    {/* Card Footer: Cause, Score & Timestamp */}
                    <div
                      style={{
                        padding: "14px 16px",
                        background: "white",
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                        flex: 1,
                        justifyContent: "space-between",
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: "#0B6873",
                            textTransform: "uppercase",
                            letterSpacing: "0.05em",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <Target style={{ width: 12, height: 12, color: "#0B6873" }} />
                          TOP DIAGNOSED CAUSE
                        </div>
                        <div
                          style={{
                            fontSize: 14,
                            fontWeight: 700,
                            color: "#1E293B",
                            marginTop: 3,
                            lineHeight: 1.3,
                          }}
                        >
                          {topCause}{" "}
                          {score && (
                            <span style={{ color: "#0B6873", fontWeight: 800 }}>({score})</span>
                          )}
                        </div>
                      </div>

                      <div
                        style={{
                          paddingTop: 10,
                          borderTop: "1px solid #F1F5F9",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          fontSize: 12,
                          color: "#64748B",
                        }}
                      >
                        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                          <Clock style={{ width: 13, height: 13, color: "#94A3B8" }} />
                          {timestamp}
                        </span>
                        <span
                          style={{
                            color: "#0B6873",
                            fontWeight: 700,
                            display: "flex",
                            alignItems: "center",
                            gap: 2,
                          }}
                        >
                          View Full Report →
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 4. Modal: Detailed Report Popup */}
        {(selectedCase || detailLoading) && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(15,23,42,0.65)",
              backdropFilter: "blur(6px)",
              zIndex: 999,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 20,
            }}
            onClick={() => {
              setSelectedCase(null)
              setReport(null)
            }}
          >
            <div
              style={{
                background: "white",
                borderRadius: 24,
                maxWidth: 1160,
                width: "100%",
                maxHeight: "92vh",
                overflowY: "auto",
                padding: "32px 36px",
                boxShadow: "0 25px 60px rgba(0,0,0,0.3)",
                border: "1px solid rgba(255,255,255,0.2)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {detailLoading ? (
                <div style={{ textAlign: "center", padding: 48, color: "#64748B" }}>
                  Loading diagnostic details…
                </div>
              ) : (
                selectedCase && (
                  <div>
                    {/* Modal Header */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        borderBottom: "1px solid #E2E8F0",
                        paddingBottom: 16,
                        marginBottom: 20,
                      }}
                    >
                      <div>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 800,
                            color: "#0B6873",
                            letterSpacing: "0.08em",
                            textTransform: "uppercase",
                          }}
                        >
                          Full Diagnostic Report
                        </span>
                        <h2
                          style={{
                            margin: "4px 0 0",
                            fontSize: 26,
                            fontWeight: 900,
                            color: "#102A43",
                            fontFamily: "'Barlow Condensed', sans-serif",
                          }}
                        >
                          {selectedCase.defect_label || selectedCase.defect_class || "Inspection Case"}
                        </h2>
                        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748B" }}>
                          {selectedCase.filename || "upload"} · {formatWhen(selectedCase.created_at)} ·{" "}
                          <span
                            style={{
                              fontWeight: 700,
                              color: selectedCase.status === "diagnosed" ? "#047857" : "#475569",
                              textTransform: "uppercase",
                            }}
                          >
                            {selectedCase.status}
                          </span>
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          setSelectedCase(null)
                          setReport(null)
                        }}
                        style={{
                          background: "#F1F5F9",
                          border: "none",
                          borderRadius: 8,
                          width: 32,
                          height: 32,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          cursor: "pointer",
                          color: "#64748B",
                        }}
                      >
                        <X style={{ width: 18, height: 18 }} />
                      </button>
                    </div>

                    {/* Image & Key Metrics */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "minmax(0, 1.2fr) minmax(220px, 0.8fr)",
                        gap: 18,
                        marginBottom: 20,
                      }}
                    >
                      {(() => {
                        const problemDescription =
                          selectedCase.problem_description ||
                          selectedCase.answers?.problem_description ||
                          selectedCase.answers?.user_description ||
                          selectedCase.answers?.description ||
                          report?.problem_description ||
                          (selectedCase.answers?.amount
                            ? `${selectedCase.answers.amount}${
                                selectedCase.answers.frequency ? ` · ${selectedCase.answers.frequency}` : ""
                              }${selectedCase.answers.recent_change ? ` · ${selectedCase.answers.recent_change}` : ""}`
                            : "Manual Text Description Record");

                        const contextTags: string[] = [];
                        if (selectedCase.answers?.amount && !problemDescription.includes(selectedCase.answers.amount)) {
                          contextTags.push(`Symptom: ${selectedCase.answers.amount}`);
                        }
                        if (selectedCase.answers?.frequency && !problemDescription.includes(selectedCase.answers.frequency)) {
                          contextTags.push(`Frequency: ${selectedCase.answers.frequency}`);
                        }
                        if (selectedCase.answers?.recent_change && !problemDescription.includes(selectedCase.answers.recent_change)) {
                          contextTags.push(`Recent Change: ${selectedCase.answers.recent_change}`);
                        }

                        return (
                          <div>
                            {selectedCase.annotated_image_base64 ? (
                              <div
                                style={{
                                  borderRadius: 16,
                                  overflow: "hidden",
                                  border: "1px solid #E2E8F0",
                                  background: "#0F172A",
                                }}
                              >
                                <img
                                  src={`data:image/jpeg;base64,${selectedCase.annotated_image_base64}`}
                                  alt="Annotated inspection"
                                  style={{ width: "100%", maxHeight: 260, objectFit: "cover" }}
                                />
                              </div>
                            ) : (
                              <div
                                style={{
                                  height: "100%",
                                  minHeight: 180,
                                  padding: "20px 22px",
                                  borderRadius: 16,
                                  background: "#F8FAFC",
                                  border: "1px solid #E2E8F0",
                                  display: "flex",
                                  flexDirection: "column",
                                  justifyContent: "space-between",
                                }}
                              >
                                <div>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "space-between",
                                      marginBottom: 12,
                                    }}
                                  >
                                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                      <div
                                        style={{
                                          width: 28,
                                          height: 28,
                                          borderRadius: 8,
                                          background: "rgba(11,104,115,0.1)",
                                          color: "#0B6873",
                                          display: "flex",
                                          alignItems: "center",
                                          justifyContent: "center",
                                        }}
                                      >
                                        <FileText style={{ width: 16, height: 16 }} />
                                      </div>
                                      <span
                                        style={{
                                          fontSize: 11,
                                          fontWeight: 800,
                                          color: "#0B6873",
                                          textTransform: "uppercase",
                                          letterSpacing: "0.06em",
                                        }}
                                      >
                                        Problem Description
                                      </span>
                                    </div>
                                    <span
                                      style={{
                                        fontSize: 11,
                                        fontWeight: 700,
                                        color: "#64748B",
                                        background: "#EDF2F7",
                                        padding: "3px 8px",
                                        borderRadius: 6,
                                      }}
                                    >
                                      User Input
                                    </span>
                                  </div>

                                  <div
                                    style={{
                                      fontSize: 14,
                                      lineHeight: 1.6,
                                      color: "#1E293B",
                                      fontWeight: 500,
                                      background: "white",
                                      padding: "14px 16px",
                                      borderRadius: 12,
                                      border: "1px solid #E2E8F0",
                                    }}
                                  >
                                    {problemDescription}
                                  </div>
                                </div>

                                {contextTags.length > 0 && (
                                  <div
                                    style={{
                                      display: "flex",
                                      flexWrap: "wrap",
                                      gap: 6,
                                      marginTop: 12,
                                    }}
                                  >
                                    {contextTags.map((tag, i) => (
                                      <span
                                        key={i}
                                        style={{
                                          fontSize: 11,
                                          color: "#475569",
                                          background: "white",
                                          padding: "3px 8px",
                                          borderRadius: 6,
                                          border: "1px solid #E2E8F0",
                                        }}
                                      >
                                        {tag}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        <div
                          style={{
                            background: "#F8FAFC",
                            borderRadius: 12,
                            padding: "10px 14px",
                            border: "1px solid #E2E8F0",
                          }}
                        >
                          <div style={{ fontSize: 11, fontWeight: 700, color: "#64748B", textTransform: "uppercase" }}>
                            Quality Score
                          </div>
                          <div style={{ fontSize: 20, fontWeight: 900, color: "#102A43", marginTop: 2 }}>
                            {selectedCase.quality_score != null ? `${selectedCase.quality_score}` : "—"}
                          </div>
                        </div>

                        <div
                          style={{
                            background: "#F8FAFC",
                            borderRadius: 12,
                            padding: "10px 14px",
                            border: "1px solid #E2E8F0",
                          }}
                        >
                          <div style={{ fontSize: 11, fontWeight: 700, color: "#64748B", textTransform: "uppercase" }}>
                            Confidence
                          </div>
                          <div style={{ fontSize: 20, fontWeight: 900, color: "#102A43", marginTop: 2 }}>
                            {selectedCase.confidence ? `${(selectedCase.confidence * 100).toFixed(0)}%` : "—"}
                          </div>
                        </div>

                        <div
                          style={{
                            background: "#F8FAFC",
                            borderRadius: 12,
                            padding: "10px 14px",
                            border: "1px solid #E2E8F0",
                          }}
                        >
                          <div style={{ fontSize: 11, fontWeight: 700, color: "#64748B", textTransform: "uppercase" }}>
                            Top Diagnosed Cause
                          </div>
                          <div style={{ fontSize: 14, fontWeight: 800, color: "#0B6873", marginTop: 2 }}>
                            {selectedCase.top_cause || "Pending"}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Causes Likelihood Analysis */}
                    {Array.isArray(selectedCase.causes) && selectedCase.causes.length > 0 && (
                      <div style={{ marginBottom: 20 }}>
                        <h4 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 800, color: "#102A43", textTransform: "uppercase" }}>
                          AI Cause Likelihood Analysis
                        </h4>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {selectedCase.causes.map((c: any, index: number) => {
                            const rawScore = c.score ?? c.likelihood_pct ?? c.probability ?? c.pct;
                            const formattedScore = rawScore != null ? `${Number(rawScore).toFixed(0)}%` : null;

                            return (
                              <div
                                key={c.name || index}
                                style={{
                                  background: "#F8FAFC",
                                  borderRadius: 12,
                                  padding: "12px 14px",
                                  border: "1px solid #E2E8F0",
                                }}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                  <strong style={{ color: "#102A43", fontSize: 14 }}>
                                    {c.name || c.cause || "Unknown Cause"}
                                  </strong>
                                  {formattedScore && (
                                    <span style={{ color: "#0B6873", fontWeight: 800, fontSize: 14 }}>
                                      {formattedScore}
                                    </span>
                                  )}
                                </div>
                                {(c.explanation || c.reasoning || c.description) && (
                                  <p style={{ margin: "4px 0 0", fontSize: 13, color: "#475569" }}>
                                    {c.explanation || c.reasoning || c.description}
                                  </p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Action Plan */}
                    {Array.isArray(selectedCase.action_plan) && selectedCase.action_plan.length > 0 && (
                      <div style={{ marginBottom: 20 }}>
                        <h4 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 800, color: "#102A43", textTransform: "uppercase" }}>
                          Recommended Action Plan
                        </h4>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {selectedCase.action_plan.map((step: any, idx: number) => {
                            const stepNum = step?.step || idx + 1;
                            const actionText = typeof step === "string"
                              ? step
                              : step?.action || step?.description || step?.title || JSON.stringify(step);

                            return (
                              <div
                                key={idx}
                                style={{
                                  display: "flex",
                                  gap: 12,
                                  background: "#F8FAFC",
                                  padding: "12px 14px",
                                  borderRadius: 12,
                                  border: "1px solid #E2E8F0",
                                  alignItems: "center",
                                }}
                              >
                                <div
                                  style={{
                                    width: 24,
                                    height: 24,
                                    borderRadius: "50%",
                                    background: "#0B6873",
                                    color: "white",
                                    fontSize: 12,
                                    fontWeight: 800,
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    flexShrink: 0,
                                  }}
                                >
                                  {stepNum}
                                </div>
                                <div style={{ fontSize: 13, fontWeight: 700, color: "#102A43", lineHeight: 1.4 }}>
                                  {actionText}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Report Preview Document View */}
                    {report && (
                      <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid #E2E8F0" }}>
                        <ReportDocument data={report} />
                      </div>
                    )}

                    {/* Modal Actions Footer */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 12,
                        paddingTop: 16,
                        borderTop: "1px solid #E2E8F0",
                        marginTop: 20,
                        flexWrap: "wrap",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <select
                          value={downloadFormat}
                          onChange={(e) => setDownloadFormat(e.target.value as "pdf" | "docx")}
                          style={{
                            padding: "8px 12px",
                            borderRadius: 10,
                            border: "1px solid #CBD5E1",
                            fontSize: 13,
                            background: "white",
                          }}
                        >
                          <option value="pdf">PDF Document</option>
                          <option value="docx">Word (.docx)</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => void handleDownload(selectedCase.session_id)}
                          disabled={downloadBusy}
                          style={{
                            background: downloadBusy ? "#94A3B8" : "#0B6873",
                            color: "white",
                            border: "none",
                            borderRadius: 10,
                            padding: "8px 16px",
                            fontSize: 13,
                            fontWeight: 700,
                            cursor: downloadBusy ? "not-allowed" : "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <Download style={{ width: 14, height: 14 }} />
                          {downloadBusy ? "Generating…" : "Export Report"}
                        </button>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          setSelectedCase(null)
                          setReport(null)
                        }}
                        style={{
                          background: "#F1F5F9",
                          border: "1px solid #CBD5E1",
                          borderRadius: 10,
                          padding: "8px 18px",
                          fontSize: 13,
                          fontWeight: 700,
                          color: "#475569",
                          cursor: "pointer",
                        }}
                      >
                        Close
                      </button>
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

// Standalone Report Download Bar
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
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
