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

const QUIZ_QUESTIONS = [
  {
    title: "What material is being dispensed?",
    options: [
      "Liquid Metal",
      "Solder Paste (All types)",
      "Phosphor",
      "Conductive/non-conductive Adhesive",
      "UV Glue/Adhesive",
      "Titanium dioxide (TiO₂)"
    ]
  },
  {
    title: "Is the dispensing amount too large or too small?",
    options: [
      "Too Large (Excess volume, slumping, or spreading)",
      "Too Small (Insufficient volume or starved dot/line)",
      "Inconsistent (Fluctuating between too large and too small)",
      "Completely Missing (Zero deposit / skipped shot)"
    ]
  },
  {
    title: "Is the defect happening continuously or occasionally?",
    options: [
      "Continuously (Occurs on every single dispensing target)",
      "Occasionally / Intermittently (Occurs randomly across target array)",
      "Progressively (Starts normal, then worsens over runtime)"
    ]
  },
  {
    title: "Has the material, nozzle or process setting recently changed?",
    options: [
      "Yes – New syringe barrel or material batch installed",
      "Yes – Nozzle tip replaced or cleaned",
      "Yes – Pressure, shot timer, or standoff height adjusted",
      "No – Running existing baseline process without recent changes"
    ]
  },
  {
    title: "Is the defect happening at one location or across multiple locations?",
    options: [
      "Single Specific Location (Isolates to one specific pin, pad, or corner)",
      "Multiple Random Locations (Scattered sporadically across the board)",
      "Entire Board / Array (Affects all dispensing locations uniformly)",
      "Perimeter / Edge Locations (Concentrated along board edges or boundaries)"
    ]
  }
];

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
  type FlowStep = "select" | "describe" | "upload" | "quiz" | "results"
  const inputRef = useRef<HTMLInputElement>(null)
  
  const [flowStep, setFlowStep] = useState<FlowStep>("select")
  const [entryType, setEntryType] = useState<"describe" | "upload" | null>(null)
  const [problemDesc, setProblemDesc] = useState("")

  const [quizStep, setQuizStep] = useState(0)
  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({})
  
  const [preview, setPreview] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [diagnosing, setDiagnosing] = useState(false)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  
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
    setCauses([])
    setActionPlan([])
    setChat([])
  }

  const onPick = (picked: File | null) => {
    setError("")
    setResult(null)
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
      setChat([
        {
          role: "assistant",
          content: `Detected ${data.defect_label}.`,
        },
      ])
      // After analyzing image, proceed to quiz
      setFlowStep("quiz")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed")
    } finally {
      setAnalyzing(false)
    }
  }

  const runDiagnose = async (analysisResult: AnalyzeResponse | null, description: string | null) => {
    setDiagnosing(true)
    setError("")
    try {
      const formData = new FormData()
      formData.append('yolo_defect', analysisResult?.defect_class || description || 'inconsistent_size')
      formData.append('material', quizAnswers[0] || '')
      formData.append('amount', quizAnswers[1] || '')
      formData.append('frequency', quizAnswers[2] || '')
      formData.append('recent_change', quizAnswers[3] || '')
      formData.append('location', quizAnswers[4] || '')

      const res = await fetch('http://localhost:8000/api/diagnose', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      
      const newCauses = data.cause_table.map((c: any) => ({
        cause_id: c.cause,
        name: c.cause,
        likelihood_pct: c.score_num,
        reasoning: c.reasoning
      }))
      const newActionPlan = data.action_plan.map((a: any) => ({
        step: a.step,
        title: a.cause,
        detail: a.action,
        status: a.status,
        related_cause: a.cause
      }))
      
      setCauses(newCauses)
      setActionPlan(newActionPlan)
      
      const top = newCauses[0]
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

  // Trigger diagnosis automatically when quiz completes
  useEffect(() => {
    if (quizStep >= QUIZ_QUESTIONS.length && flowStep === "quiz") {
      setFlowStep("results")
      void runDiagnose(result, entryType === "describe" ? problemDesc : null)
    }
  }, [quizStep, flowStep])

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


  // Render Select Screen
  if (flowStep === "select") {
    return (
      <section style={{ minHeight: "100vh", padding: "80px 20px", display: "flex", justifyContent: "center", background: "#F5F8FA" }}>
        <div style={{ width: "100%", maxWidth: 640 }}>
          <button onClick={onBack} style={{ background: "none", border: "none", color: "#0B6873", fontSize: 14, fontWeight: 600, cursor: "pointer", marginBottom: 30 }}>
            ← Back to dashboard
          </button>
          <h2 style={{ textAlign: "center", fontSize: 28, fontWeight: 800, color: "#102A43", marginBottom: 40 }}>
            How would you like to provide the defect information?
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <button
              onClick={() => { setEntryType("upload"); setFlowStep("upload") }}
              style={{ padding: "30px", borderRadius: 24, border: "2px solid #E5E7EB", background: "white", cursor: "pointer", display: "flex", alignItems: "center", gap: 20, transition: "all 0.2s" }}
            >
              <div style={{ width: 60, height: 60, borderRadius: "50%", background: "rgba(11,104,115,0.1)", display: "flex", alignItems: "center", justifyContent: "center", color: "#0B6873" }}>
                <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div style={{ textAlign: "left" }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#102A43", marginBottom: 6 }}>Upload a Photo</div>
                <div style={{ fontSize: 14, color: "#6B7280" }}>Let the YOLO vision model detect the defect automatically.</div>
              </div>
            </button>
            
            <button
              onClick={() => { setEntryType("describe"); setFlowStep("describe") }}
              style={{ padding: "30px", borderRadius: 24, border: "2px solid #E5E7EB", background: "white", cursor: "pointer", display: "flex", alignItems: "center", gap: 20, transition: "all 0.2s" }}
            >
              <div style={{ width: 60, height: 60, borderRadius: "50%", background: "rgba(214,106,44,0.1)", display: "flex", alignItems: "center", justifyContent: "center", color: "#D66A2C" }}>
                <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </div>
              <div style={{ textAlign: "left" }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#102A43", marginBottom: 6 }}>Describe the Problem</div>
                <div style={{ fontSize: 14, color: "#6B7280" }}>Manually describe the issue if you don't have a clear photo.</div>
              </div>
            </button>
          </div>
        </div>
      </section>
    )
  }

  // Render Describe Input Screen
  if (flowStep === "describe") {
    return (
      <section style={{ minHeight: "100vh", padding: "80px 20px", display: "flex", justifyContent: "center", background: "#F5F8FA" }}>
        <div style={{ width: "100%", maxWidth: 640 }}>
          <button onClick={() => setFlowStep("select")} style={{ background: "none", border: "none", color: "#0B6873", fontSize: 14, fontWeight: 600, cursor: "pointer", marginBottom: 30 }}>
            ← Back
          </button>
          <div style={{ background: "white", borderRadius: 24, padding: "32px", boxShadow: "0 10px 40px rgba(0,0,0,0.05)" }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: "#102A43", marginBottom: 8 }}>Describe the Defect</h2>
            <p style={{ color: "#6B7280", fontSize: 14, marginBottom: 24 }}>What specific problem are you observing with the dispensing?</p>
            <textarea 
              value={problemDesc}
              onChange={e => setProblemDesc(e.target.value)}
              placeholder="e.g., Slumping paste, missing dots, excess volume..."
              style={{ width: "100%", minHeight: 140, padding: 16, borderRadius: 12, border: "1px solid #E5E7EB", fontSize: 15, fontFamily: "inherit", resize: "vertical", outline: "none", marginBottom: 24 }}
            />
            <button
              onClick={() => {
                if (!problemDesc.trim()) { setError("Please provide a description"); return; }
                setError(""); setFlowStep("quiz")
              }}
              style={{ width: "100%", padding: "16px", borderRadius: 12, background: "#0B6873", color: "white", fontSize: 16, fontWeight: 700, border: "none", cursor: "pointer" }}
            >
              Next Step
            </button>
            {error && <div style={{ marginTop: 12, color: "#DC2626", fontSize: 14, textAlign: "center" }}>{error}</div>}
          </div>
        </div>
      </section>
    )
  }

  // Render Quiz Screen
  if (flowStep === "quiz" && quizStep < QUIZ_QUESTIONS.length) {
    const currentQ = QUIZ_QUESTIONS[quizStep];
    return (
      <section style={{ minHeight: "100vh", padding: "40px 20px", display: "flex", justifyContent: "center", background: "#F5F8FA" }}>
        <div style={{ width: "100%", maxWidth: 600, background: "white", borderRadius: 24, padding: "32px", boxShadow: "0 10px 40px rgba(0,0,0,0.05)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 40 }}>
            <span style={{ fontWeight: 700, color: "#1F2937", fontSize: 16 }}>{quizStep + 1}/{QUIZ_QUESTIONS.length}</span>
            <div style={{ flex: 1, height: 8, background: "#E5E7EB", borderRadius: 999, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${((quizStep + 1) / QUIZ_QUESTIONS.length) * 100}%`, background: "#93C5FD", borderRadius: 999, transition: "width 0.3s ease" }} />
            </div>
            <button onClick={() => setFlowStep(entryType === "upload" ? "upload" : "describe")} style={{ width: 36, height: 36, borderRadius: "50%", background: "#F3F4F6", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M1 1L13 13M1 13L13 1" stroke="#4B5563" strokeWidth="2" strokeLinecap="round"/></svg>
            </button>
          </div>
          
          <h2 style={{ textAlign: "center", fontSize: 24, fontWeight: 700, color: "#1E3A8A", marginBottom: 32, lineHeight: 1.4 }}>
            {currentQ.title}
          </h2>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {currentQ.options.map((opt) => {
              const selected = quizAnswers[quizStep] === opt;
              return (
                <button
                  key={opt}
                  onClick={() => {
                    setQuizAnswers(prev => ({ ...prev, [quizStep]: opt }));
                    setTimeout(() => setQuizStep(s => s + 1), 300);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    padding: "16px 20px",
                    borderRadius: 16,
                    border: selected ? "2px solid #93C5FD" : "1px solid #E5E7EB",
                    background: selected ? "#EFF6FF" : "white",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.2s ease"
                  }}
                >
                  <div style={{
                    width: 24, height: 24, borderRadius: "50%",
                    border: selected ? "6px solid #93C5FD" : "2px solid #93C5FD",
                    background: "white",
                    flexShrink: 0
                  }} />
                  <span style={{ fontSize: 16, fontWeight: 600, color: "#1F2937", lineHeight: 1.4 }}>{opt}</span>
                </button>
              )
            })}
          </div>
        </div>
      </section>
    );
  }

  // Render Upload or Results Screen
  return (
    <section
      style={{
        minHeight: "100vh",
        padding: "96px 28px 64px",
        background: "linear-gradient(160deg, rgba(234,242,240,0.95) 0%, rgba(245,248,247,0.98) 40%, #EEF2F1 100%)",
      }}
    >
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => {
            if (flowStep === 'results' && entryType === 'upload') setFlowStep('upload')
            else if (flowStep === 'results' && entryType === 'describe') setFlowStep('describe')
            else setFlowStep('select')
          }}
          style={{ background: "none", border: "none", color: "#0B6873", fontSize: 13, fontWeight: 600, cursor: "pointer", marginBottom: 20, padding: 0 }}
        >
          ← {flowStep === 'results' ? 'Back to editing' : 'Back to selection'}
        </button>

        <div style={{ marginBottom: 28 }}>
          <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#0B6873", marginBottom: 8 }}>
            Solder Paste Scan
          </p>
          <h1 style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "clamp(2rem, 4vw, 2.8rem)", fontWeight: 800, color: "#102A43", margin: "0 0 8px", letterSpacing: "-0.02em" }}>
            Dispensing quality assessment
          </h1>
          <p style={{ margin: 0, color: "rgba(22,32,42,0.6)", fontSize: 15 }}>
            Analyze defects + answer follow-ups → ranked causes + action checklist.
          </p>
          {error && (
            <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 10, background: "rgba(239,68,68,0.1)", color: "#991B1B", fontSize: 13 }}>
              {error}
            </div>
          )}
        </div>

        {/* Show Image Analysis cards ONLY if they chose upload */}
        {entryType === "upload" && (flowStep === "upload" || flowStep === "results") && (
          <div className="scan-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.35fr) minmax(280px, 0.9fr)", gap: 20, alignItems: "start" }}>
            <div style={card}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>IMAGE RESULT</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1.15fr", gap: 14 }}>
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  style={{ minHeight: 280, borderRadius: 16, border: "2px dashed rgba(16,42,67,0.22)", background: "rgba(255,255,255,0.65)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: 20 }}
                >
                  <svg width="42" height="42" viewBox="0 0 24 24" fill="none">
                    <path d="M12 16V4m0 0l-4 4m4-4l4 4" stroke="#6B7280" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M4 16.5V18a2 2 0 002 2h12a2 2 0 002-2v-1.5" stroke="#6B7280" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                  <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.04em", color: "#4B5563", textAlign: "center", lineHeight: 1.4 }}>
                    UPLOAD DEFECT IMAGE<br />(JPEG, PNG, ETC.)
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

              {flowStep === "upload" && (
                <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
                  <button
                    type="button"
                    onClick={runAnalyze}
                    disabled={!file || analyzing}
                    style={{ background: !file || analyzing ? "rgba(22,32,42,0.2)" : "#D66A2C", color: "white", border: "none", borderRadius: 999, padding: "12px 22px", fontSize: 14, fontWeight: 700, cursor: !file || analyzing ? "not-allowed" : "pointer" }}
                  >
                    {analyzing ? "Analyzing…" : "Analyze with YOLO"}
                  </button>
                  <button
                    type="button"
                    onClick={() => onPick(null)}
                    style={{ background: "white", color: "#102A43", border: "1px solid rgba(16,42,67,0.15)", borderRadius: 999, padding: "12px 22px", fontSize: 14, fontWeight: 600, cursor: "pointer" }}
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>

            <div style={card}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>DISPENSING QUALITY ASSESSMENT</div>
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
                  {result.detections?.length ?? 0} bounding box{(result.detections?.length ?? 0) === 1 ? "" : "es"} · confidence {(((result.confidence ?? (result.vision as any)?.confidence) || 0) * 100).toFixed(0)}%
                </div>
              )}
            </div>
          </div>
        )}

        {/* Show Problem Description Summary if they chose describe and are in results */}
        {entryType === "describe" && flowStep === "results" && (
          <div style={{ ...card, marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>PROBLEM DESCRIPTION</div>
            <div style={{ background: "white", borderRadius: 16, padding: "20px", border: "1px solid rgba(16,42,67,0.08)", fontSize: 15, color: "#374151", lineHeight: 1.5 }}>
              {problemDesc}
            </div>
          </div>
        )}

        {/* Results Sections */}
        {flowStep === "results" && causes.length > 0 && (
          <>
            <div className="scan-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.2fr) minmax(280px, 0.9fr)", gap: 20, marginTop: 20, alignItems: "start" }}>
              <div style={card}>
                <div style={{ fontSize: 16, color: "#000", marginBottom: 14 }}>
                  Possible Causes:
                </div>
                <ul style={{ margin: 0, paddingLeft: 24, display: "flex", flexDirection: "column", gap: 10, fontSize: 15, color: "#000", lineHeight: 1.5 }}>
                  {causes.map((row) => (
                    <li key={row.cause_id}>
                      <strong>{row.name}:</strong> {row.reasoning}
                    </li>
                  ))}
                </ul>
              </div>

              <div style={card}>
                <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 14 }}>TROUBLESHOOTING ACTION PLAN</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {actionPlan.map((step) => {
                    const st = statusStyle(step.status)
                    return (
                      <div key={step.step} style={{ background: "white", borderRadius: 14, padding: "12px 14px", border: "1px solid rgba(16,42,67,0.08)", borderLeft: `4px solid ${step.status === "In progress" ? "#D66A2C" : "#0B6873"}` }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", marginBottom: 6 }}>
                          <strong style={{ fontSize: 13, color: "#102A43" }}>Step {step.step}. {step.title}</strong>
                          <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 999, background: st.bg, color: st.color, whiteSpace: "nowrap" }}>{step.status}</span>
                        </div>
                        <p style={{ margin: 0, fontSize: 12, color: "rgba(22,32,42,0.65)", lineHeight: 1.5 }}>{step.detail}</p>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Fast chat */}
            <div style={{ ...card, marginTop: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#102A43", marginBottom: 6 }}>FAST Q&A · RULE ENGINE</div>
              <p style={{ margin: "0 0 12px", fontSize: 13, color: "rgba(22,32,42,0.5)" }}>
                Instant answers (no Gemini latency). Try: “top cause”, “nozzle”, “air bubble”, “what should I check first?”
              </p>
              <div style={{ minHeight: 100, maxHeight: 220, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
                {chat.map((m, i) => (
                  <div key={`${m.role}-${i}`} style={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", maxWidth: "85%", background: m.role === "user" ? "#0B6873" : "white", color: m.role === "user" ? "white" : "#102A43", border: m.role === "user" ? "none" : "1px solid rgba(16,42,67,0.08)", borderRadius: 14, padding: "10px 14px", fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                    {m.content}
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendQuestion() } }}
                  placeholder="Ask about this defect…"
                  style={{ flex: 1, borderRadius: 12, border: "1px solid rgba(16,42,67,0.15)", padding: "12px 14px", fontSize: 14, outline: "none" }}
                />
                <button
                  type="button"
                  onClick={() => void sendQuestion()}
                  disabled={asking || !question.trim()}
                  style={{ background: asking || !question.trim() ? "rgba(22,32,42,0.2)" : "#0B6873", color: "white", border: "none", borderRadius: 12, padding: "0 20px", fontWeight: 700, cursor: asking || !question.trim() ? "not-allowed" : "pointer" }}
                >
                  {asking ? "…" : "Ask"}
                </button>
              </div>
            </div>
            
            {result?.session_id && causes.length > 0 && entryType === "upload" && (
              <div style={{ marginTop: 20 }}>
                <ReportDownloadBar sessionId={result.session_id} />
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}

