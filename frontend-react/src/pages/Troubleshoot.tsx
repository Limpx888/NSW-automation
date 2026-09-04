import { useCallback, useEffect, useMemo, useState, useRef, Suspense } from "react";
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
  const [trainingMode, setTrainingMode] = useState(false);
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

  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshQuestion = useCallback(async (nextAnswers: Record<string, any>, llm = useLlm) => {
    const payload = { ...nextAnswers, use_llm: llm, include_optional: true };
    const res = await postDiscover(payload);
    setComplete(res.complete);
    setCurrentQ(res.next);
    setProgress(res.progress);
    setAnswers(res.answers || nextAnswers);
    return res;
  }, [useLlm]);

  const loadDemo = useCallback(async () => {
    const { sample_image, ...rest } = DEMO_PRESET;
    setSample(sample_image);
    setPreview(sampleUrl(sample_image));
    setOrder(Object.keys(rest));
    setNozzle(rest.nozzle_id_um || 60);
    await refreshQuestion(rest);
  }, [refreshQuestion]);

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
          await loadDemo();
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
  }, [loadDemo, refreshQuestion]);

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
      setError(err.message || "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCounterTestFeedback = async (feedback: "resolved" | "unresolved" | "shifted") => {
    if (!currentTest || !result || verifying) return;
    setVerifying(true);
    try {
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
    a.download = `nsw-dispense-report-${result.session_id || "diagnostic"}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const history = useMemo(
    () => order.filter((id) => id !== SKIPPED && answers[id] != null),
    [order, answers],
  );

  // NSW 5x rule violation check
  const isNswRuleViolation = 
    (answers.material === "solder_paste" || !answers.material) &&
    ((answers.nozzle_id_um && Number(answers.nozzle_id_um) < 80) ||
     (result?.ranked_causes?.[0]?.id === "powder_nozzle_mismatch"));

  return (
    <div>
      {/* Top Workspace Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <span className="card-badge" style={{ color: "var(--primary)", borderColor: "rgba(16, 185, 129, 0.3)" }}>
              Workspace Split · 50/50 Dual Engine
            </span>
          </div>
          <h1>Diagnostic Workspace</h1>
          <p className="muted" style={{ margin: 0, fontSize: "0.92rem" }}>
            High-precision root-cause differential diagnosis and thermal rheology compensation engine
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.65rem", alignItems: "center" }}>
          <button
            className="btn-compact-demo"
            onClick={loadDemo}
            title="Pre-load Type 6 Solder Paste under-dispensing demo"
          >
            <span>🧪</span> Load Judge Demo
          </button>
          {result && (
            <button className="btn-ghost" style={{ fontSize: "0.82rem", padding: "0.45rem 0.85rem" }} onClick={pdf}>
              <span>📄</span> Export PDF
            </button>
          )}
        </div>
      </div>

      {error && <div className="banner warn">{error}</div>}

      {/* Responsive 50/50 Workspace Split */}
      <div className="workspace-split">

        {/* ===================================================================
            LEFT COLUMN (Input & Physical Context - 50%)
           =================================================================== */}
        <div className="workspace-left-col">
          
          {/* Card 1: Visual & Material Setup */}
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span style={{ color: "var(--secondary)" }}>📸</span>
                <h3>Visual & Material Setup</h3>
              </div>
              <span className="card-badge">Section 1</span>
            </div>

            {/* Compact Image Dropzone (h-36 / ~140px) */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: "none" }}
              onChange={(e) => onFile(e.target.files?.[0] || null)}
            />

            <div
              className="compact-dropzone"
              onClick={() => fileInputRef.current?.click()}
            >
              {preview ? (
                <>
                  <img src={preview} alt="Dispense sample" className="compact-dropzone-preview" />
                  <div className="compact-dropzone-content" style={{ background: "rgba(15, 23, 42, 0.8)", padding: "0.5rem 1rem", borderRadius: "6px" }}>
                    <span style={{ color: "var(--primary)", fontWeight: 600, fontSize: "0.85rem" }}>✓ Image Loaded</span>
                    <span className="muted" style={{ fontSize: "0.75rem" }}>Click to replace photo</span>
                  </div>
                </>
              ) : (
                <div className="compact-dropzone-content">
                  <span style={{ fontSize: "1.5rem" }}>📷</span>
                  <span style={{ fontSize: "0.88rem", fontWeight: 600, color: "var(--text-main)" }}>
                    Drop dispense photo or click to browse
                  </span>
                  <span className="muted" style={{ fontSize: "0.75rem" }}>
                    Supports PNG, JPG (Auto defect vision classification)
                  </span>
                </div>
              )}
            </div>

            {/* Quick pre-loaded demo thumbnails */}
            {samples.length > 0 && (
              <div className="thumbnails-row">
                <span className="muted" style={{ fontSize: "0.72rem", alignSelf: "center", whiteSpace: "nowrap" }}>
                  Demo samples:
                </span>
                {samples.slice(0, 4).map((name) => (
                  <button
                    key={name}
                    type="button"
                    className={`thumbnail-pill ${sample === name ? "active" : ""}`}
                    onClick={() => {
                      setSample(name);
                      setFile(null);
                      setPreview(sampleUrl(name));
                    }}
                  >
                    {name.replace(/\.[^/.]+$/, "").replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            )}

            {/* 2-Column Dropdown Grid: Material & Pattern */}
            <div className="dropdown-grid">
              <div>
                <label className="form-label">Material Type</label>
                <select
                  value={answers.material || "solder_paste"}
                  onChange={(e) => commit("material", e.target.value)}
                >
                  <option value="solder_paste">Solder Paste (Type 3-6)</option>
                  <option value="silver_epoxy">Silver Epoxy</option>
                  <option value="uv_glue">UV Acrylic / Adhesive</option>
                  <option value="silicone_gel">Silicone Gel</option>
                </select>
              </div>

              <div>
                <label className="form-label">Dispense Pattern</label>
                <select
                  value={answers.pattern || "dot"}
                  onChange={(e) => commit("pattern", e.target.value)}
                >
                  <option value="dot">Dot Array</option>
                  <option value="line">Continuous Line</option>
                  <option value="dam_fill">Dam & Fill</option>
                </select>
              </div>
            </div>
          </div>

          {/* Card 2: Physics & Environment Setup */}
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span style={{ color: "var(--warning)" }}>🌡️</span>
                <h3>Physics & Environment Setup</h3>
              </div>
              <span className="card-badge">Section 2</span>
            </div>

            <div className="env-control-panel">
              {/* Ambient Temperature Slider & Presets */}
              <div className="env-row">
                <div className="env-row-header">
                  <span className="form-label" style={{ margin: 0 }}>Workshop Ambient Temperature</span>
                  <div className="env-value-badge" style={{ color: ambientTemp > 23 ? "var(--warning)" : ambientTemp < 23 ? "var(--secondary)" : "var(--primary)" }}>
                    {ambientTemp.toFixed(1)}°C
                    {ambientTemp !== 23 && (
                      <span style={{ fontSize: "0.72rem", marginLeft: "0.35rem", opacity: 0.8 }}>
                        ({ambientTemp > 23 ? `+${(ambientTemp - 23).toFixed(1)}` : (ambientTemp - 23).toFixed(1)}°C)
                      </span>
                    )}
                  </div>
                </div>

                <input
                  type="range"
                  min="10.0"
                  max="45.0"
                  step="0.5"
                  value={ambientTemp}
                  onChange={(e) => setAmbientTemp(parseFloat(e.target.value))}
                  style={{ width: "100%", accentColor: "var(--warning)", cursor: "pointer" }}
                />

                <div className="env-presets-group">
                  {[
                    { label: "Standard (23°C)", val: 23.0 },
                    { label: "Warm (26.5°C)", val: 26.5 },
                    { label: "Cold (18°C)", val: 18.0 },
                    { label: "Peak (30°C)", val: 30.0 },
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

              {/* Syringe Pot Life Stepper / Slider */}
              <div className="env-row">
                <div className="env-row-header">
                  <span className="form-label" style={{ margin: 0 }}>Syringe Open Pot Life</span>
                  <div className="env-value-badge">
                    {potLife.toFixed(1)} hrs
                    <span style={{ fontSize: "0.72rem", marginLeft: "0.4rem", color: potLife > 6 ? "var(--danger)" : potLife < 2 ? "var(--primary)" : "var(--text-muted)" }}>
                      {potLife < 2 ? "Fresh" : potLife > 6 ? "Aged (>6h)" : "Normal"}
                    </span>
                  </div>
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

                <div className="env-presets-group">
                  {[
                    { label: "Fresh (<2h)", val: 0.5 },
                    { label: "Mid-Shift (4h)", val: 4.0 },
                    { label: "Aged (>6h)", val: 8.0 },
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
            </div>
          </div>

          {/* Card 3: Primary Observed Symptom Card */}
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span style={{ color: "var(--primary)" }}>📋</span>
                <h3>Primary Observed Symptoms</h3>
              </div>
              <div style={{ display: "flex", gap: "0.85rem", alignItems: "center" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.78rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={useLlm}
                    onChange={(e) => setUseLlm(e.target.checked)}
                  />
                  <span style={{ color: useLlm ? "var(--secondary)" : "var(--text-muted)", fontWeight: useLlm ? 600 : 400 }}>
                    LLM Q&A
                  </span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.78rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={trainingMode}
                    onChange={(e) => setTrainingMode(e.target.checked)}
                  />
                  <span style={{ color: trainingMode ? "var(--primary)" : "var(--text-muted)", fontWeight: trainingMode ? 600 : 400 }}>
                    Training Mode
                  </span>
                </label>
              </div>
            </div>

            {/* Dimension Progress Chips */}
            <div className="chips" style={{ marginBottom: "0.85rem" }}>
              {progress?.dimensions?.map((dim: any) => (
                <span key={dim.id} className={`chip ${dim.done ? "done" : ""}`}>
                  {dim.done ? "✓" : "·"} {dim.title}
                </span>
              ))}
            </div>

            {/* Dynamic Q&A Body */}
            {currentQ ? (
              <div style={{ marginTop: "0.5rem" }}>
                <h4 style={{ marginBottom: "0.5rem", color: "var(--text-main)" }}>
                  {currentQ.prompt}
                </h4>

                {trainingMode && currentQ.why && (
                  <div className="training-tip">
                    <strong>💡 Engineering Note:</strong> {currentQ.why}
                  </div>
                )}

                <div style={{ marginTop: "0.85rem" }}>
                  {currentQ.options === "number_or_skip" ? (
                    <div>
                      <input
                        className="input mono"
                        type="number"
                        min={0}
                        max={400}
                        value={nozzle || ""}
                        onChange={(e) => setNozzle(Number(e.target.value))}
                        placeholder="Enter nozzle inner diameter (µm)..."
                      />
                      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
                        <button
                          className="btn-primary"
                          style={{ flex: 1, padding: "0.55rem" }}
                          onClick={() => (nozzle ? commit(currentQ.id, nozzle) : skip(currentQ.id))}
                        >
                          Save Nozzle ID
                        </button>
                        <button
                          className="btn-ghost"
                          style={{ padding: "0.55rem 1rem" }}
                          onClick={() => skip(currentQ.id)}
                        >
                          Skip
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                      {(currentQ.choices || []).map((choice: any) => (
                        <button
                          key={choice.id}
                          className="choice"
                          onClick={() => commit(currentQ.id, choice.id)}
                        >
                          <span>{choice.label}</span>
                          <span className="muted" style={{ fontSize: "0.75rem" }}>Select →</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {order.length > 0 && (
                  <button
                    className="btn-ghost"
                    style={{ marginTop: "0.75rem", width: "100%", padding: "0.45rem", fontSize: "0.8rem" }}
                    onClick={back}
                  >
                    ← Previous Question
                  </button>
                )}
              </div>
            ) : complete ? (
              <div className="banner ok" style={{ margin: "0.5rem 0" }}>
                <span>✓ All required symptom dimensions identified. Ready to analyze.</span>
              </div>
            ) : (
              <p className="muted" style={{ fontSize: "0.85rem" }}>Configuring symptom interview questions...</p>
            )}

            {history.length > 0 && (
              <details style={{ marginTop: "0.85rem" }}>
                <summary>Current Symptom Log ({history.length})</summary>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                  {history.map((id) => (
                    <div key={id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
                      <span className="muted">{pretty(id)}:</span>
                      <span className="mono" style={{ color: "var(--text-main)" }}>{pretty(answers[id])}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>

          {/* Primary CTA: Analyze Root Cause */}
          <button
            className="btn-primary btn-cta-full"
            disabled={analyzing || (!complete && !answers.defect_class && !answers.amount)}
            onClick={analyze}
          >
            {analyzing ? "⚡ Running Bayesian Inference & Rheology Simulation..." : "⚡ Analyze Root Cause"}
          </button>
        </div>

        {/* ===================================================================
            RIGHT COLUMN (Live Intelligence Output - 50%)
           =================================================================== */}
        <div className="workspace-right-col">
          {!result ? (
            <div className="standby-state-box">
              <div className="standby-icon">⚡</div>
              <h3 style={{ margin: 0, color: "var(--text-main)" }}>Awaiting Diagnostic Execution</h3>
              <p style={{ maxWidth: "380px", margin: 0, fontSize: "0.88rem" }}>
                Configure physical dispense parameters on the left and click <strong>Analyze Root Cause</strong> to run Bayesian differential diagnosis and Arrhenius rheology simulation.
              </p>
            </div>
          ) : (
            <>
              {/* Output Card 1: Top Priority Cause Card */}
              {result.ranked_causes?.[0] && (
                <div className="top-cause-card">
                  <div className="top-cause-header">
                    <div>
                      <span className="card-badge" style={{ color: "var(--primary)", borderColor: "rgba(16, 185, 129, 0.3)" }}>
                        Rank #1 Root Cause
                      </span>
                      <div className="top-cause-name" style={{ marginTop: "0.35rem" }}>
                        {result.ranked_causes[0].name}
                      </div>
                      <div className="top-cause-meta">
                        Category: {result.ranked_causes[0].family_label || result.ranked_causes[0].category} · Cost Rank: {result.ranked_causes[0].cost_rank}
                      </div>
                    </div>
                  </div>

                  {/* Confidence Progress Bar */}
                  <div className="confidence-bar-container">
                    <div className="confidence-bar-header">
                      <span className="confidence-bar-label">Bayesian Likelihood Confidence</span>
                      <span className="confidence-percentage">
                        {result.ranked_causes[0].likelihood_pct}%
                      </span>
                    </div>
                    <div className="progress-track">
                      <div
                        className="progress-fill"
                        style={{ width: `${Math.min(100, result.ranked_causes[0].likelihood_pct)}%` }}
                      />
                    </div>
                  </div>

                  {/* Explicit Rule Flags */}
                  {isNswRuleViolation && (
                    <div className="rule-flag-pill">
                      <span>⚠️</span>
                      <span>
                        <strong>NSW 5× Rule Violation:</strong> Nozzle ID {answers.nozzle_id_um ? `(${answers.nozzle_id_um}µm)` : ""} is below the 5× largest powder particle floor (80µm).
                      </span>
                    </div>
                  )}

                  {result.fired_rules?.slice(0, 2).map((rule: any) => (
                    <div key={rule.id} className="rule-flag-pill" style={{ background: "rgba(56, 189, 248, 0.08)", borderColor: "rgba(56, 189, 248, 0.3)", color: "#bae6fd" }}>
                      <span>💡</span>
                      <span>{rule.explain || rule.id}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Output Card 2: Thermal & Rheology Offset Card (Amber Outline) */}
              {result.rheology && (
                <div className="rheology-offset-card">
                  <div className="rheology-offset-header">
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontSize: "1.25rem" }}>🌡️</span>
                      <h3 style={{ margin: 0, color: "var(--warning)" }}>
                        Thermal & Rheology Offset
                      </h3>
                    </div>
                    <span className="card-badge" style={{ color: "var(--warning)", borderColor: "rgba(245, 158, 11, 0.4)" }}>
                      {result.rheology.risk_level === "OPTIMAL" ? "Optimal Nominal" : "Thermal Drift Warning"}
                    </span>
                  </div>

                  {/* Quantitative Parameter Offset Chips in JetBrains Mono */}
                  <div className="rheology-chips-grid">
                    <div className="offset-chip">
                      <span className="offset-chip-label">📉 Pressure Offset</span>
                      <span className="offset-chip-value mono warning">
                        {result.rheology.pressure_offset_mpa >= 0 ? `+${result.rheology.pressure_offset_mpa}` : result.rheology.pressure_offset_mpa} MPa
                      </span>
                      <span className="muted" style={{ fontSize: "0.72rem" }}>
                        ({result.rheology.pressure_offset_pct >= 0 ? `+${result.rheology.pressure_offset_pct}` : result.rheology.pressure_offset_pct}%)
                      </span>
                    </div>

                    <div className="offset-chip">
                      <span className="offset-chip-label">🌡️ Tip Temp Offset</span>
                      <span className="offset-chip-value mono">
                        {result.rheology.heater_offset_c > 0 ? `+${result.rheology.heater_offset_c}` : result.rheology.heater_offset_c}°C
                      </span>
                      <span className="muted" style={{ fontSize: "0.72rem" }}>
                        Nozzle heater trim
                      </span>
                    </div>

                    <div className="offset-chip">
                      <span className="offset-chip-label">🔄 Viscosity Drift</span>
                      <span className="offset-chip-value mono" style={{ color: result.rheology.viscosity_drift_pct < 0 ? "var(--danger)" : "var(--primary)" }}>
                        {result.rheology.viscosity_drift_pct >= 0 ? `+${result.rheology.viscosity_drift_pct}` : result.rheology.viscosity_drift_pct}%
                      </span>
                      <span className="muted" style={{ fontSize: "0.72rem" }}>
                        Ratio: {result.rheology.viscosity_ratio}x
                      </span>
                    </div>
                  </div>

                  {/* Offset Action Recommendation */}
                  <div className="offset-action-banner">
                    {result.rheology.pressure_offset_mpa < 0 ? (
                      <div>
                        <strong>Compensation:</strong> Reduce pneumatic pressure by {Math.abs(result.rheology.pressure_offset_mpa).toFixed(4)} MPa to prevent spreading slump.
                      </div>
                    ) : result.rheology.pressure_offset_mpa > 0 ? (
                      <div>
                        <strong>Compensation:</strong> Increase pneumatic pressure by +{result.rheology.pressure_offset_mpa.toFixed(4)} MPa to overcome fluid thickening.
                      </div>
                    ) : (
                      <div><strong>Nominal:</strong> Fluid viscosity is within operating baseline (23°C).</div>
                    )}
                    {result.rheology.thixotropic_alert && (
                      <div style={{ marginTop: "0.35rem", fontWeight: 600 }}>
                        🔄 Action: Execute 3 continuous dummy purge shots (open pot life &gt;6h).
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Output Card 3: Interactive Elimination Tree Card */}
              <div className="elimination-card">
                <div className="elimination-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "1.2rem" }}>🩺</span>
                    <h3 style={{ margin: 0, color: "var(--text-main)" }}>
                      Interactive Elimination Tree
                    </h3>
                  </div>

                  <div style={{ display: "flex", gap: "0.4rem" }}>
                    <button
                      className="btn-compact-demo"
                      disabled={historyStack.length === 0 || verifying}
                      onClick={handleUndoStep}
                      title="Undo last verification step"
                    >
                      ↩ Undo
                    </button>
                    <button
                      className="btn-compact-demo"
                      disabled={eliminationPathway.length === 0 || verifying}
                      onClick={handleResetDiagnosticLoop}
                      title="Reset elimination loop"
                    >
                      🔄 Reset
                    </button>
                  </div>
                </div>

                {/* Resolved State */}
                {isResolved ? (
                  <div className="banner ok" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.6rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontSize: "1.25rem" }}>🎉</span>
                      <strong style={{ fontSize: "1.05rem" }}>
                        Root Cause Confirmed: {pretty(confirmedCause || result.ranked_causes?.[0]?.name)}
                      </strong>
                    </div>
                    <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-main)" }}>
                      Physical verification test succeeded. Root cause confirmed and recorded into closed-loop audit history.
                    </p>
                    <button className="btn-primary" style={{ marginTop: "0.5rem", padding: "0.6rem 1.2rem" }} onClick={pdf}>
                      📄 Download Confirmed Report (PDF)
                    </button>
                  </div>
                ) : currentTest?.action_type === "ESCALATE" ? (
                  <div className="banner danger" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.6rem" }}>
                    <strong style={{ color: "var(--danger)", fontSize: "1rem" }}>
                      🚨 {currentTest.title}
                    </strong>
                    <p style={{ margin: 0, fontSize: "0.88rem", color: "var(--text-main)" }}>
                      {currentTest.instruction}
                    </p>
                    <button className="btn-primary" style={{ background: "var(--danger)", borderColor: "var(--danger)", color: "#fff" }} onClick={pdf}>
                      Export FAE Diagnostic Packet (PDF)
                    </button>
                  </div>
                ) : (
                  <>
                    {/* Lowest-Cost Verification Action Box */}
                    {currentTest && (
                      <div className="counter-action-box">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                          <span className="card-badge" style={{ color: "var(--secondary)", borderColor: "rgba(56, 189, 248, 0.3)" }}>
                            {currentTest.cost_badge || "⚡ Low-Cost Action"}
                          </span>
                          <span className="muted" style={{ fontSize: "0.75rem" }}>
                            Target: {pretty(result.ranked_causes?.[0]?.name || "Lead Hypothesis")}
                          </span>
                        </div>
                        <div className="counter-action-title">{currentTest.title}</div>
                        <div className="counter-action-instruction">{currentTest.instruction}</div>

                        {/* 3 Quick Feedback Buttons */}
                        <div className="feedback-buttons-row">
                          <button
                            className="btn-fb btn-fb-resolved"
                            disabled={verifying}
                            onClick={() => handleCounterTestFeedback("resolved")}
                          >
                            <span>🟢 Resolved</span>
                          </button>
                          <button
                            className="btn-fb btn-fb-shifted"
                            disabled={verifying}
                            onClick={() => handleCounterTestFeedback("shifted")}
                          >
                            <span>🟡 Shifted</span>
                          </button>
                          <button
                            className="btn-fb btn-fb-unresolved"
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

                {/* Live Visual Elimination Trail */}
                {eliminationPathway.length > 0 && (
                  <div className="elimination-trail">
                    <span className="form-label" style={{ margin: 0 }}>
                      Live Elimination Trail ({eliminationPathway.length} Step{eliminationPathway.length > 1 ? "s" : ""})
                    </span>
                    {eliminationPathway.map((step: any, idx: number) => {
                      const isElim = step.status === "ELIMINATED";
                      const isConf = step.status === "CONFIRMED";
                      return (
                        <div
                          key={idx}
                          className={`trail-node ${isElim ? "eliminated" : isConf ? "confirmed" : "shifted"}`}
                        >
                          <span className="mono" style={{ fontWeight: 700 }}>#{idx + 1}</span>
                          <span style={{ fontWeight: 700, color: isElim ? "var(--danger)" : isConf ? "var(--primary)" : "var(--warning)" }}>
                            {isElim ? "❌ ELIMINATED" : isConf ? "✅ CONFIRMED" : "🟡 SHIFTED"}
                          </span>
                          <span className={isElim ? "trail-text-eliminated" : ""} style={{ color: "var(--text-main)" }}>
                            {step.target_cause_name}
                          </span>
                          <span className="muted" style={{ marginLeft: "auto", fontSize: "0.75rem" }}>
                            {step.test_title}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Expandable Detailed Cause Matrix */}
              <details>
                <summary>Complete Cause Ranking Matrix ({result.ranked_causes?.length || 0} Candidates)</summary>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {result.ranked_causes?.map((cause: any, idx: number) => (
                    <div
                      key={cause.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "0.5rem 0.75rem",
                        background: idx === 0 ? "rgba(16, 185, 129, 0.08)" : "var(--bg-card-alt)",
                        borderRadius: "6px",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div>
                        <span className="mono" style={{ fontWeight: 700, color: idx === 0 ? "var(--primary)" : "var(--text-muted)", marginRight: "0.5rem" }}>
                          #{idx + 1}
                        </span>
                        <strong style={{ color: "var(--text-main)" }}>{cause.name}</strong>
                        <span className="muted" style={{ fontSize: "0.75rem", marginLeft: "0.5rem" }}>
                          ({cause.family_label || cause.category})
                        </span>
                      </div>
                      <span className="mono" style={{ fontWeight: 700, color: idx === 0 ? "var(--primary)" : "var(--text-main)" }}>
                        {cause.likelihood_pct}%
                      </span>
                    </div>
                  ))}
                </div>
              </details>

              {/* Expandable Engineering SOP Plan */}
              <details>
                <summary>Engineering SOP Action Plan (SOP Standard)</summary>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                  {(result.sop_plan || result.action_plan)?.map((step: any, i: number) => (
                    <div
                      key={i}
                      style={{
                        padding: "0.75rem",
                        background: "var(--bg-card-alt)",
                        borderRadius: "6px",
                        borderLeft: "3px solid var(--secondary)",
                      }}
                    >
                      <h4 style={{ margin: "0 0 0.25rem 0", color: "var(--text-main)" }}>
                        Step {step.step_number || i + 1}: {step.action_title || pretty(step.target_cause || "Action")}
                      </h4>
                      <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
                        {step.action_details || step.instruction}
                      </p>
                    </div>
                  ))}
                </div>
              </details>

              {/* Full PDF Download Button */}
              <button
                className="btn-ghost"
                style={{ width: "100%", padding: "0.75rem", fontSize: "0.9rem" }}
                onClick={pdf}
              >
                <span>📄</span> Download Full Engineering PDF Diagnostic Report
              </button>
            </>
          )}
        </div>

      </div>
    </div>
  );
}

export default function TroubleshootPage() {
  return (
    <Suspense fallback={<p>Loading Troubleshoot...</p>}>
      <TroubleshootInner />
    </Suspense>
  );
}
