import { useEffect, useRef, useState, type CSSProperties } from "react"
import {
  createLearningCase,
  fetchCloudRag,
  fetchCloudStatus,
  fetchLearning,
  markLearningSuccess,
  type CloudRagResult,
  type LearningCase,
  type LearningCauseSlice,
  type LearningInsights,
  type LearningStats,
} from "@/lib/api"

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatTitle(raw?: string | null): string {
  if (!raw) return "—"
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

function cleanSolution(text: string): string {
  if (!text) return ""
  return text.replace(/^[a-z0-9_]+:\s*/i, "")
}

function asList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => (typeof item === "string" ? item : String((item as { name?: string })?.name || item)))
    .filter(Boolean)
}

function pct(count: number, total: number) {
  return total ? Math.round((count / total) * 100) : 0
}

function timeAgo(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return "just now"
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ─── Design tokens ───────────────────────────────────────────────────────────

const TEAL = "#0B6873"
const ORANGE = "#D66A2C"
const DARK = "#102A43"
const MUTED = "#64748B"

const card: CSSProperties = {
  background: "rgba(255,255,255,0.92)",
  borderRadius: 20,
  padding: 24,
  border: "1px solid rgba(16,42,67,0.08)",
  boxShadow: "0 8px 32px rgba(16,42,67,0.07)",
}

// ─── Mini bar chart ──────────────────────────────────────────────────────────

function BarChart({ data, color = TEAL }: { data: LearningCauseSlice[]; color?: string }) {
  const max = Math.max(...data.map((d) => d.count), 1)
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {data.slice(0, 6).map((row) => (
        <div key={row.name}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: DARK, maxWidth: "70%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {formatTitle(row.name)}
            </span>
            <span style={{ fontSize: 12, fontWeight: 700, color: MUTED }}>
              {row.count} ({row.pct}%)
            </span>
          </div>
          <div style={{ background: "rgba(16,42,67,0.06)", borderRadius: 6, height: 8, overflow: "hidden" }}>
            <div
              style={{
                width: `${(row.count / max) * 100}%`,
                height: "100%",
                background: color,
                borderRadius: 6,
                transition: "width 0.8s ease",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Donut chart (pure SVG) ──────────────────────────────────────────────────

const DONUT_COLOURS = [TEAL, ORANGE, "#6366F1", "#F59E0B", "#10B981", "#EC4899"]

function DonutChart({ data, size = 130 }: { data: LearningCauseSlice[]; size?: number }) {
  const r = size * 0.38
  const cx = size / 2
  const circumference = 2 * Math.PI * r
  const total = data.reduce((s, d) => s + d.count, 0)
  if (!total) return <div style={{ textAlign: "center", color: MUTED, fontSize: 13 }}>No data yet</div>

  let offset = 0
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={cx} cy={cx} r={r} fill="none" stroke="rgba(16,42,67,0.06)" strokeWidth={size * 0.12} />
        {data.slice(0, 6).map((slice, i) => {
          const frac = slice.count / total
          const dash = frac * circumference
          const el = (
            <circle
              key={slice.name}
              cx={cx} cy={cx} r={r}
              fill="none"
              stroke={DONUT_COLOURS[i % DONUT_COLOURS.length]}
              strokeWidth={size * 0.12}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
            />
          )
          offset += dash
          return el
        })}
      </svg>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center" }}>
        {data.slice(0, 6).map((slice, i) => (
          <div key={slice.name} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: DONUT_COLOURS[i % DONUT_COLOURS.length], flexShrink: 0 }} />
            <span style={{ fontSize: 10, color: MUTED, fontWeight: 600 }}>{formatTitle(slice.name)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Cloud status badge ───────────────────────────────────────────────────────

function CloudBadge({ ready, label }: { ready: boolean; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: ready ? "#059669" : MUTED }}>
      <div style={{
        width: 7, height: 7, borderRadius: "50%",
        background: ready ? "#10B981" : "#CBD5E1",
        boxShadow: ready ? "0 0 0 2px rgba(16,185,129,0.25)" : "none",
      }} />
      {label}
    </div>
  )
}

// ─── RAG copilot panel ────────────────────────────────────────────────────────

function RagCopilotPanel({ defectType, defectLabel }: { defectType: string; defectLabel?: string }) {
  const [result, setResult] = useState<CloudRagResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [problem, setProblem] = useState("")
  const [err, setErr] = useState("")

  const run = async () => {
    setLoading(true)
    setErr("")
    setResult(null)
    try {
      const r = await fetchCloudRag(defectType, { defect_label: defectLabel, problem, top_k: 3 })
      setResult(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally {
      setLoading(false)
    }
  }

  const sourceLabelMap: Record<string, string> = {
    cloud: "☁ Supabase cloud vector search",
    local_db: "💾 Local SQLite knowledge base",
    deterministic: "⚙ Rule-based fallback",
  }
  const providerLabel = result?.provider === "gemini" ? "🤖 Gemini AI" : "📋 Rule-based"

  return (
    <div style={{ ...card, background: "linear-gradient(135deg, rgba(11,104,115,0.05), rgba(99,102,241,0.05))", border: "1.5px solid rgba(11,104,115,0.18)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <div style={{ fontSize: 22 }}>🧠</div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: DARK }}>AI Copilot — RAG Guidance</div>
          <div style={{ fontSize: 11, color: MUTED }}>Retrieval-Augmented Generation from cloud knowledge base</div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <input
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          placeholder="Describe the problem (optional)"
          style={{ flex: 1, borderRadius: 10, border: "1px solid rgba(16,42,67,0.15)", padding: "9px 12px", fontSize: 13 }}
        />
        <button
          type="button"
          onClick={() => void run()}
          disabled={loading}
          style={{
            background: loading ? "rgba(22,32,42,0.15)" : TEAL,
            color: "white", border: "none", borderRadius: 10,
            padding: "9px 18px", fontSize: 13, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {loading ? "Analysing…" : "Get AI Guidance"}
        </button>
      </div>

      {err && <div style={{ color: "#991B1B", fontSize: 12, marginBottom: 10 }}>{err}</div>}

      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Source + provider badges */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 10, fontWeight: 800, background: "rgba(11,104,115,0.1)", color: TEAL, borderRadius: 6, padding: "4px 8px" }}>
              {sourceLabelMap[result.source] ?? result.source}
            </span>
            <span style={{ fontSize: 10, fontWeight: 800, background: "rgba(99,102,241,0.1)", color: "#6366F1", borderRadius: 6, padding: "4px 8px" }}>
              {providerLabel}
            </span>
            <span style={{ fontSize: 10, fontWeight: 800, background: "rgba(16,42,67,0.06)", color: MUTED, borderRadius: 6, padding: "4px 8px" }}>
              {result.case_count} similar case{result.case_count !== 1 ? "s" : ""} retrieved
            </span>
          </div>

          {/* Guidance text */}
          <div style={{ background: "white", borderRadius: 14, padding: "16px 18px", border: "1px solid rgba(11,104,115,0.12)" }}>
            <div style={{ fontSize: 10, fontWeight: 800, color: TEAL, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>AI Technician Guidance</div>
            <p style={{ margin: 0, fontSize: 14, color: DARK, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{result.guidance}</p>
          </div>

          {/* Similar cases retrieved */}
          {result.past_cases.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: MUTED, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Retrieved similar cases
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {result.past_cases.map((c, i) => (
                  <div key={i} style={{ background: "white", borderRadius: 12, padding: "12px 14px", border: "1px solid rgba(16,42,67,0.08)", display: "flex", gap: 12, alignItems: "flex-start" }}>
                    <div style={{ minWidth: 44, textAlign: "center" }}>
                      <div style={{ fontSize: 13, fontWeight: 800, color: TEAL }}>{c.similarity ? `${(c.similarity * 100).toFixed(0)}%` : "—"}</div>
                      <div style={{ fontSize: 9, color: MUTED, fontWeight: 600 }}>MATCH</div>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: DARK, marginBottom: 3 }}>
                        {formatTitle(c.root_cause || "Unknown cause")}
                      </div>
                      <div style={{ fontSize: 11, color: MUTED, lineHeight: 1.4 }}>{c.resolution_action || c.dispensing_problem || "—"}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* How it works explanation */}
          <details style={{ fontSize: 12, color: MUTED }}>
            <summary style={{ cursor: "pointer", fontWeight: 700, color: TEAL, fontSize: 11 }}>
              How does this work? (Vector similarity calculation)
            </summary>
            <div style={{ marginTop: 10, background: "rgba(16,42,67,0.03)", borderRadius: 10, padding: "12px 14px", lineHeight: 1.6 }}>
              <p style={{ margin: "0 0 8px" }}>
                <strong>1. Embedding</strong> — Your defect description is converted into a 384-dimension mathematical vector
                using the <code>all-MiniLM-L6-v2</code> sentence-transformer model. Each dimension encodes a semantic feature
                of the text.
              </p>
              <p style={{ margin: "0 0 8px" }}>
                <strong>2. Cosine Similarity Search</strong> — The system searches the Supabase <code>failure_logs</code> table
                using the formula: <strong>similarity = 1 − (A · B) / (|A| × |B|)</strong> where A and B are the query and stored
                embedding vectors. A score of 1.0 means identical; 0.0 means unrelated.
              </p>
              <p style={{ margin: "0 0 8px" }}>
                <strong>3. RAG Synthesis</strong> — The top {result.case_count} most similar historical cases are injected as
                context into a Gemini prompt. The AI synthesises a 3-step action plan grounded in real proven fixes rather than
                hallucinated advice.
              </p>
              <p style={{ margin: 0 }}>
                <strong>4. Continuous Learning</strong> — Every new confirmed fix in the Learning Database is automatically
                embedded and synced to Supabase, so future queries benefit from accumulated knowledge.
              </p>
            </div>
          </details>
        </div>
      )}
    </div>
  )
}

// ─── Intelligence proof section ───────────────────────────────────────────────

function IntelligenceProof({ stats, cases }: { stats: LearningStats; cases: LearningCase[] }) {
  const resolved = cases.filter((c) => c.successful_solution)
  const resolutionRate = pct(stats.resolved_count, stats.total_cases)
  const avgCausesPerCase = cases.length ? (cases.reduce((s, c) => s + asList(c.possible_causes).length, 0) / cases.length).toFixed(1) : "0"

  // Trend: how many cases added over time (group by date)
  const byDay: Record<string, number> = {}
  cases.forEach((c) => {
    const day = c.created_at.slice(0, 10)
    byDay[day] = (byDay[day] || 0) + 1
  })
  const trend = Object.entries(byDay).sort(([a], [b]) => a.localeCompare(b)).slice(-7)
  const maxTrend = Math.max(...trend.map(([, v]) => v), 1)

  return (
    <div style={{ ...card, background: "linear-gradient(135deg, rgba(214,106,44,0.04), rgba(99,102,241,0.04))", border: "1.5px solid rgba(214,106,44,0.15)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18 }}>
        <span style={{ fontSize: 20 }}>📊</span>
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: DARK }}>Intelligence Proof</div>
          <div style={{ fontSize: 11, color: MUTED }}>How DARA demonstrates learning capability</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "Resolution Rate", value: `${resolutionRate}%`, sub: `${stats.resolved_count} of ${stats.total_cases} cases`, color: "#10B981" },
          { label: "Avg Causes / Case", value: avgCausesPerCase, sub: "multi-hypothesis reasoning", color: ORANGE },
          { label: "Knowledge Nodes", value: String(stats.total_cases), sub: "cases in learning DB", color: TEAL },
        ].map((m) => (
          <div key={m.label} style={{ background: "white", borderRadius: 14, padding: "14px 16px", border: "1px solid rgba(16,42,67,0.07)", textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 900, color: m.color, lineHeight: 1 }}>{m.value}</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: DARK, marginTop: 4 }}>{m.label}</div>
            <div style={{ fontSize: 10, color: MUTED, marginTop: 2 }}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* Mini trend sparkline */}
      {trend.length > 1 && (
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: MUTED, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>Cases logged (last 7 days)</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 48 }}>
            {trend.map(([day, count]) => (
              <div key={day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                <div style={{ width: "100%", background: TEAL, borderRadius: "4px 4px 0 0", height: `${(count / maxTrend) * 40}px`, opacity: 0.8 }} />
                <span style={{ fontSize: 8, color: MUTED }}>{day.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Resolution showcase */}
      {resolved.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: MUTED, marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Confirmed successful fixes — AI learning signal
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {resolved.slice(0, 3).map((c) => (
              <div key={c.case_id} style={{ background: "white", borderRadius: 12, padding: "10px 14px", border: "1px solid rgba(16,185,129,0.2)", display: "flex", gap: 10, alignItems: "center" }}>
                <div style={{ color: "#10B981", fontSize: 16 }}>✓</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: DARK, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.dispensing_problem}</div>
                  <div style={{ fontSize: 11, color: MUTED }}>Fix: {cleanSolution(c.successful_solution || "")}</div>
                </div>
                <div style={{ fontSize: 10, color: MUTED, flexShrink: 0 }}>{timeAgo(c.updated_at)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function LearningDatabase({
  onBack,
  userEmail,
}: {
  onBack: () => void
  userEmail?: string
}) {
  const [cases, setCases] = useState<LearningCase[]>([])
  const [stats, setStats] = useState<LearningStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)
  const [problem, setProblem] = useState("")
  const [causesText, setCausesText] = useState("")
  const [solutionsText, setSolutionsText] = useState("")
  const [successText, setSuccessText] = useState("")
  const [markingId, setMarkingId] = useState<string | null>(null)
  const [markDraft, setMarkDraft] = useState("")
  const [activeTab, setActiveTab] = useState<"analytics" | "cases" | "copilot" | "add">("analytics")
  const [cloudStatus, setCloudStatus] = useState<{ supabase: { ready: boolean }; embedder: { ready: boolean } } | null>(null)
  const [ragDefect, setRagDefect] = useState("")

  const load = async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchLearning(200)
      setCases(data.cases)
      setStats(data.stats)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load learning database")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    fetchCloudStatus().then(setCloudStatus).catch(() => { })
  }, [])

  const addCase = async () => {
    if (!problem.trim()) { setError("Dispensing problem is required."); return }
    setSaving(true)
    setError("")
    try {
      await createLearningCase({
        dispensing_problem: problem.trim(),
        possible_causes: causesText.split("\n").map((s) => s.trim()).filter(Boolean),
        recommended_solutions: solutionsText.split("\n").map((s) => s.trim()).filter(Boolean),
        successful_solution: successText.trim() || undefined,
        successful_cause: causesText.split("\n").map((s) => s.trim()).filter(Boolean)[0],
        user_email: userEmail,
      })
      setProblem(""); setCausesText(""); setSolutionsText(""); setSuccessText("")
      await load()
      setActiveTab("cases")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save case")
    } finally {
      setSaving(false)
    }
  }

  const confirmSuccess = async (row: LearningCase) => {
    const text = markDraft.trim()
    if (!text) return
    setSaving(true)
    setError("")
    try {
      await markLearningSuccess({
        case_id: row.case_id,
        successful_solution: text,
        successful_cause: asList(row.possible_causes)[0],
      })
      setMarkingId(null)
      setMarkDraft("")
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record successful solution")
    } finally {
      setSaving(false)
    }
  }

  const tabs = [
    { id: "analytics", label: "📈 Analytics", },
    { id: "copilot", label: "🧠 AI Copilot" },
    { id: "cases", label: `📋 Cases (${cases.length})` },
    { id: "add", label: "➕ Add Case" },
  ] as const

  const resolutionRate = stats ? pct(stats.resolved_count, stats.total_cases) : 0

  return (
    <section style={{ minHeight: "100vh", padding: "80px 20px 64px", background: "linear-gradient(160deg, #EAF2F0 0%, #F5F8F7 45%, #EEF2F1 100%)" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>

        {/* Header */}
        <button 
          onClick={onBack} 
          style={{ 
            background: "white", 
            border: "1px solid #E2E8F0", 
            color: "#475569", 
            fontSize: 14, 
            fontWeight: 600, 
            cursor: "pointer", 
            marginBottom: 40,
            padding: "8px 16px",
            borderRadius: 999,
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
            transition: "all 0.2s"
          }}
          onMouseEnter={e => { e.currentTarget.style.background = "#F8FAFC"; e.currentTarget.style.color = "#0B6873" }}
          onMouseLeave={e => { e.currentTarget.style.background = "white"; e.currentTarget.style.color = "#475569" }}
        >
          ← Back to dashboard
        </button>

        <div style={{ ...card, marginBottom: 16, background: `linear-gradient(120deg, ${TEAL}, #0e8f9e)`, border: "none" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
            <div>
              <h1 style={{ margin: "0 0 6px", fontSize: 24, fontWeight: 900, color: "white", letterSpacing: "-0.03em" }}>
                🧬 AI Learning Database
              </h1>
              <p style={{ margin: 0, fontSize: 13, color: "rgba(255,255,255,0.78)", maxWidth: 600, lineHeight: 1.55 }}>
                Every confirmed fix teaches DARA. Case patterns are embedded as 384-dimension vectors, enabling semantic
                similarity search across the cloud knowledge base to generate context-aware technician guidance.
              </p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
              <CloudBadge ready={!!cloudStatus?.supabase?.ready} label={cloudStatus?.supabase?.ready ? "Cloud KB connected" : "Cloud KB offline"} />
              <CloudBadge ready={!!cloudStatus?.embedder?.ready} label={cloudStatus?.embedder?.ready ? "Embedder ready" : "Embedder loading"} />
            </div>
          </div>
        </div>

        {error && <div style={{ marginBottom: 12, padding: "10px 14px", borderRadius: 10, background: "rgba(239,68,68,0.1)", color: "#991B1B", fontSize: 13 }}>{error}</div>}

        {/* KPI row */}
        {stats && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
            {[
              { label: "Cases logged", value: stats.total_cases, icon: "📁", color: TEAL },
              { label: "Confirmed fixes", value: stats.resolved_count, icon: "✅", color: "#10B981" },
              { label: "Resolution rate", value: `${resolutionRate}%`, icon: "🎯", color: ORANGE },
              { label: "Top root cause", value: formatTitle(stats.top_cause), icon: "🔍", color: "#6366F1", small: true },
            ].map((kpi) => (
              <div key={kpi.label} style={{ ...card, textAlign: "center", padding: "18px 14px" }}>
                <div style={{ fontSize: 22, marginBottom: 6 }}>{kpi.icon}</div>
                <div style={{ fontSize: kpi.small ? 13 : 22, fontWeight: 900, color: kpi.color, lineHeight: 1.1, marginBottom: 4 }}>{kpi.value}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: "0.06em" }}>{kpi.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, background: "rgba(255,255,255,0.6)", borderRadius: 14, padding: 4, border: "1px solid rgba(16,42,67,0.08)" }}>
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id)}
              style={{
                flex: 1, border: "none", borderRadius: 10, padding: "9px 14px",
                fontSize: 13, fontWeight: 700, cursor: "pointer", transition: "all 0.2s",
                background: activeTab === t.id ? TEAL : "transparent",
                color: activeTab === t.id ? "white" : MUTED,
                boxShadow: activeTab === t.id ? "0 4px 12px rgba(11,104,115,0.25)" : "none",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Analytics tab ── */}
        {activeTab === "analytics" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>

            <div style={{ ...card, gridColumn: "span 1" }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: DARK, marginBottom: 4 }}>Root Cause Distribution</div>
              <div style={{ fontSize: 11, color: MUTED, marginBottom: 16 }}>How frequently each cause type appears</div>
              {loading ? <div style={{ color: MUTED, fontSize: 13 }}>Loading…</div> : stats?.cause_breakdown.length ? (
                <BarChart data={stats.cause_breakdown} color={TEAL} />
              ) : <div style={{ color: MUTED, fontSize: 13 }}>No data yet</div>}
            </div>

            <div style={{ ...card, display: "flex", flexDirection: "column", alignItems: "center", gridColumn: "span 3" }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: DARK, marginBottom: 4, alignSelf: "flex-start" }}>Cause Share</div>
              <div style={{ fontSize: 11, color: MUTED, marginBottom: 16, alignSelf: "flex-start" }}>Proportional breakdown of all confirmed causes</div>
              {loading ? <div style={{ color: MUTED, fontSize: 13 }}>Loading…</div> : (
                <DonutChart data={stats?.cause_breakdown ?? []} size={150} />
              )}
            </div>

            <div style={{ ...card, gridColumn: "span 1" }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: DARK, marginBottom: 4 }}>Resolution Progress</div>
              <div style={{ fontSize: 11, color: MUTED, marginBottom: 16 }}>Ratio of confirmed fixes to total cases</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {[
                  { label: "Confirmed fixes", count: stats?.resolved_count ?? 0, total: stats?.total_cases ?? 1, color: "#10B981" },
                  { label: "Pending resolution", count: (stats?.total_cases ?? 0) - (stats?.resolved_count ?? 0), total: stats?.total_cases ?? 1, color: ORANGE },
                ].map((row) => (
                  <div key={row.label}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: DARK }}>{row.label}</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: MUTED }}>{row.count} ({pct(row.count, row.total)}%)</span>
                    </div>
                    <div style={{ background: "rgba(16,42,67,0.06)", borderRadius: 8, height: 10 }}>
                      <div style={{ width: `${pct(row.count, row.total)}%`, height: "100%", background: row.color, borderRadius: 8, transition: "width 0.8s ease" }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {stats && (
              <div style={{ gridColumn: "span 3" }}>
                <IntelligenceProof stats={stats} cases={cases} />
              </div>
            )}
          </div>
        )}

        {/* ── AI Copilot tab ── */}
        {activeTab === "copilot" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ ...card, background: "rgba(255,255,255,0.95)" }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: DARK, marginBottom: 4 }}>Select Defect Type for Copilot Analysis</div>
              <div style={{ fontSize: 11, color: MUTED, marginBottom: 12 }}>
                The AI Copilot will search the cloud vector database for similar cases and generate a 3-step action plan.
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {["inconsistent_size", "missing_deposit", "excess_volume", "stringing", "bridging", "missing_dot", "too_little", "under_dispense"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setRagDefect(d)}
                    style={{
                      border: ragDefect === d ? `2px solid ${TEAL}` : "1.5px solid rgba(16,42,67,0.12)",
                      borderRadius: 8, padding: "6px 12px", fontSize: 11, fontWeight: 700,
                      background: ragDefect === d ? `rgba(11,104,115,0.08)` : "white",
                      color: ragDefect === d ? TEAL : MUTED, cursor: "pointer",
                    }}
                  >
                    {formatTitle(d)}
                  </button>
                ))}
              </div>
            </div>

            {ragDefect ? (
              <RagCopilotPanel defectType={ragDefect} defectLabel={formatTitle(ragDefect)} />
            ) : (
              <div style={{ ...card, textAlign: "center", padding: 40, color: MUTED, fontSize: 14 }}>
                Select a defect type above to activate the AI Copilot
              </div>
            )}

            {/* How RAG makes the DB "intelligent" explainer */}
            <div style={{ ...card, background: "rgba(255,255,255,0.95)" }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: DARK, marginBottom: 12 }}>🔬 Why This Makes the Database Intelligent</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[
                  { icon: "🔢", title: "384-D Vector Embeddings", body: "Each case is converted to a 384-dimension numerical vector capturing semantic meaning — not just keywords. Defects with similar context cluster together even if worded differently." },
                  { icon: "📐", title: "Cosine Similarity", body: "Similarity = 1 − (A·B)/(|A||B|). Two embedding vectors at 0° apart = identical concept (1.0); at 90° = unrelated (0.0). This enables fuzzy, intent-aware matching." },
                  { icon: "☁", title: "Cloud-Scale Knowledge", body: "Confirmed fixes sync to Supabase automatically. Over time the DB accumulates institutional knowledge from every engineer, making guidance progressively more accurate." },
                  { icon: "🤖", title: "Grounded Generation", body: "Gemini is prompted with real retrieved cases — not just the question. This 'grounding' eliminates hallucination and ensures advice is backed by actual evidence." },
                ].map((item) => (
                  <div key={item.title} style={{ background: "rgba(16,42,67,0.03)", borderRadius: 12, padding: "14px 16px" }}>
                    <div style={{ fontSize: 20, marginBottom: 6 }}>{item.icon}</div>
                    <div style={{ fontSize: 12, fontWeight: 800, color: DARK, marginBottom: 4 }}>{item.title}</div>
                    <div style={{ fontSize: 11, color: MUTED, lineHeight: 1.55 }}>{item.body}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Cases tab ── */}
        {activeTab === "cases" && (
          <div style={{ ...card, overflowX: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 800, color: DARK }}>Case Library</div>
                <div style={{ fontSize: 11, color: MUTED }}>{cases.length} cases — each feeds the AI learning model</div>
              </div>
              <button type="button" onClick={() => setActiveTab("add")} style={{ background: ORANGE, color: "white", border: "none", borderRadius: 10, padding: "8px 16px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                + Add Case
              </button>
            </div>
            {loading ? (
              <div style={{ color: MUTED, fontSize: 14, padding: 24 }}>Loading cases…</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, tableLayout: "fixed" }}>
                <thead>
                  <tr style={{ color: MUTED, fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                    {["Problem", "Possible Causes", "Recommended Solutions", "Confirmed Fix", ""].map((h, i) => (
                      <th key={i} style={{ padding: "10px 12px", borderBottom: "2px solid rgba(16,42,67,0.08)", fontWeight: 800, textAlign: "left", width: ["24%", "20%", "28%", "20%", "8%"][i] }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {cases.map((row) => {
                    const causes = asList(row.possible_causes)
                    const solutions = asList(row.recommended_solutions)
                    const resolved = !!row.successful_solution
                    return (
                      <tr key={row.case_id} style={{ verticalAlign: "top", transition: "background 0.15s" }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(11,104,115,0.03)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                        <td style={{ padding: "14px 12px", borderBottom: "1px solid rgba(16,42,67,0.06)" }}>
                          <div style={{ fontWeight: 700, color: DARK, lineHeight: 1.4, marginBottom: 4 }}>{row.dispensing_problem}</div>
                          {row.defect_label && (
                            <span style={{ fontSize: 9, fontWeight: 800, color: TEAL, background: "rgba(11,104,115,0.08)", borderRadius: 5, padding: "2px 6px", textTransform: "uppercase" }}>
                              {row.defect_label}
                            </span>
                          )}
                          <div style={{ fontSize: 10, color: MUTED, marginTop: 4 }}>{timeAgo(row.created_at)}</div>
                        </td>
                        <td style={{ padding: "14px 12px", borderBottom: "1px solid rgba(16,42,67,0.06)", color: "#475569" }}>
                          {causes.length ? causes.map((c) => <div key={c} style={{ marginBottom: 4, lineHeight: 1.4 }}>• {formatTitle(c)}</div>) : "—"}
                        </td>
                        <td style={{ padding: "14px 12px", borderBottom: "1px solid rgba(16,42,67,0.06)", color: "#475569" }}>
                          {solutions.length ? solutions.map((s) => <div key={s} style={{ marginBottom: 4, lineHeight: 1.4 }}>• {cleanSolution(s)}</div>) : "—"}
                        </td>
                        <td style={{ padding: "14px 12px", borderBottom: "1px solid rgba(16,42,67,0.06)" }}>
                          {resolved ? (
                            <div>
                              <span style={{ color: "#059669", fontWeight: 700, fontSize: 11 }}>✓ Confirmed</span>
                              <div style={{ fontSize: 11, color: DARK, marginTop: 4, lineHeight: 1.4 }}>{cleanSolution(row.successful_solution!)}</div>
                            </div>
                          ) : markingId === row.case_id ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                              <textarea
                                value={markDraft}
                                onChange={(e) => setMarkDraft(e.target.value)}
                                placeholder="What worked?"
                                rows={2}
                                style={{ borderRadius: 8, border: "1px solid rgba(16,42,67,0.15)", padding: "7px 10px", fontSize: 11, fontFamily: "inherit" }}
                              />
                              <div style={{ display: "flex", gap: 5 }}>
                                <button type="button" onClick={() => void confirmSuccess(row)} style={{ background: TEAL, color: "white", border: "none", borderRadius: 7, padding: "5px 10px", fontSize: 10, fontWeight: 700, cursor: "pointer" }}>Save</button>
                                <button type="button" onClick={() => { setMarkingId(null); setMarkDraft("") }} style={{ background: "transparent", border: "none", color: MUTED, fontSize: 10, cursor: "pointer", fontWeight: 600 }}>Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <button type="button" onClick={() => { setMarkingId(row.case_id); setMarkDraft(cleanSolution(solutions[0] || "")) }}
                              style={{ background: "white", color: TEAL, border: `1px solid rgba(11,104,115,0.3)`, borderRadius: 7, padding: "5px 10px", fontSize: 10, fontWeight: 700, cursor: "pointer" }}>
                              Record fix
                            </button>
                          )}
                        </td>
                        <td style={{ padding: "14px 12px", borderBottom: "1px solid rgba(16,42,67,0.06)", textAlign: "center" }}>
                          <div style={{ fontSize: 16 }}>{resolved ? "🟢" : "🟡"}</div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* ── Add Case tab ── */}
        {activeTab === "add" && (
          <div style={card}>
            <div style={{ fontSize: 14, fontWeight: 800, color: DARK, marginBottom: 4 }}>Log a New Troubleshooting Case</div>
            <p style={{ margin: "0 0 18px", fontSize: 12, color: MUTED }}>
              One item per line for causes and solutions. Confirmed fixes are embedded and synced to the cloud knowledge base automatically.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 6, gridColumn: "1 / -1" }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: DARK, textTransform: "uppercase", letterSpacing: "0.06em" }}>Dispensing problem *</span>
                <textarea value={problem} onChange={(e) => setProblem(e.target.value)} rows={2}
                  placeholder="e.g. Inconsistent volume; first dots after a break are starved"
                  style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: 12, fontSize: 13, fontFamily: "inherit", outline: "none" }} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: DARK, textTransform: "uppercase", letterSpacing: "0.06em" }}>Possible causes</span>
                <textarea value={causesText} onChange={(e) => setCausesText(e.target.value)} rows={4}
                  placeholder={"Air trapped inside the syringe\nNozzle blockage\nIncorrect vacuum parameter"}
                  style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: 12, fontSize: 13, fontFamily: "inherit" }} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: DARK, textTransform: "uppercase", letterSpacing: "0.06em" }}>Recommended solutions</span>
                <textarea value={solutionsText} onChange={(e) => setSolutionsText(e.target.value)} rows={4}
                  placeholder={"Purge the syringe barrel\nClean or replace the nozzle\nAdjust suck-back parameter"}
                  style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: 12, fontSize: 13, fontFamily: "inherit" }} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 6, gridColumn: "1 / -1" }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: DARK, textTransform: "uppercase", letterSpacing: "0.06em" }}>Successful solution (optional)</span>
                <input value={successText} onChange={(e) => setSuccessText(e.target.value)}
                  placeholder="What actually fixed it on the line — this is the AI learning signal"
                  style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: "10px 12px", fontSize: 13 }} />
              </label>
            </div>
            <div style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center" }}>
              <button type="button" onClick={() => void addCase()} disabled={saving}
                style={{ background: saving ? "rgba(22,32,42,0.2)" : ORANGE, color: "white", border: "none", borderRadius: 10, padding: "10px 22px", fontSize: 13, fontWeight: 700, cursor: saving ? "not-allowed" : "pointer" }}>
                {saving ? "Saving…" : "💾 Save to Learning Database"}
              </button>
              <span style={{ fontSize: 11, color: MUTED }}>
                {successText ? "⚡ Will auto-sync to cloud KB as a learning signal" : "Tip: add a confirmed fix to maximise AI learning value"}
              </span>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

// ─── Insight banner (used from CaseWorkspace / diagnosis view) ────────────────

export function LearningInsightBanner({
  insights,
  onRecordSuccess,
  solutions,
  recording,
}: {
  insights: LearningInsights | null
  onRecordSuccess?: (solution: string, cause?: string) => void
  solutions?: { text: string; cause?: string }[]
  recording?: boolean
}) {
  const [picked, setPicked] = useState(solutions?.[0]?.text || "")
  if (!insights?.insight && !onRecordSuccess) return null

  return (
    <div style={{
      background: "rgba(11,104,115,0.06)", borderRadius: 18, padding: 20,
      border: "1.5px solid rgba(11,104,115,0.18)", marginTop: 20,
    }}>
      <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.08em", color: TEAL, textTransform: "uppercase", marginBottom: 8 }}>
        🧠 AI learning from previous cases
      </div>
      {insights?.insight && <p style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600, color: DARK, lineHeight: 1.55 }}>{insights.insight}</p>}
      {insights?.cause_breakdown?.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: onRecordSuccess ? 14 : 0 }}>
          {insights.cause_breakdown.slice(0, 4).map((c) => (
            <span key={c.name} style={{ fontSize: 11, fontWeight: 700, background: "white", border: "1px solid rgba(11,104,115,0.15)", borderRadius: 999, padding: "4px 10px", color: TEAL }}>
              {formatTitle(c.name)}: {c.count}
            </span>
          ))}
        </div>
      ) : null}
      {onRecordSuccess && solutions && solutions.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 8 }}>Which recommended solution actually worked?</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <select value={picked} onChange={(e) => setPicked(e.target.value)}
              style={{ flex: 1, minWidth: 220, borderRadius: 10, border: "1px solid rgba(16,42,67,0.15)", padding: "10px 12px", fontSize: 13 }}>
              {solutions.map((s) => <option key={s.text} value={s.text}>{cleanSolution(s.text)}</option>)}
            </select>
            <button type="button" disabled={recording || !picked}
              onClick={() => { const match = solutions.find((s) => s.text === picked); onRecordSuccess(picked, match?.cause) }}
              style={{ background: recording ? "rgba(22,32,42,0.2)" : TEAL, color: "white", border: "none", borderRadius: 10, padding: "10px 16px", fontSize: 13, fontWeight: 700, cursor: recording ? "not-allowed" : "pointer" }}>
              {recording ? "Saving…" : "Record successful solution"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}