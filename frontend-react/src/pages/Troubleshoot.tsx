import { useCallback, useEffect, useMemo, useState, Suspense } from "react";
import { downloadReport, fetchMeta, postCounterTestVerify, postDiscover, postSession, sampleUrl } from "../lib/api";
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
  
  // Environmental & Rheology parameters
  const [ambientTemp, setAmbientTemp] = useState<number>(23.0);
  const [potLife, setPotLife] = useState<number>(0.5);

  // Hypothesis-Testing & Counter-Test Loop states
  const [currentTest, setCurrentTest] = useState<any>(null);
  const [eliminationPathway, setEliminationPathway] = useState<any[]>([]);
  const [historyStack, setHistoryStack] = useState<any[]>([]);
  const [isResolved, setIsResolved] = useState(false);
  const [confirmedCause, setConfirmedCause] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [initialCausesBackup, setInitialCausesBackup] = useState<any[]>([]);

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
      const sessionPayload = {
        ...answers,
        ambient_temp_c: ambientTemp,
        pot_life_hours: potLife,
      };
      const res = await postSession(sessionPayload, file, sample || null);
      setResult(res);
      setOpenCause(res.ranked_causes?.[0]?.id ?? null);
      
      // Initialize Counter-Test Loop
      setEliminationPathway([]);
      setHistoryStack([]);
      setIsResolved(false);
      setConfirmedCause(null);
      setCurrentTest(res.initial_test || null);
      setInitialCausesBackup(res.ranked_causes ? JSON.parse(JSON.stringify(res.ranked_causes)) : []);
    } catch (err: any) {
      setError(err.message || "Analyse failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCounterTestFeedback = async (feedback: "resolved" | "unresolved" | "shifted") => {
    if (!currentTest || !result || verifying) return;
    setVerifying(true);
    try {
      // Push state snapshot for 1-Click Undo
      const snapshot = {
        ranked_causes: JSON.parse(JSON.stringify(result.ranked_causes || [])),
        currentTest: { ...currentTest },
        eliminationPathway: [...eliminationPathway],
        isResolved,
        confirmedCause,
        openCause,
      };
      setHistoryStack((prev) => [...prev, snapshot]);

      const res = await postCounterTestVerify({
        current_causes: result.ranked_causes,
        test_id: currentTest.action_id,
        feedback,
        test_history: eliminationPathway,
        session_id: result.session_id,
      });

      setResult((prev: any) => ({
        ...prev,
        ranked_causes: res.ranked_causes,
        confirmed_cause: res.confirmed_cause,
        elimination_pathway: res.elimination_pathway,
      }));

      setEliminationPathway(res.elimination_pathway || []);
      setCurrentTest(res.next_test || null);
      setIsResolved(Boolean(res.resolved));
      setConfirmedCause(res.confirmed_cause || null);
      if (res.ranked_causes?.[0]?.id) {
        setOpenCause(res.ranked_causes[0].id);
      }
    } catch (err: any) {
      setError(err.message || "Verification step failed");
    } finally {
      setVerifying(false);
    }
  };

  const handleUndoStep = () => {
    if (historyStack.length === 0 || !result) return;
    const prevSnapshot = historyStack[historyStack.length - 1];
    setHistoryStack((prev) => prev.slice(0, -1));

    setResult((prev: any) => ({
      ...prev,
      ranked_causes: prevSnapshot.ranked_causes,
      confirmed_cause: prevSnapshot.confirmedCause,
      elimination_pathway: prevSnapshot.eliminationPathway,
    }));
    setCurrentTest(prevSnapshot.currentTest);
    setEliminationPathway(prevSnapshot.eliminationPathway);
    setIsResolved(prevSnapshot.isResolved);
    setConfirmedCause(prevSnapshot.confirmedCause);
    setOpenCause(prevSnapshot.openCause);
  };

  const handleResetDiagnosticLoop = () => {
    if (!result || initialCausesBackup.length === 0) return;
    setResult((prev: any) => ({
      ...prev,
      ranked_causes: JSON.parse(JSON.stringify(initialCausesBackup)),
      confirmed_cause: null,
      elimination_pathway: [],
    }));
    setEliminationPathway([]);
    setHistoryStack([]);
    setIsResolved(false);
    setConfirmedCause(null);
    setCurrentTest(result.initial_test || null);
    setOpenCause(initialCausesBackup[0]?.id || null);
  };

  const pdf = async () => {
    if (!result) return;
    const sessionPayload = {
      ...result,
      confirmed_cause: confirmedCause || result.confirmed_cause,
      elimination_pathway: eliminationPathway.length > 0 ? eliminationPathway : result.elimination_pathway,
    };
    const blob = await downloadReport(sessionPayload);
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

  // Helper for rendering stars horizontally
  const renderStars = (pct: number) => {
    const score = Math.round(pct / 20); // 0-5 stars
    return (
      <div style={{ display: 'inline-flex', flexDirection: 'row', gap: '4px', justifyContent: 'center', alignItems: 'center', margin: '4px auto' }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={`star ${i <= score ? 'filled' : ''}`} style={{ display: 'inline-block', lineHeight: 1 }}>★</span>
        ))}
      </div>
    );
  };

  return (
    <div>
      <h1>Troubleshoot</h1>
      <p>Upload a photo, then answer like an engineer — the next question depends on what you just said.</p>
      {error && <div className="banner warn">{error}</div>}

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

          {/* Environmental & Fluid Lifetime Controls */}
          <section className="env-control-card">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span style={{ fontSize: "1.2rem" }}>🌡️</span>
                <h3 style={{ margin: 0, fontSize: "1.05rem", color: "var(--primary)" }}>Workshop Environment & Rheology</h3>
              </div>
              <span className="muted" style={{ fontSize: "0.8rem" }}>Physics-Based Input</span>
            </div>

            {/* Ambient Temperature Slider & Controls */}
            <div className="env-slider-group">
              <div className="env-slider-header">
                <label style={{ fontSize: "0.88rem", fontWeight: 600 }}>
                  Ambient Temperature: <span style={{ color: ambientTemp !== 23.0 ? (ambientTemp > 23.0 ? "var(--warning)" : "var(--primary)") : "var(--success)", fontWeight: 800 }}>{ambientTemp.toFixed(1)}°C</span>
                  {ambientTemp !== 23.0 && (
                    <span className="muted" style={{ fontSize: "0.8rem", marginLeft: "0.5rem" }}>
                      ({ambientTemp > 23.0 ? `+${(ambientTemp - 23.0).toFixed(1)}` : (ambientTemp - 23.0).toFixed(1)}°C drift)
                    </span>
                  )}
                </label>
              </div>
              <input
                type="range"
                min="10.0"
                max="45.0"
                step="0.5"
                value={ambientTemp}
                onChange={(e) => setAmbientTemp(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "var(--primary)", cursor: "pointer" }}
              />
              <div className="env-slider-presets">
                {[
                  { label: "❄️ Cold (18°C)", val: 18.0 },
                  { label: "🟢 Nominal (23°C)", val: 23.0 },
                  { label: "🔥 Warm (26.5°C)", val: 26.5 },
                  { label: "🌡️ Peak (30°C)", val: 30.0 },
                ].map((p) => (
                  <button
                    key={p.val}
                    type="button"
                    className={`env-preset-btn ${ambientTemp === p.val ? "active" : ""}`}
                    onClick={() => setAmbientTemp(p.val)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Syringe Pot Life / Open Hours */}
            <div className="env-slider-group" style={{ marginBottom: 0 }}>
              <div className="env-slider-header">
                <label style={{ fontSize: "0.88rem", fontWeight: 600 }}>
                  Syringe Pot Life (Hours): <span style={{ color: potLife > 6.0 ? "var(--warning)" : "var(--text-main)", fontWeight: 800 }}>{potLife.toFixed(1)}h</span>
                  {potLife > 6.0 && (
                    <span style={{ fontSize: "0.78rem", color: "var(--warning)", marginLeft: "0.5rem", fontWeight: 700 }}>
                      ⚠️ &gt;6h Thixotropic Alert
                    </span>
                  )}
                </label>
              </div>
              <input
                type="range"
                min="0.0"
                max="24.0"
                step="0.5"
                value={potLife}
                onChange={(e) => setPotLife(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "var(--secondary)", cursor: "pointer" }}
              />
              <div className="env-slider-presets">
                {[
                  { label: "⏱️ Fresh (0.5h)", val: 0.5 },
                  { label: "⏱️ 3.0h", val: 3.0 },
                  { label: "⚠️ Aged (8.0h)", val: 8.0 },
                ].map((p) => (
                  <button
                    key={p.val}
                    type="button"
                    className={`env-preset-btn ${potLife === p.val ? "active" : ""}`}
                    onClick={() => setPotLife(p.val)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
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

              {/* INNOVATIVE FEATURE: Physics-Based Rheology & Thermal Offset Calculator */}
              {result.rheology && (
                <div className="rheology-card">
                  <div className="rheology-header">
                    <div className="rheology-title">
                      <span style={{ fontSize: "1.35rem" }}>🌡️</span>
                      <div>
                        <h3 style={{ margin: 0, fontSize: "1.1rem", color: "var(--primary)" }}>
                          Physics Rheology & Thermal Offset
                        </h3>
                        <span className="muted" style={{ fontSize: "0.8rem" }}>
                          Arrhenius Viscosity Model & Poiseuille Flow Compensation
                        </span>
                      </div>
                    </div>
                    <span className={`rheology-status-badge ${result.rheology.risk_level.toLowerCase()}`}>
                      {result.rheology.risk_level === "OPTIMAL"
                        ? "🟢 Optimal Nominal"
                        : result.rheology.risk_level === "MODERATE_DRIFT"
                        ? "🟡 Moderate Thermal Drift"
                        : "🔴 High Thermal Drift"}
                    </span>
                  </div>

                  {result.rheology.is_clamped && (
                    <div className="safety-guard-pill">
                      🛡️ Safety Boundary Guard: Input values safely clamped to factory operating window (10°C–45°C, ±30% max offset).
                    </div>
                  )}

                  {/* Rheology Quantitative Metrics */}
                  <div className="rheology-grid">
                    <div className="rheology-stat-box">
                      <span className="rheology-stat-label">Workshop Temp</span>
                      <div className="rheology-stat-val">
                        {result.rheology.ambient_temp_c}°C
                      </div>
                      <span className="rheology-stat-sub">
                        {result.rheology.delta_t_c >= 0 ? `+${result.rheology.delta_t_c}` : result.rheology.delta_t_c}°C vs 23°C baseline
                      </span>
                    </div>

                    <div className="rheology-stat-box">
                      <span className="rheology-stat-label">Viscosity Drift (Δη)</span>
                      <div
                        className="rheology-stat-val"
                        style={{
                          color:
                            result.rheology.viscosity_drift_pct < -5
                              ? "var(--danger)"
                              : result.rheology.viscosity_drift_pct > 5
                              ? "var(--warning)"
                              : "var(--success)",
                        }}
                      >
                        {result.rheology.viscosity_drift_pct >= 0 ? `+${result.rheology.viscosity_drift_pct}` : result.rheology.viscosity_drift_pct}%
                      </div>
                      <span className="rheology-stat-sub">
                        Ratio: {result.rheology.viscosity_ratio}x ({result.rheology.viscosity_drift_pct < 0 ? "Fluid thinned" : result.rheology.viscosity_drift_pct > 0 ? "Fluid thickened" : "Nominal"})
                      </span>
                    </div>

                    <div className="rheology-stat-box">
                      <span className="rheology-stat-label">Pressure Offset (ΔP)</span>
                      <div className="rheology-stat-val" style={{ color: "var(--primary)" }}>
                        {result.rheology.pressure_offset_mpa >= 0 ? `+${result.rheology.pressure_offset_mpa}` : result.rheology.pressure_offset_mpa} MPa
                      </div>
                      <span className="rheology-stat-sub">
                        {result.rheology.pressure_offset_pct >= 0 ? `+${result.rheology.pressure_offset_pct}` : result.rheology.pressure_offset_pct}% pneumatic compensation
                      </span>
                    </div>

                    <div className="rheology-stat-box">
                      <span className="rheology-stat-label">Tip Heater Offset</span>
                      <div className="rheology-stat-val" style={{ color: "var(--secondary)" }}>
                        {result.rheology.heater_offset_c > 0 ? `+${result.rheology.heater_offset_c}` : result.rheology.heater_offset_c}°C
                      </div>
                      <span className="rheology-stat-sub">
                        Thermal nozzle offset
                      </span>
                    </div>
                  </div>

                  {/* Machine Parameter Compensation Action */}
                  <div className="compensation-action-card">
                    <div className="compensation-action-title">
                      ⚙️ Machine Parameter Compensation Recommendation
                    </div>
                    <div className="compensation-action-detail">
                      {result.rheology.pressure_offset_mpa < 0 ? (
                        <>
                          <strong>Reduce dispense pressure by {Math.abs(result.rheology.pressure_offset_mpa).toFixed(4)} MPa ({Math.abs(result.rheology.pressure_offset_pct)}%)</strong> to compensate for thermal viscosity thinning and prevent dot slump or line bleed.
                        </>
                      ) : result.rheology.pressure_offset_mpa > 0 ? (
                        <>
                          <strong>Increase dispense pressure by +{result.rheology.pressure_offset_mpa.toFixed(4)} MPa (+{result.rheology.pressure_offset_pct}%)</strong> to overcome fluid thickening caused by cool cleanroom conditions.
                        </>
                      ) : (
                        <>
                          <strong>Fluid viscosity is nominal.</strong> Maintain standard pneumatic baseline pressure (0.200 MPa).
                        </>
                      )}
                      {result.rheology.heater_offset_c !== 0 && (
                        <span style={{ display: "block", marginTop: "0.4rem" }}>
                          Optional nozzle heater trim: Adjust tip heater setpoint by {result.rheology.heater_offset_c > 0 ? `+${result.rheology.heater_offset_c}` : result.rheology.heater_offset_c}°C.
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Thixotropic Purge Alert */}
                  {result.rheology.thixotropic_alert && (
                    <div className="thixotropic-banner">
                      <span style={{ fontSize: "1.3rem" }}>⚠️</span>
                      <div>
                        <strong>Thixotropic Restructuring Warning:</strong>
                        <p style={{ margin: "0.25rem 0 0 0" }}>{result.rheology.thixotropic_alert}</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* INNOVATIVE FEATURE: Interactive Elimination Tree & Counter-Test Loop */}
              <div className="diff-panel" style={{ marginTop: "1.5rem" }}>
                <div className="diff-header">
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontSize: "1.3rem" }}>🩺</span>
                      <h3 style={{ margin: 0, fontSize: "1.15rem", color: "var(--primary)" }}>
                        Differential Diagnosis & Counter-Test Loop
                      </h3>
                    </div>
                    <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.2rem" }}>
                      Active hypothesis elimination with live Bayesian confidence re-scoring
                    </p>
                  </div>
                  
                  <div className="undo-reset-toolbar">
                    <button 
                      onClick={handleUndoStep} 
                      disabled={historyStack.length === 0 || verifying}
                      title="Revert previous test outcome and restore confidence distribution"
                    >
                      ↩️ Undo Step
                    </button>
                    <button 
                      onClick={handleResetDiagnosticLoop} 
                      disabled={eliminationPathway.length === 0 || verifying}
                      title="Reset elimination tree back to initial diagnosis"
                    >
                      🔄 Reset Loop
                    </button>
                  </div>
                </div>

                {isResolved ? (
                  <div className="banner ok" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.75rem", padding: "1.25rem", borderRadius: "var(--radius-md)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontSize: "1.5rem" }}>🎉</span>
                      <strong style={{ fontSize: "1.1rem" }}>
                        Root Cause Confirmed: {pretty(confirmedCause || result.ranked_causes?.[0]?.name)}
                      </strong>
                    </div>
                    <p style={{ margin: 0, fontSize: "0.9rem" }}>
                      Verification test succeeded. Issue resolution path recorded into historical audit database.
                    </p>
                    <button className="btn-primary" onClick={pdf} style={{ alignSelf: "flex-start", marginTop: "0.5rem" }}>
                      📄 Download Confirmed Resolution Report
                    </button>
                  </div>
                ) : currentTest?.action_type === "ESCALATE" ? (
                  <div className="fae-escalation-alert">
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.5rem" }}>
                      <span style={{ fontSize: "1.5rem" }}>🚨</span>
                      <strong style={{ color: "var(--danger)", fontSize: "1.1rem" }}>
                        {currentTest.title}
                      </strong>
                    </div>
                    <p style={{ fontSize: "0.95rem", marginBottom: "1rem", color: "var(--text-main)" }}>
                      {currentTest.instruction}
                    </p>
                    <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                      <button className="btn-primary" style={{ background: "var(--danger)", borderColor: "var(--danger)", color: "#fff" }} onClick={pdf}>
                        📋 Export FAE Diagnostic Packet (PDF)
                      </button>
                      <button className="btn-ghost" onClick={handleResetDiagnosticLoop}>
                        🔄 Restart Automated Checks
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Leading Hypothesis Card */}
                    {result.ranked_causes?.[0] && (
                      <div className="hypothesis-lead-card">
                        <div className="hypothesis-lead-info">
                          <span style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "1px", color: "var(--text-muted)", fontWeight: 700 }}>
                            Target Hypothesis (Rank #1)
                          </span>
                          <strong style={{ fontSize: "1.15rem", color: "var(--text-main)" }}>
                            {result.ranked_causes[0].name}
                          </strong>
                          <span className="muted" style={{ fontSize: "0.85rem" }}>
                            {result.ranked_causes[0].family_label || result.ranked_causes[0].category}
                          </span>
                        </div>
                        <div className="hypothesis-confidence-pill">
                          {result.ranked_causes[0].likelihood_pct}%
                        </div>
                      </div>
                    )}

                    {/* Low-Cost Action Prompt Card */}
                    {currentTest && (
                      <div className="counter-test-card">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span className="cost-tag">{currentTest.cost_badge}</span>
                          <span className="muted" style={{ fontSize: "0.8rem" }}>Recommended Low-Cost Test</span>
                        </div>
                        <h4 style={{ margin: 0, fontSize: "1.05rem", color: "var(--primary)" }}>
                          {currentTest.title}
                        </h4>
                        <p style={{ margin: 0, fontSize: "0.9rem", lineHeight: 1.5, color: "var(--text-main)" }}>
                          {currentTest.instruction}
                        </p>
                        {currentTest.expected_resolved && (
                          <div style={{ background: "rgba(0,0,0,0.25)", padding: "0.75rem", borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--success)", fontSize: "0.85rem" }}>
                            <strong style={{ color: "var(--success)" }}>Expected Outcome:</strong> {currentTest.expected_resolved}
                          </div>
                        )}

                        {/* 3 Quick Feedback Action Buttons */}
                        <div className="test-feedback-btn-group">
                          <button
                            className="btn-feedback btn-feedback-resolved"
                            disabled={verifying}
                            onClick={() => handleCounterTestFeedback("resolved")}
                          >
                            <span>🟢 Resolved</span>
                          </button>
                          <button
                            className="btn-feedback btn-feedback-shifted"
                            disabled={verifying}
                            onClick={() => handleCounterTestFeedback("shifted")}
                          >
                            <span>🟡 Shifted</span>
                          </button>
                          <button
                            className="btn-feedback btn-feedback-unresolved"
                            disabled={verifying}
                            onClick={() => handleCounterTestFeedback("unresolved")}
                          >
                            <span>🔴 Unresolved</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* Elimination Audit Trail */}
                {eliminationPathway.length > 0 && (
                  <div style={{ marginTop: "1.25rem" }}>
                    <h5 style={{ margin: "0 0 0.5rem 0", color: "var(--text-muted)", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      Elimination Pathway ({eliminationPathway.length} Step{eliminationPathway.length > 1 ? "s" : ""})
                    </h5>
                    <div className="elimination-timeline">
                      {eliminationPathway.map((step: any, idx: number) => {
                        const isElim = step.status === "ELIMINATED";
                        const isConf = step.status === "CONFIRMED";
                        return (
                          <div 
                            key={idx} 
                            className={`elimination-step-node ${isElim ? "eliminated" : isConf ? "confirmed" : "shifted"}`}
                          >
                            <span style={{ fontWeight: 800, minWidth: "20px" }}>{idx + 1}.</span>
                            <div style={{ flex: 1 }}>
                              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                                <span style={{ fontWeight: 700, color: isElim ? "var(--danger)" : isConf ? "var(--success)" : "var(--warning)" }}>
                                  {isElim ? "❌ ELIMINATED" : isConf ? "✅ CONFIRMED" : "🟡 SHIFTED"}
                                </span>
                                <span className={isElim ? "eliminated-cause-name" : ""}>
                                  {step.target_cause_name}
                                </span>
                              </div>
                              <div className="muted" style={{ fontSize: "0.8rem", marginTop: "0.15rem" }}>
                                {step.summary || `Tested via ${step.test_title}`}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

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

              <h3 style={{ marginTop: "2rem", marginBottom: "1rem", color: "var(--primary)" }}>Recommended Action Plan</h3>

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
                        Step {stepNum}: {step.action_title && !step.action_title.startsWith("Step ") ? step.action_title : (step.target_cause && step.target_cause !== "System Detected" ? pretty(step.target_cause) : (step.instruction || step.action_details || "").slice(0, 35) + "...")}
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
