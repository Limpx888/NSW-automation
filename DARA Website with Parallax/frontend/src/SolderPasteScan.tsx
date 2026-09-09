import { useEffect, useRef, useState, type CSSProperties } from "react"
import {
  analyzeImage,
  askQuestion,
  diagnoseWorkflow,
  fetchMeta,
  type ActionStep,
  type AnalyzeResponse,
  type CauseRow,
  type FollowUpQuestion,
} from "@/lib/api"
import { ReportDownloadBar } from "@/CaseWorkspace"

function StarRating({ value }: { value: number }) {
  const stars = [1, 2, 3, 4, 5]
  return (
    <div style={{ display: "flex", gap: 3 }} aria-label={`${value} out of 5`}>
      {stars.map((n) => {
        const fill = Math.max(0, Math.min(1, value - (n - 1)))
        return (
          <span key={n} style={{ position: "relative", width: 18, height: 18, display: "inline-block" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.8 6.7 19.6l1-5.8L3.5 9.7l5.9-.9L12 3.5z"
                fill="#E5E7EB"
                stroke="#D1D5DB"
                strokeWidth="1"
              />
            </svg>
            <span style={{ position: "absolute", inset: 0, width: `${fill * 100}%`, overflow: "hidden" }}>
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path
                  d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.8 6.7 19.6l1-5.8L3.5 9.7l5.9-.9L12 3.5z"
                  fill="#F5B942"
                />
              </svg>
            </span>
          </span>
        )
      })}
    </div>
  )
}

function scoreColor(score: number) {
  if (score >= 85) return "#059669"
  if (score >= 70) return "#0B6873"
  if (score >= 50) return "#D97706"
  return "#DC2626"
}

function likelihoodColor(pct: number) {
  if (pct >= 28) return "#DC2626"
  if (pct >= 18) return "#D97706"
  return "#0B6873"
}

function statusStyle(status: string) {
  if (status === "In progress") return { bg: "rgba(214,106,44,0.12)", color: "#B85320" }
  if (status === "Done") return { bg: "rgba(16,185,129,0.12)", color: "#047857" }
  return { bg: "rgba(16,42,67,0.08)", color: "#4B5563" }
}

const card: CSSProperties = {
  background: "rgba(255,255,255,0.72)",
  borderRadius: 22,
  padding: 18,
  border: "1px solid rgba(16,42,67,0.08)",
  boxShadow: "0 16px 40px rgba(16,42,67,0.06)",
}

export default function SolderPasteScan({ onBack }: { onBack: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [diagnosing, setDiagnosing] = useState(false)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [questions, setQuestions] = useState<FollowUpQuestion[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [causes, setCauses] = useState<CauseRow[]>([])
  const [actionPlan, setActionPlan] = useState<ActionStep[]>([])
  const [error, setError] = useState("")
  const [metaOk, setMetaOk] = useState<boolean | null>(null)
  const [question, setQuestion] = useState("")
  const [chat, setChat] = useState<{ role: "user" | "assistant"; content: string }[]>([])
  const [asking, setAsking] = useState(false)

  useEffect(() => {
    fetchMeta()
      .then(() => setMetaOk(true))
      .catch(() => setMetaOk(false))
  }, [])

  const resetDownstream = () => {
    setAnswers({})
    setCauses([])
    setActionPlan([])
    setChat([])
  }

  const onPick = (picked: File | null) => {
    setError("")
    setResult(null)
    setQuestions([])
    resetDownstream()
    setFile(picked)
    if (picked) setPreview(URL.createObjectURL(picked))
    else setPreview("")
  }

  const runAnalyze = async () => {
    if (!file) {
      setError("Choose an image to analyze (JPEG or PNG).")
      return
    }
    setAnalyzing(true)
    setError("")
    resetDownstream()
    try {
      const data = await analyzeImage(file)
      setResult(data)
      setQuestions(data.followup_questions || [])
      setChat([
        {
          role: "assistant",
          content: `Detected ${data.defect_label}. Answer the 2 follow-ups below for cause ranking — replies are instant (rule-based), no Gemini wait.`,
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed")
    } finally {
      setAnalyzing(false)
    }
  }

  const selectAnswer = (qid: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [qid]: value }))
  }

  const runDiagnose = async () => {
    if (!result) return
    if (!answers.frequency || !answers.recent_change) {
      setError("Answer both follow-up questions before running cause analysis.")
      return
    }
    setDiagnosing(true)
    setError("")
    try {
      const data = await diagnoseWorkflow(result, answers)
      setCauses(data.causes)
      setActionPlan(data.action_plan)
      setResult((prev) =>
        prev
          ? {
              ...prev,
              session_id: data.session_id || prev.session_id,
              causes: data.causes,
              action_plan: data.action_plan,
            }
          : prev,
      )
      const top = data.causes[0]
      setChat((prev) => [
        ...prev,
        {
          role: "assistant",
          content: top
            ? `Cause ranking ready. Top cause: ${top.name} (${top.likelihood_pct.toFixed(0)}%). See the table and action plan below — or ask “what should I check first?”`
            : "Cause ranking ready.",
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diagnosis failed")
    } finally {
      setDiagnosing(false)
    }
  }

  const sendQuestion = async () => {
    const q = question.trim()
    if (!q) return
    setAsking(true)
    setError("")
    const nextHistory = [...chat, { role: "user" as const, content: q }]
    setChat(nextHistory)
    setQuestion("")
    try {
      const context = result ? { ...result, causes, action_plan: actionPlan } : null
      const res = await askQuestion(q, context, nextHistory)
      setChat((prev) => [...prev, { role: "assistant", content: res.answer }])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Q&A failed")
    } finally {
      setAsking(false)
    }
  }

  const annotatedSrc = result
    ? `data:image/jpeg;base64,${result.annotated_image_base64}`
    : preview

  const bothAnswered = Boolean(answers.frequency && answers.recent_change)

  return (
    <section
      style={{
        minHeight: "100vh",
        padding: "96px 28px 64px",
        background:
          "linear-gradient(160deg, rgba(234,242,240,0.95) 0%, rgba(245,248,247,0.98) 40%, #EEF2F1 100%)",
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
            fontWeight: 600,
            cursor: "pointer",
            marginBottom: 20,
            padding: 0,
          }}
        >
          ← Back to dashboard
        </button>

        <div style={{ marginBottom: 28 }}>
          <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#0B6873", marginBottom: 8 }}>
            Solder Paste Scan
          </p>
          <h1
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: "clamp(2rem, 4vw, 2.8rem)",
              fontWeight: 800,
              color: "#102A43",
              margin: "0 0 8px",
              letterSpacing: "-0.02em",
            }}
          >
            Dispensing quality assessment
          </h1>
          <p style={{ margin: 0, color: "rgba(22,32,42,0.6)", fontSize: 15 }}>
            YOLO scan → 2 shop-floor follow-ups → ranked causes + action checklist. Q&A is rule-based for instant replies.
          </p>
          {metaOk === false && (
            <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 10, background: "rgba(245,158,11,0.12)", color: "#92400E", fontSize: 13 }}>
              Backend not reachable on port 8000. Start with <code>npm run backend</code>
            </div>
          )}
          {error && (
            <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 10, background: "rgba(239,68,68,0.1)", color: "#991B1B", fontSize: 13 }}>
              {error}
            </div>
          )}
        </div>

        {/* Top: image result + quality (mockup layout) */}
        <div className="scan-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.35fr) minmax(280px, 0.9fr)", gap: 20, alignItems: "start" }}>
          <div style={card}>
            <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>
              IMAGE RESULT
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.15fr", gap: 14 }}>
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                style={{
                  minHeight: 280,
                  borderRadius: 16,
                  border: "2px dashed rgba(16,42,67,0.22)",
                  background: "rgba(255,255,255,0.65)",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 12,
                  padding: 20,
                }}
              >
                <svg width="42" height="42" viewBox="0 0 24 24" fill="none">
                  <path d="M12 16V4m0 0l-4 4m4-4l4 4" stroke="#6B7280" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M4 16.5V18a2 2 0 002 2h12a2 2 0 002-2v-1.5" stroke="#6B7280" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
                <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.04em", color: "#4B5563", textAlign: "center", lineHeight: 1.4 }}>
                  UPLOAD DEFECT IMAGE
                  <br />
                  (JPEG, PNG, ETC.)
                </span>
                {file && <span style={{ fontSize: 12, color: "#0B6873", fontWeight: 600 }}>{file.name}</span>}
              </button>

              <div style={{ borderRadius: 16, overflow: "hidden", background: "#111827", minHeight: 280, display: "flex", flexDirection: "column" }}>
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {annotatedSrc ? (
                    <img src={annotatedSrc} alt="Dispense analysis" style={{ width: "100%", height: "100%", objectFit: "contain", maxHeight: 320 }} />
                  ) : (
                    <span style={{ color: "rgba(255,255,255,0.35)", fontSize: 13 }}>Preview appears here</span>
                  )}
                </div>
                <div style={{ background: "#0B0F14", color: "white", textAlign: "center", padding: "12px 10px", fontSize: 13, fontWeight: 800, letterSpacing: "0.06em" }}>
                  {result?.defect_label || (file ? "READY TO ANALYZE" : "WAITING FOR IMAGE")}
                </div>
              </div>
            </div>

            <input ref={inputRef} type="file" accept="image/*" hidden onChange={(e) => onPick(e.target.files?.[0] || null)} />

            <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={runAnalyze}
                disabled={!file || analyzing}
                style={{
                  background: !file || analyzing ? "rgba(22,32,42,0.2)" : "#D66A2C",
                  color: "white",
                  border: "none",
                  borderRadius: 999,
                  padding: "12px 22px",
                  fontSize: 14,
                  fontWeight: 700,
                  cursor: !file || analyzing ? "not-allowed" : "pointer",
                }}
              >
                {analyzing ? "Analyzing…" : "Analyze with YOLO"}
              </button>
              <button
                type="button"
                onClick={() => onPick(null)}
                style={{
                  background: "white",
                  color: "#102A43",
                  border: "1px solid rgba(16,42,67,0.15)",
                  borderRadius: 999,
                  padding: "12px 22px",
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Clear
              </button>
            </div>
          </div>

          <div style={card}>
            <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>
              DISPENSING QUALITY ASSESSMENT
            </div>
            <div style={{ background: "white", borderRadius: 16, padding: "22px 20px", border: "1px solid rgba(16,42,67,0.06)" }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#102A43", marginBottom: 8 }}>
                OVERALL QUALITY SCORE:{" "}
                <span style={{ fontSize: 28, fontWeight: 800, color: scoreColor(result?.overall_quality_score ?? 0), marginLeft: 4 }}>
                  {result ? `${result.overall_quality_score}/100` : "—/100"}
                </span>
              </div>
              {[
                ["Shape Consistency", result?.shape_consistency],
                ["Size Consistency", result?.size_consistency],
                ["Dispensing Position", result?.dispensing_position],
                ["Defect Risk", result?.defect_risk],
              ].map(([label, value]) => (
                <div key={String(label)} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid rgba(16,42,67,0.06)" }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#374151" }}>{label}</span>
                  <StarRating value={typeof value === "number" ? value : 0} />
                </div>
              ))}
            </div>
            {result && (
              <div style={{ marginTop: 14, fontSize: 12, color: "rgba(22,32,42,0.55)" }}>
                {result.detections?.length ?? 0} bounding box{(result.detections?.length ?? 0) === 1 ? "" : "es"} · confidence{" "}
                {(((result.confidence ?? (result.vision as any)?.confidence) || 0) * 100).toFixed(0)}%
              </div>
            )}
          </div>
        </div>

        {/* STEP 2: Follow-ups */}
        {result && questions.length > 0 && (
          <div style={{ ...card, marginTop: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 6 }}>
              STEP 2 · INTERACTIVE Q&A
            </div>
            <p style={{ margin: "0 0 16px", fontSize: 14, color: "rgba(22,32,42,0.55)" }}>
              Two shop-floor follow-ups — answers adjust cause likelihoods instantly.
            </p>
            <div style={{ display: "grid", gap: 18 }}>
              {questions.map((q) => (
                <div key={q.id}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#102A43", marginBottom: 10 }}>{q.prompt}</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {q.options.map((opt) => {
                      const selected = answers[q.id] === opt.value
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => selectAnswer(q.id, opt.value)}
                          style={{
                            borderRadius: 999,
                            padding: "10px 16px",
                            fontSize: 13,
                            fontWeight: 600,
                            cursor: "pointer",
                            border: selected ? "2px solid #0B6873" : "1px solid rgba(16,42,67,0.15)",
                            background: selected ? "rgba(11,104,115,0.1)" : "white",
                            color: selected ? "#0B6873" : "#374151",
                          }}
                        >
                          {opt.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void runDiagnose()}
              disabled={!bothAnswered || diagnosing}
              style={{
                marginTop: 18,
                background: !bothAnswered || diagnosing ? "rgba(22,32,42,0.2)" : "#0B6873",
                color: "white",
                border: "none",
                borderRadius: 999,
                padding: "12px 22px",
                fontSize: 14,
                fontWeight: 700,
                cursor: !bothAnswered || diagnosing ? "not-allowed" : "pointer",
              }}
            >
              {diagnosing ? "Scoring…" : "Run cause analysis"}
            </button>
          </div>
        )}

        {/* STEP 4 + 5 */}
        {causes.length > 0 && (
          <div className="scan-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.2fr) minmax(280px, 0.9fr)", gap: 20, marginTop: 20, alignItems: "start" }}>
            <div style={card}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>
                STEP 4 · CAUSE ANALYSIS
              </div>
              <div style={{ overflowX: "auto", background: "white", borderRadius: 14, border: "1px solid rgba(16,42,67,0.08)" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "#102A43", color: "white", textAlign: "left" }}>
                      <th style={{ padding: "12px 14px", fontWeight: 700 }}>Possible Cause</th>
                      <th style={{ padding: "12px 14px", fontWeight: 700, whiteSpace: "nowrap" }}>AI Likelihood Score</th>
                      <th style={{ padding: "12px 14px", fontWeight: 700 }}>Reasoning</th>
                    </tr>
                  </thead>
                  <tbody>
                    {causes.map((row, i) => (
                      <tr key={row.cause_id} style={{ borderTop: "1px solid rgba(16,42,67,0.08)", background: i === 0 ? "rgba(214,106,44,0.06)" : "white" }}>
                        <td style={{ padding: "12px 14px", fontWeight: 700, color: "#102A43" }}>{row.name}</td>
                        <td style={{ padding: "12px 14px" }}>
                          <span style={{ fontWeight: 800, color: likelihoodColor(row.likelihood_pct) }}>{row.likelihood_pct.toFixed(1)}%</span>
                          <div style={{ marginTop: 6, height: 6, borderRadius: 99, background: "#E5E7EB", maxWidth: 120 }}>
                            <div style={{ height: 6, borderRadius: 99, width: `${Math.min(row.likelihood_pct, 100)}%`, background: likelihoodColor(row.likelihood_pct) }} />
                          </div>
                        </td>
                        <td style={{ padding: "12px 14px", color: "rgba(22,32,42,0.7)", lineHeight: 1.45 }}>{row.reasoning}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div style={card}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>
                STEP 5 · TROUBLESHOOTING ACTION PLAN
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {actionPlan.map((step) => {
                  const st = statusStyle(step.status)
                  return (
                    <div
                      key={step.step}
                      style={{
                        background: "white",
                        borderRadius: 14,
                        padding: "12px 14px",
                        border: "1px solid rgba(16,42,67,0.08)",
                        borderLeft: `4px solid ${step.status === "In progress" ? "#D66A2C" : "#0B6873"}`,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", marginBottom: 6 }}>
                        <strong style={{ fontSize: 13, color: "#102A43" }}>
                          Step {step.step}. {step.title}
                        </strong>
                        <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 999, background: st.bg, color: st.color, whiteSpace: "nowrap" }}>
                          {step.status}
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: 12, color: "rgba(22,32,42,0.65)", lineHeight: 1.5 }}>{step.detail}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {result?.session_id && causes.length > 0 && (
          <ReportDownloadBar sessionId={result.session_id} />
        )}

        {/* Fast chat */}
        <div style={{ ...card, marginTop: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 6 }}>
            FAST Q&A · RULE ENGINE
          </div>
          <p style={{ margin: "0 0 12px", fontSize: 13, color: "rgba(22,32,42,0.5)" }}>
            Instant answers (no Gemini latency). Try: “top cause”, “nozzle”, “air bubble”, “what should I check first?”
          </p>
          <div style={{ minHeight: 100, maxHeight: 220, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
            {chat.map((m, i) => (
              <div
                key={`${m.role}-${i}`}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  background: m.role === "user" ? "#0B6873" : "white",
                  color: m.role === "user" ? "white" : "#102A43",
                  border: m.role === "user" ? "none" : "1px solid rgba(16,42,67,0.08)",
                  borderRadius: 14,
                  padding: "10px 14px",
                  fontSize: 14,
                  lineHeight: 1.5,
                  whiteSpace: "pre-wrap",
                }}
              >
                {m.content}
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  void sendQuestion()
                }
              }}
              placeholder="Ask about this defect…"
              style={{ flex: 1, borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: "12px 14px", fontSize: 14, outline: "none" }}
            />
            <button
              type="button"
              onClick={() => void sendQuestion()}
              disabled={asking || !question.trim()}
              style={{
                background: asking || !question.trim() ? "rgba(22,32,42,0.2)" : "#0B6873",
                color: "white",
                border: "none",
                borderRadius: 12,
                padding: "0 20px",
                fontWeight: 700,
                cursor: asking || !question.trim() ? "not-allowed" : "pointer",
              }}
            >
              {asking ? "…" : "Ask"}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
