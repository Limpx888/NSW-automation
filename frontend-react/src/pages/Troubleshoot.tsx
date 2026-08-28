import { useCallback, useEffect, useMemo, useState, Suspense } from "react";
import { downloadReport, fetchMeta, postDiscover, postSession, sampleUrl } from "../lib/api";
import { DEMO_PRESET, FOLLOWUP_KEYS, pretty } from "../lib/content";

const SKIPPED = "_skipped";

function TroubleshootInner() {
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [currentQ, setCurrentQ] = useState<any>(null);
  const [progress, setProgress] = useState<any>(null);
  const [complete, setComplete] = useState(false);
  const [useLlm, setUseLlm] = useState(false);
  const [trainingMode, setTrainingMode] = useState(false); // Feature 1
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [samples, setSamples] = useState<string[]>([]);
  const [sample, setSample] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [nozzle, setNozzle] = useState(0);
  const [openCause, setOpenCause] = useState<string | null>(null);
  
  // Technician Mode states
  const [resolvedSteps, setResolvedSteps] = useState<Record<string, boolean>>({});
  const [technicianMode, setTechnicianMode] = useState(false); // Feature 4

  const refreshQuestion = useCallback(async (nextAnswers: Record<string, any>, llm = useLlm) => {
    const payload = { ...nextAnswers, use_llm: llm, include_optional: true };
    const res = await postDiscover(payload);
    setComplete(res.complete);
    setCurrentQ(res.next);
    setProgress(res.progress);
    setAnswers(res.answers || nextAnswers);
    return res;
  }, [useLlm]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const m = await fetchMeta();
        if (!cancelled) setSamples(m.samples || []);
      } catch {
        if (!cancelled) setError("API is not running on port 8000.");
      }
      const demo = new URLSearchParams(window.location.search).get("demo") === "1";
      try {
        if (demo) {
          const { sample_image, ...rest } = DEMO_PRESET;
          setSample(sample_image);
          setPreview(sampleUrl(sample_image));
          setOrder(Object.keys(rest));
          await refreshQuestion(rest);
        } else {
          await refreshQuestion({});
        }
      } catch {
        if (!cancelled) setError("Could not start the interview.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const commit = async (qid: string, value: any) => {
    const next = { ...answers, [qid]: value };
    if (["material", "amount", "frequency", "pattern"].includes(qid)) {
      for (const key of FOLLOWUP_KEYS) delete next[key];
      next[SKIPPED] = [];
    }
    const nextOrder = order.includes(qid) ? order : [...order, qid];
    setOrder(nextOrder.filter((id) => id in next || id === qid));
    setResult(null);
    await refreshQuestion(next);
  };

  const skip = async (qid: string) => {
    const skipped = [...(answers[SKIPPED] || [])];
    if (!skipped.includes(qid)) skipped.push(qid);
    const next = { ...answers, [SKIPPED]: skipped };
    await refreshQuestion(next);
  };

  const back = async () => {
    const nextOrder = [...order];
    const last = nextOrder.pop();
    if (!last) return;
    const next = { ...answers };
    delete next[last];
    if (Array.isArray(next[SKIPPED])) {
      next[SKIPPED] = next[SKIPPED].filter((id: string) => id !== last);
    }
    setOrder(nextOrder);
    await refreshQuestion(next);
  };

  const onFile = (picked: File | null) => {
    setFile(picked);
    setSample("");
    if (picked) setPreview(URL.createObjectURL(picked));
    else setPreview("");
  };

  const analyze = async () => {
    setAnalyzing(true);
    setError("");
    try {
      const res = await postSession(answers, file, sample || null);
      setResult(res);
      setOpenCause(res.ranked_causes?.[0]?.id ?? null);
      setResolvedSteps({}); // Reset checklists
    } catch (err: any) {
      setError(err.message || "Analyse failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const pdf = async () => {
    if (!result) return;
    const blob = await downloadReport(result);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "dispense-troubleshooting-report.pdf";
    a.click();
  };

  const history = useMemo(
    () => order.filter((id) => id !== SKIPPED && answers[id] != null),
    [order, answers],
  );

  // Helper for rendering stars
  const renderStars = (pct: number) => {
    const score = Math.round(pct / 20); // 0-5 stars
    return (
      <div style={{ display: 'flex', gap: '2px', justifyContent: 'center' }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={`star ${i <= score ? 'filled' : ''}`}>★</span>
        ))}
      </div>
    );
  };

  return (
    <div>
      <h1>Troubleshoot</h1>
      <p>Upload a photo, then answer like an engineer — the next question depends on what you just said.</p>
      {error && <div className="banner warn">{error}</div>}

      {/* Feature 4: Technician Mode Overlay */}
      {technicianMode && result?.sop_plan && (
        <div className="technician-modal-overlay">
          <div className="technician-modal-content">
            <h2 style={{ fontSize: "2rem", color: "var(--primary)" }}>Live Technician Checklist</h2>
            <p>Take this tablet to the machine and check off the steps as you complete them.</p>
            
            <div style={{ marginTop: "2rem" }}>
              {result.sop_plan.map((step: any, i: number) => {
                const stepNum = step.step_number || step.step || (i + 1);
                const isChecked = !!resolvedSteps[stepNum];
                return (
                  <div key={stepNum} className={`technician-step ${isChecked ? 'checked' : ''}`}>
                    <input 
                      type="checkbox" 
                      className="technician-checkbox"
                      checked={isChecked}
                      onChange={(e) => setResolvedSteps(prev => ({...prev, [stepNum]: e.target.checked}))}
                    />
                    <div>
                      <h4 style={{ color: isChecked ? "var(--text-muted)" : "var(--text-main)" }}>
                        Step {stepNum}: {step.action_title || "Check"}
                      </h4>
                      <p>{step.action_details || step.instruction}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ display: "flex", gap: "1rem", marginTop: "2rem" }}>
              <button 
                className="btn-primary" 
                onClick={() => {
                  setTechnicianMode(false);
                  setResolvedSteps(prev => ({ ...prev, submit: true }));
                }}
              >
                Submit Resolution & Close
              </button>
              <button className="btn-ghost" onClick={() => setTechnicianMode(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bento-grid" style={{ marginTop: "2rem" }}>
        <div className="col-span-6" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          
          <section className="card" style={{ background: "linear-gradient(145deg, rgba(20,20,35,0.7) 0%, rgba(10,10,20,0.9) 100%)", borderTop: "4px solid var(--primary)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
              <div style={{ width: "40px", height: "40px", borderRadius: "50%", background: "rgba(0, 240, 255, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--primary)", fontWeight: "bold", fontSize: "1.2rem" }}>1</div>
              <h2 style={{ margin: 0 }}>Dispense photo</h2>
            </div>
            <label className="drop">
              <input
                type="file"
                accept="image/png,image/jpeg"
                hidden
                onChange={(e) => onFile(e.target.files?.[0] || null)}
              />
              <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>📷</div>
              {file ? <strong>{file.name}</strong> : "Drag & drop or click to upload"}
            </label>
            
            {samples.length > 0 && (
              <div style={{ marginTop: "1.5rem", position: "relative" }}>
                <div style={{ textAlign: "center", color: "var(--text-dark)", fontSize: "0.85rem", marginBottom: "1rem", position: "relative" }}>
                  <span style={{ background: "var(--bg-base)", padding: "0 10px", position: "relative", zIndex: 1 }}>OR</span>
                  <div style={{ position: "absolute", top: "50%", left: 0, right: 0, height: "1px", background: "var(--glass-border)", zIndex: 0 }}></div>
                </div>
                <select
                  className="select"
                  style={{ padding: "1.2rem", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)" }}
                  value={sample}
                  onChange={(e) => {
                    const name = e.target.value;
                    setSample(name);
                    setFile(null);
                    setPreview(name ? sampleUrl(name) : "");
                  }}
                >
                  <option value="">🧪 Pick a synthetic demo image</option>
                  {samples.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {preview && <img src={preview} alt="Dispense" style={{ width: "100%", marginTop: "1rem", borderRadius: "10px" }} />}
          </section>

          <section className="card" style={{ background: "linear-gradient(145deg, rgba(20,20,35,0.7) 0%, rgba(10,10,20,0.9) 100%)", borderTop: "4px solid var(--secondary)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
              <div style={{ width: "40px", height: "40px", borderRadius: "50%", background: "rgba(176, 38, 255, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--secondary)", fontWeight: "bold", fontSize: "1.2rem" }}>2</div>
              <h2 style={{ margin: 0 }}>Guided interview</h2>
            </div>
            
            <div className="chips" style={{ background: "rgba(0,0,0,0.3)", padding: "1rem", borderRadius: "10px", border: "1px solid var(--glass-border)" }}>
              {progress?.dimensions?.map((dim: any) => (
                <span key={dim.id} className={`chip${dim.done ? " done" : ""}`}>
                  {dim.done ? "✓" : "·"} {dim.title}
                </span>
              ))}
            </div>

            {history.length > 0 && (
              <details>
                <summary>Answers so far</summary>
                {history.map((id) => (
                  <p key={id}>
                    <strong>{pretty(id)}:</strong> {pretty(answers[id])}
                  </p>
                ))}
              </details>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", margin: "1rem 0" }}>
              <label className="muted" style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
                Let the LLM pick among follow-ups
              </label>
              
              {/* Feature 1 Toggle */}
              <label className="muted" style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input type="checkbox" checked={trainingMode} onChange={(e) => setTrainingMode(e.target.checked)} />
                <span style={{ color: trainingMode ? 'var(--primary)' : 'inherit', fontWeight: trainingMode ? 600 : 400 }}>
                  Operator Training Mode (Show AI reasoning)
                </span>
              </label>
            </div>

            {currentQ ? (
              <div style={{ background: "rgba(0,0,0,0.2)", padding: "1.5rem", borderRadius: "var(--radius-lg)", border: "1px solid var(--glass-border)", marginTop: "1rem" }}>
                {currentQ.source !== "core" && (
                  <div className="banner info">
                    {currentQ.fuzzy_strength < 0.999
                      ? `Fuzzy follow-up (μ=${Number(currentQ.fuzzy_strength).toFixed(2)}) — symptoms overlap this question.`
                      : "Follow-up — chosen because of your previous answers."}
                  </div>
                )}
                {currentQ.optional && <p className="muted">Optional — skip if you do not know.</p>}
                <h3>{currentQ.prompt}</h3>
                
                {/* Feature 1 Educational Tip */}
                {trainingMode && currentQ.why && (
                  <div className="training-tip">
                    <strong>💡 Educational Tip:</strong> {currentQ.why}
                  </div>
                )}

                <div style={{ marginTop: "1.5rem" }}>
                  {currentQ.options === "number_or_skip" ? (
                    <>
                      <input
                        className="input"
                        type="number"
                        min={0}
                        max={400}
                        value={nozzle}
                        onChange={(e) => setNozzle(Number(e.target.value))}
                        placeholder="Nozzle inner diameter (µm)"
                      />
                      <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                        <button className="btn-primary" onClick={() => (nozzle ? commit(currentQ.id, nozzle) : skip(currentQ.id))}>
                          Save nozzle ID
                        </button>
                        <button className="btn-ghost" onClick={() => skip(currentQ.id)}>
                          Skip
                        </button>
                      </div>
                    </>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      {(currentQ.choices || []).map((choice: any) => (
                        <button key={choice.id} className="choice" onClick={() => commit(currentQ.id, choice.id)}>
                          {choice.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                
                {order.length > 0 && (
                  <button className="btn-ghost" style={{ marginTop: "1rem", width: "100%" }} onClick={back}>
                    Back
                  </button>
                )}
              </div>
            ) : complete ? (
              <div style={{ background: "rgba(0,0,0,0.2)", padding: "1.5rem", borderRadius: "var(--radius-lg)", border: "1px solid var(--glass-border)", marginTop: "1rem" }}>
                <div className="banner ok">Interview complete — review, then Analyse.</div>
                <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                  <button className="btn-ghost" onClick={back} style={{ flex: 1 }}>
                    Back
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      setAnswers({});
                      setOrder([]);
                      setResult(null);
                      refreshQuestion({});
                    }}
                    style={{ flex: 1 }}
                  >
                    Restart interview
                  </button>
                </div>
              </div>
            ) : (
              <p>Loading interview…</p>
            )}
          </section>

          <button className="btn-primary" disabled={!complete || analyzing} onClick={analyze}>
            {analyzing ? "Analysing…" : "Analyse"}
          </button>
          {!complete && <p className="muted" style={{ textAlign: 'center' }}>Answer the required questions to enable Analyse.</p>}
        </div>

        <section className="card col-span-6" style={{ alignSelf: "flex-start", background: "linear-gradient(145deg, rgba(20,20,35,0.7) 0%, rgba(10,10,20,0.9) 100%)", borderTop: "4px solid var(--success)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ width: "40px", height: "40px", borderRadius: "50%", background: "rgba(0, 255, 170, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--success)", fontWeight: "bold", fontSize: "1.2rem" }}>3</div>
            <h2 style={{ margin: 0 }}>Live analysis</h2>
          </div>
          
          {!result ? (
            <p>Complete the interview and click Analyse. Tip: Dashboard → Load demo for the judge scenario.</p>
          ) : (
            <div>
              <div className="bento-grid" style={{ marginBottom: "1.5rem" }}>
                <div className="metric col-span-6">
                  <b style={{ fontSize: "1.2rem" }}>{pretty(result.pattern_specific_name)}</b>
                  <span>Defect</span>
                </div>
                <div className="metric col-span-6">
                  <b style={{ fontSize: "1.2rem" }}>
                    {result.vision ? `${Math.round((result.vision.confidence || 0) * 100)}%` : "n/a"}
                  </b>
                  {/* Visual Star Rating added here */}
                  {result.vision && renderStars((result.vision.confidence || 0) * 100)}
                  <span>Vision Confidence</span>
                </div>
              </div>

              {/* Feature 5: Historical Dashboard */}
              {result.similar?.breakdown && result.similar.breakdown.length > 0 && (
                <div style={{ background: "rgba(0,0,0,0.3)", padding: "1.5rem", borderRadius: "10px", marginBottom: "1.5rem", border: "1px solid var(--glass-border)" }}>
                  <h3 style={{ margin: "0 0 1rem 0", color: "var(--primary)", fontSize: "1.1rem" }}>📊 Historical Case Lookup</h3>
                  <p className="muted" style={{ fontSize: "0.9rem", marginBottom: "1rem" }}>
                    In the last {result.similar.total} similar {pretty(result.defect_class)} cases on {pretty(result.material)}, the confirmed causes were:
                  </p>
                  {result.similar.breakdown.map((row: any) => {
                    const pct = Math.round((row.count / result.similar.total) * 100);
                    return (
                      <div key={row.cause} style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "0.75rem" }}>
                        <div style={{ width: "40px", textAlign: "right", fontWeight: "bold" }}>{pct}%</div>
                        <div style={{ flex: 1, height: "12px", background: "rgba(255,255,255,0.05)", borderRadius: "10px", overflow: "hidden" }}>
                          <div style={{ width: `${pct}%`, height: "100%", background: "linear-gradient(90deg, var(--primary), var(--secondary))" }} />
                        </div>
                        <div style={{ width: "160px", fontSize: "0.9rem" }}>{pretty(row.cause)}</div>
                      </div>
                    );
                  })}
                </div>
              )}

              {result.symptoms?.vision_disagreement && (
                <div className="banner warn">
                  Your symptom answer and the photo classifier disagree. Ranking uses your answers.
                </div>
              )}

              <h3 style={{ marginTop: "1.5rem" }}>AI Likelihood Score</h3>
              <div className="banner info">{result.reasoning_chain || result.explanation}</div>

              {result.ranked_causes?.slice(0, 6).map((cause: any) => (
                <details
                  key={cause.id}
                  open={openCause === cause.id}
                  onToggle={(e) => {
                    if ((e.target as HTMLDetailsElement).open) setOpenCause(cause.id);
                  }}
                >
                  <summary>
                    {cause.likelihood_pct}% · {cause.name}
                  </summary>
                  {cause.match_score != null && <p className="muted">Symptom match: {cause.match_score}</p>}
                  {(cause.evidence || []).map((item: any, i: number) => {
                    const d = item.delta || 0;
                    const mu = item.membership ?? 1;
                    return (
                      <p key={i}>
                        {d > 0 ? `+${d.toFixed(0)}%` : `${d.toFixed(0)}%`} — {item.label}
                        {mu < 0.999 ? ` · μ=${mu.toFixed(2)}` : ""}
                      </p>
                    );
                  })}
                </details>
              ))}

              <h3 style={{ marginTop: "2rem", marginBottom: "0.5rem", color: "var(--primary)" }}>Recommended Action Plan</h3>
              
              {/* Feature 4: Start Technician Mode Button */}
              {result.sop_plan?.length > 0 && (
                <button 
                  className="btn-primary" 
                  style={{ width: "100%", marginBottom: "1.5rem", padding: "1.2rem", background: "var(--bg-gradient-start)", border: "1px solid var(--primary)", color: "var(--primary)" }}
                  onClick={() => setTechnicianMode(true)}
                >
                  📱 Start Live Technician Checklist Mode
                </button>
              )}

              {resolvedSteps.submit && (
                <div className="banner ok" style={{ marginBottom: "1rem", fontWeight: "bold", fontSize: "1.1rem", justifyContent: "center" }}>
                  🎉 Issue Resolution Submitted to Database! Great job.
                </div>
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {(result.sop_plan || result.action_plan)?.map((step: any, i: number) => {
                  const stepNum = step.step_number || step.step || (i + 1);
                  return (
                    <div 
                      key={stepNum} 
                      style={{ 
                        padding: "1.2rem", 
                        background: "rgba(20,20,35,0.5)",
                        borderRadius: "10px",
                        borderLeft: "4px solid var(--glass-border)",
                      }}
                    >
                      <h4 style={{ margin: "0 0 0.5rem 0", color: "var(--text-main)" }}>
                        Step {stepNum}: {step.action_title || "Check"}
                      </h4>
                      <p style={{ marginBottom: "0.5rem", fontSize: "0.95rem" }}>{step.action_details || step.instruction}</p>
                    </div>
                  );
                })}
              </div>

              <button className="btn-ghost" style={{ marginTop: "2rem", width: "100%" }} onClick={pdf}>
                Download PDF report
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default function TroubleshootPage() {
  return (
    <Suspense fallback={<p>Loading Troubleshoot…</p>}>
      <TroubleshootInner />
    </Suspense>
  );
}
