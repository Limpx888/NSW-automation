import { useEffect, useState, type CSSProperties } from "react"
import {
  createLearningCase,
  fetchLearning,
  markLearningSuccess,
  type LearningCase,
  type LearningInsights,
  type LearningStats,
} from "@/lib/api"

const panel: CSSProperties = {
  background: "rgba(255,255,255,0.85)",
  borderRadius: 22,
  padding: 24,
  border: "1px solid rgba(16,42,67,0.08)",
  boxShadow: "0 16px 40px rgba(16,42,67,0.06)",
}

function asList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => (typeof item === "string" ? item : String((item as { name?: string })?.name || item))).filter(Boolean)
}

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
  }, [])

  const addCase = async () => {
    if (!problem.trim()) {
      setError("Dispensing problem is required.")
      return
    }
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
      setProblem("")
      setCausesText("")
      setSolutionsText("")
      setSuccessText("")
      await load()
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

  const exampleInsight =
    stats && stats.cause_breakdown[0]
      ? `Similar problems occurred ${stats.total_cases} times previously. In ${stats.cause_breakdown[0].count} cases, the main cause was ${stats.cause_breakdown[0].name}.`
      : null

  return (
    <section
      style={{
        minHeight: "100vh",
        padding: "96px 24px 64px",
        background: "linear-gradient(160deg, #EAF2F0 0%, #F5F8F7 45%, #EEF2F1 100%)",
      }}
    >
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
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
          }}
        >
          ← Back to dashboard
        </button>

        <div style={{ ...panel, marginBottom: 20 }}>
          <h1 style={{ margin: "6px 0 8px", fontSize: 26, fontWeight: 800, color: "#102A43", letterSpacing: "-0.03em" }}>
            AI Learning Database
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "rgba(16,42,67,0.62)", maxWidth: 720, lineHeight: 1.6 }}>
            Log dispensing problems, possible causes, recommended fixes, and the solution that actually worked.
            Over time DARA learns from those confirmed cases — the same pattern used in industrial troubleshooting data.
          </p>
        </div>

        {error && (
          <div style={{ marginBottom: 16, padding: "10px 14px", borderRadius: 10, background: "rgba(239,68,68,0.1)", color: "#991B1B", fontSize: 13 }}>
            {error}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 20 }}>
          {[
            { label: "Cases logged", value: stats?.total_cases ?? "—" },
            { label: "Successful fixes recorded", value: stats?.resolved_count ?? "—" },
            { label: "Leading confirmed cause", value: stats?.top_cause || "—" },
          ].map((card) => (
            <div key={card.label} style={panel}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                {card.label}
              </div>
              <div style={{ marginTop: 8, fontSize: 18, fontWeight: 800, color: "#102A43", lineHeight: 1.3 }}>
                {card.value}
              </div>
            </div>
          ))}
        </div>

        {exampleInsight && (
          <div
            style={{
              ...panel,
              marginBottom: 20,
              background: "linear-gradient(135deg, rgba(11,104,115,0.08), rgba(214,106,44,0.08))",
              border: "1px solid rgba(11,104,115,0.2)",
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 800, color: "#0B6873", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
              What the AI learned
            </div>
            <p style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#102A43", lineHeight: 1.55 }}>
              {exampleInsight}
            </p>
          </div>
        )}

        <div style={{ ...panel, marginBottom: 20 }}>
          <h2 style={{ margin: "0 0 6px", fontSize: 16, fontWeight: 800, color: "#102A43" }}>Add a troubleshooting case</h2>
          <p style={{ margin: "0 0 16px", fontSize: 13, color: "rgba(16,42,67,0.55)" }}>
            One item per line for causes and recommended solutions.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 12 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, gridColumn: "1 / -1" }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>Dispensing problem</span>
              <textarea
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
                rows={2}
                placeholder="e.g. Inconsistent volume; first dots after a break are starved"
                style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: 12, fontSize: 14, fontFamily: "inherit" }}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>Possible causes</span>
              <textarea
                value={causesText}
                onChange={(e) => setCausesText(e.target.value)}
                rows={4}
                placeholder={"Air trapped inside the syringe\nNozzle blockage"}
                style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: 12, fontSize: 14, fontFamily: "inherit" }}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>Recommended solutions</span>
              <textarea
                value={solutionsText}
                onChange={(e) => setSolutionsText(e.target.value)}
                rows={4}
                placeholder={"Purge air from the syringe\nClean or replace the nozzle"}
                style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: 12, fontSize: 14, fontFamily: "inherit" }}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, gridColumn: "1 / -1" }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>Successful solution (optional)</span>
              <input
                value={successText}
                onChange={(e) => setSuccessText(e.target.value)}
                placeholder="What actually fixed it on the line"
                style={{ borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: "10px 12px", fontSize: 14 }}
              />
            </label>
          </div>
          <button
            type="button"
            onClick={() => void addCase()}
            disabled={saving}
            style={{
              marginTop: 14,
              background: saving ? "rgba(22,32,42,0.2)" : "#D66A2C",
              color: "white",
              border: "none",
              borderRadius: 999,
              padding: "10px 20px",
              fontSize: 13,
              fontWeight: 700,
              cursor: saving ? "not-allowed" : "pointer",
            }}
          >
            {saving ? "Saving…" : "Save to learning database"}
          </button>
        </div>

        <div style={{ ...panel, overflowX: "auto" }}>
          <h2 style={{ margin: "0 0 14px", fontSize: 16, fontWeight: 800, color: "#102A43" }}>Case library</h2>
          {loading ? (
            <p style={{ margin: 0, fontSize: 14, color: "#64748B" }}>Loading cases…</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "#64748B", fontSize: 11, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                  {["Dispensing problem", "Possible causes", "Recommended solutions", "Successful solution"].map((h) => (
                    <th key={h} style={{ padding: "8px 10px", borderBottom: "1px solid rgba(16,42,67,0.1)", fontWeight: 700 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cases.map((row) => {
                  const causes = asList(row.possible_causes)
                  const solutions = asList(row.recommended_solutions)
                  return (
                    <tr key={row.case_id} style={{ verticalAlign: "top" }}>
                      <td style={{ padding: "12px 10px", borderBottom: "1px solid rgba(16,42,67,0.06)", color: "#102A43", fontWeight: 600, maxWidth: 260 }}>
                        {row.dispensing_problem}
                        {row.defect_label && (
                          <div style={{ marginTop: 4, fontSize: 11, fontWeight: 700, color: "#0B6873" }}>{row.defect_label}</div>
                        )}
                      </td>
                      <td style={{ padding: "12px 10px", borderBottom: "1px solid rgba(16,42,67,0.06)", color: "#475569" }}>
                        {causes.length ? causes.map((c) => <div key={c}>• {c}</div>) : "—"}
                      </td>
                      <td style={{ padding: "12px 10px", borderBottom: "1px solid rgba(16,42,67,0.06)", color: "#475569" }}>
                        {solutions.length ? solutions.map((s) => <div key={s}>• {s}</div>) : "—"}
                      </td>
                      <td style={{ padding: "12px 10px", borderBottom: "1px solid rgba(16,42,67,0.06)", color: "#047857", fontWeight: 600 }}>
                        {row.successful_solution ? (
                          row.successful_solution
                        ) : markingId === row.case_id ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                            <input
                              value={markDraft}
                              onChange={(e) => setMarkDraft(e.target.value)}
                              placeholder="What worked?"
                              style={{ borderRadius: 8, border: "1px solid rgba(16,42,67,0.15)", padding: "6px 8px", fontSize: 12 }}
                            />
                            <div style={{ display: "flex", gap: 6 }}>
                              <button type="button" onClick={() => void confirmSuccess(row)} style={{ background: "#0B6873", color: "white", border: "none", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                                Save
                              </button>
                              <button type="button" onClick={() => { setMarkingId(null); setMarkDraft("") }} style={{ background: "transparent", border: "none", color: "#64748B", fontSize: 11, cursor: "pointer" }}>
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setMarkingId(row.case_id)
                              setMarkDraft(solutions[0] || "")
                            }}
                            style={{ background: "white", color: "#0B6873", border: "1px solid rgba(11,104,115,0.3)", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}
                          >
                            Record what worked
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  )
}

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
    <div
      style={{
        ...panel,
        marginTop: 20,
        background: "rgba(11,104,115,0.06)",
        border: "1px solid rgba(11,104,115,0.18)",
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#0B6873", textTransform: "uppercase", marginBottom: 8 }}>
        AI learning from previous cases
      </div>
      {insights?.insight && (
        <p style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600, color: "#102A43", lineHeight: 1.55 }}>
          {insights.insight}
        </p>
      )}
      {insights?.cause_breakdown?.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: onRecordSuccess ? 14 : 0 }}>
          {insights.cause_breakdown.slice(0, 4).map((c) => (
            <span
              key={c.name}
              style={{
                fontSize: 12,
                fontWeight: 700,
                background: "white",
                border: "1px solid rgba(11,104,115,0.15)",
                borderRadius: 999,
                padding: "4px 10px",
                color: "#0B6873",
              }}
            >
              {c.name}: {c.count}
            </span>
          ))}
        </div>
      ) : null}
      {onRecordSuccess && solutions && solutions.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 8 }}>
            Which recommended solution actually worked?
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <select
              value={picked}
              onChange={(e) => setPicked(e.target.value)}
              style={{ flex: 1, minWidth: 220, borderRadius: 10, border: "1px solid rgba(16,42,67,0.15)", padding: "10px 12px", fontSize: 13 }}
            >
              {solutions.map((s) => (
                <option key={s.text} value={s.text}>
                  {s.text}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={recording || !picked}
              onClick={() => {
                const match = solutions.find((s) => s.text === picked)
                onRecordSuccess(picked, match?.cause)
              }}
              style={{
                background: recording ? "rgba(22,32,42,0.2)" : "#0B6873",
                color: "white",
                border: "none",
                borderRadius: 10,
                padding: "10px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: recording ? "not-allowed" : "pointer",
              }}
            >
              {recording ? "Saving…" : "Record successful solution"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
