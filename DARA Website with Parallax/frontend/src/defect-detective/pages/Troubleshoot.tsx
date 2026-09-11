import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  downloadReport,
  fetchMeta,
  postCounterTestVerify,
  postDiscover,
  postSession,
  sampleUrl,
} from "../lib/api";
import { DEMO_PRESET, FOLLOWUP_KEYS, pretty } from "../lib/content";

const SKIPPED = "_skipped";

type Step = "application" | "mode" | "capture" | "interview" | "results";

export default function Troubleshoot() {
  const [step, setStep] = useState<Step>("application");
  const [applications, setApplications] = useState<any[]>([]);
  const [modes, setModes] = useState<any[]>([]);
  const [selectedApp, setSelectedApp] = useState<any | null>(null);
  const [mode, setMode] = useState<"photo" | "questions" | "both" | "">("");
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [currentQ, setCurrentQ] = useState<any>(null);
  const [progress, setProgress] = useState<any>(null);
  const [complete, setComplete] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [samples, setSamples] = useState<string[]>([]);
  const [sample, setSample] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [nozzle, setNozzle] = useState(0);
  const [openCause, setOpenCause] = useState<string | null>(null);
  const [currentTest, setCurrentTest] = useState<any>(null);
  const [eliminationPathway, setEliminationPathway] = useState<any[]>([]);
  const [isResolved, setIsResolved] = useState(false);
  const [confirmedCause, setConfirmedCause] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [visionReady, setVisionReady] = useState(false);
  const [machineId, setMachineId] = useState("Dispenser-01");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshQuestion = useCallback(async (nextAnswers: Record<string, any>) => {
    const payload = { ...nextAnswers, use_llm: false, include_optional: true };
    const res = await postDiscover(payload);
    setComplete(res.complete);
    setCurrentQ(res.next);
    setProgress(res.progress);
    setAnswers(res.answers || nextAnswers);
    return res;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const m = await fetchMeta();
        if (cancelled) return;
        setApplications(m.applications || []);
        setModes(m.diagnosis_modes || []);
        setSamples(m.samples || []);
        setVisionReady(Boolean(m.vision_ready));
      } catch {
        if (!cancelled) setError("API is not running on port 8000. Start uvicorn first.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const baseAnswersForApp = (app: any, materialOverride?: string) => {
    const next: Record<string, any> = {
      application: app.id,
      application_title: app.title,
      machine_id: machineId,
    };
    if (app.material) next.material = app.material;
    if (materialOverride) next.material = materialOverride;
    if (app.default_pattern) next.pattern = app.default_pattern;
    return next;
  };

  const pickApplication = async (app: any, materialOverride?: string) => {
    setError("");
    setSelectedApp(app);
    setResult(null);
    const next = baseAnswersForApp(app, materialOverride);
    setAnswers(next);
    setOrder(Object.keys(next));
    setStep("mode");
  };

  const pickMode = async (id: "photo" | "questions" | "both") => {
    setMode(id);
    setResult(null);
    if (id === "photo") {
      setStep("capture");
      return;
    }
    setStep("interview");
    try {
      await refreshQuestion(answers);
    } catch {
      setError("Could not start the interview.");
    }
  };

  const onFile = (picked: File | null) => {
    setFile(picked);
    setSample("");
    if (picked) setPreview(URL.createObjectURL(picked));
    else setPreview("");
  };

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
    await refreshQuestion({ ...answers, [SKIPPED]: skipped });
  };

  const backQuestion = async () => {
    const nextOrder = [...order];
    const last = nextOrder.pop();
    if (!last || last === "application" || last === "application_title") return;
    if (selectedApp?.material && last === "material") return;
    if (selectedApp?.default_pattern && last === "pattern") return;
    const next = { ...answers };
    delete next[last];
    if (Array.isArray(next[SKIPPED])) {
      next[SKIPPED] = next[SKIPPED].filter((id: string) => id !== last);
    }
    setOrder(nextOrder);
    await refreshQuestion(next);
  };

  const analyze = async () => {
    if ((mode === "photo" || mode === "both") && !file && !sample) {
      setError("Add a dispense photo (or pick a demo sample) before analysing.");
      return;
    }
    if (mode === "questions" || mode === "both") {
      if (!answers.amount && !answers.defect_class) {
        setError("Finish the defect look question before analysing.");
        return;
      }
    }
    setAnalyzing(true);
    setError("");
    try {
      let payload = { ...answers };
      if (mode === "photo" && !payload.amount) {
        // Photo-only: still need enough ranking context — ask minimal defaults
        payload = {
          ...payload,
          frequency: payload.frequency || "continuous",
          recent_change: payload.recent_change || "none",
          location: payload.location || "multiple",
        };
      }
      const res = await postSession(payload, file, sample || null);
      setResult(res);
      setOpenCause(res.ranked_causes?.[0]?.id ?? null);
      setEliminationPathway([]);
      setIsResolved(false);
      setConfirmedCause(null);
      setCurrentTest(res.initial_test || null);
      setStep("results");
    } catch (err: any) {
      setError(err.message || "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const continueFromCapture = async () => {
    if (!file && !sample) {
      setError("Upload a photo or pick a demo sample.");
      return;
    }
    setError("");
    if (mode === "both") {
      setStep("interview");
      try {
        await refreshQuestion(answers);
      } catch {
        setError("Could not start the interview.");
      }
      return;
    }
    await analyze();
  };

  const handleCounterTestFeedback = async (feedback: "resolved" | "unresolved" | "shifted") => {
    if (!currentTest || !result || verifying) return;
    setVerifying(true);
    try {
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
      if (res.ranked_causes?.[0]?.id) setOpenCause(res.ranked_causes[0].id);
    } catch (err: any) {
      setError(err.message || "Verification step failed");
    } finally {
      setVerifying(false);
    }
  };

  const pdf = async () => {
    if (!result) return;
    const blob = await downloadReport({
      ...result,
      confirmed_cause: confirmedCause || result.confirmed_cause,
      elimination_pathway: eliminationPathway.length > 0 ? eliminationPathway : result.elimination_pathway,
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `nsw-dispense-report-${result.session_id || "diagnostic"}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const loadDemo = async () => {
    const app = applications.find((a) => a.id === "solder_paste_dispensing") || applications[0];
    const { sample_image, ...rest } = DEMO_PRESET;
    setSelectedApp(app);
    setMode("both");
    setSample(sample_image);
    setPreview(sampleUrl(sample_image));
    setFile(null);
    setNozzle(rest.nozzle_id_um || 60);
    const next = {
      ...rest,
      application: app?.id || "solder_paste_dispensing",
      application_title: app?.title || "Solder Paste Dispensing",
      machine_id: machineId,
    };
    setOrder(Object.keys(next));
    await refreshQuestion(next);
    setStep("interview");
  };

  const restart = () => {
    setStep("application");
    setSelectedApp(null);
    setMode("");
    setAnswers({});
    setOrder([]);
    setCurrentQ(null);
    setComplete(false);
    setResult(null);
    setFile(null);
    setSample("");
    setPreview("");
    setError("");
  };

  const history = useMemo(
    () => order.filter((id) => !["application", "application_title", SKIPPED].includes(id) && answers[id] != null),
    [order, answers],
  );

  const needsMaterialChoice = selectedApp && !selectedApp.material && selectedApp.material_choices;

  return (
    <div className="wizard">
      <div className="wizard-head">
        <div>
          <p className="eyebrow">NSW Application & Solutions</p>
          <h1>Defect Detective</h1>
          <p className="lede">
            Choose your pasting application first, then diagnose with a photo, a questionnaire, or both.
          </p>
        </div>
        <div className="wizard-actions">
          <button className="btn ghost" onClick={loadDemo} type="button">
            Load judge demo
          </button>
          {step !== "application" && (
            <button className="btn ghost" onClick={restart} type="button">
              Start over
            </button>
          )}
          {result && (
            <button className="btn primary" onClick={pdf} type="button">
              Download PDF
            </button>
          )}
        </div>
      </div>

      <ol className="stepper">
        {[
          ["application", "1. Pasting type"],
          ["mode", "2. Method"],
          ["capture", "3. Photo"],
          ["interview", "4. Questions"],
          ["results", "5. Causes"],
        ].map(([id, label]) => (
          <li key={id} className={step === id ? "active" : ""}>
            {label}
          </li>
        ))}
      </ol>

      {error && <div className="banner warn">{error}</div>}

      <div className="status-row">
        <label className="machine-selector">
          Target machine
          <select value={machineId} onChange={(event) => { setMachineId(event.target.value); setAnswers((current) => ({ ...current, machine_id: event.target.value })); }}>
            <option value="Dispenser-01">Dispenser #01</option>
            <option value="Dispenser-02">Dispenser #02</option>
            <option value="Dispenser-03">Dispenser #03</option>
          </select>
        </label>
        <span className={`pill ${visionReady ? "ok" : "warn"}`}>
          Vision {visionReady ? "ready (YOLO)" : "heuristic"}
        </span>
        {selectedApp && <span className="pill">{selectedApp.title}</span>}
        {mode && <span className="pill">{pretty(mode)}</span>}
      </div>

      {step === "application" && (
        <section>
          <h2>Select pasting / application type</h2>
          <p className="muted">
            Mapped from{" "}
            <a href="https://nswautomation.com/NSW/" target="_blank" rel="noreferrer">
              NSW Automation Application & Solutions
            </a>
            .
          </p>
          <div className="app-grid">
            {applications.map((app) => (
              <button
                key={app.id}
                type="button"
                className="app-card"
                style={{ ["--accent" as any]: app.accent }}
                onClick={() => {
                  if (app.material_choices && !app.material) {
                    setSelectedApp(app);
                  } else {
                    pickApplication(app);
                  }
                }}
              >
                <span className="app-accent" />
                <strong>{app.title}</strong>
                <span className="tagline">{app.tagline}</span>
                <p>{app.description}</p>
              </button>
            ))}
          </div>

          {needsMaterialChoice && selectedApp && step === "application" && (
            <div className="card inset">
              <h3>Choose dam / fill material</h3>
              <div className="choice-row">
                {selectedApp.material_choices.map((mat: string) => (
                  <button key={mat} type="button" className="btn choice" onClick={() => pickApplication(selectedApp, mat)}>
                    {pretty(mat)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {step === "mode" && (
        <section>
          <h2>How do you want to diagnose?</h2>
          <div className="mode-grid">
            {(modes.length
              ? modes
              : [
                  { id: "photo", title: "Upload a photo", description: "Vision classifies the defect." },
                  { id: "questions", title: "Answer questions", description: "Guided interview only." },
                  { id: "both", title: "Photo + questions", description: "Highest confidence path." },
                ]
            ).map((m: any) => (
              <button key={m.id} type="button" className="mode-card" onClick={() => pickMode(m.id)}>
                <strong>{m.title}</strong>
                <p>{m.description}</p>
              </button>
            ))}
          </div>
          <button className="btn ghost" type="button" onClick={() => setStep("application")}>
            ← Back to applications
          </button>
        </section>
      )}

      {step === "capture" && (
        <section className="card">
          <h2>Upload dispense photo</h2>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => onFile(e.target.files?.[0] || null)}
          />
          <div className="dropzone" onClick={() => fileInputRef.current?.click()}>
            {preview ? (
              <img src={preview} alt="Dispense preview" />
            ) : (
              <div>
                <strong>Drop or click to upload</strong>
                <p className="muted">PNG / JPG top-down shot of the dispense</p>
              </div>
            )}
          </div>
          {samples.length > 0 && (
            <div className="thumbnails-row">
              {samples.slice(0, 6).map((name) => (
                <button
                  key={name}
                  type="button"
                  className={`thumb ${sample === name ? "active" : ""}`}
                  onClick={() => {
                    setSample(name);
                    setFile(null);
                    setPreview(sampleUrl(name));
                  }}
                >
                  <img src={sampleUrl(name)} alt={name} />
                </button>
              ))}
            </div>
          )}
          <div className="wizard-actions">
            <button className="btn ghost" type="button" onClick={() => setStep("mode")}>
              ← Back
            </button>
            <button className="btn primary" type="button" disabled={analyzing} onClick={continueFromCapture}>
              {mode === "both" ? "Continue to questions" : analyzing ? "Analysing…" : "Analyse defect"}
            </button>
          </div>
        </section>
      )}

      {step === "interview" && (
        <section className="split">
          <div className="card">
            <div className="card-header">
              <h2>Process interview</h2>
              {progress && (
                <span className="pill">
                  {progress.answered}/{progress.total} core
                </span>
              )}
            </div>
            {currentQ ? (
              <div>
                <p className="prompt">{currentQ.prompt}</p>
                {currentQ.why && <p className="muted why">{currentQ.why}</p>}
                {currentQ.options === "number_or_skip" ? (
                  <div className="nozzle-row">
                    <input
                      type="number"
                      min={10}
                      max={500}
                      value={nozzle || ""}
                      placeholder="e.g. 60"
                      onChange={(e) => setNozzle(Number(e.target.value))}
                    />
                    <button
                      className="btn primary"
                      type="button"
                      disabled={!nozzle}
                      onClick={() => commit(currentQ.id, nozzle)}
                    >
                      Use {nozzle || "—"} µm
                    </button>
                    <button className="btn ghost" type="button" onClick={() => skip(currentQ.id)}>
                      Skip
                    </button>
                  </div>
                ) : (
                  <div className="choice-row">
                    {(currentQ.choices || currentQ.options || []).map((opt: any) => {
                      const id = typeof opt === "string" ? opt : opt.id;
                      const label = typeof opt === "string" ? pretty(opt) : opt.label;
                      return (
                        <button key={id} type="button" className="btn choice" onClick={() => commit(currentQ.id, id)}>
                          {label}
                        </button>
                      );
                    })}
                  </div>
                )}
                <div className="wizard-actions" style={{ marginTop: "1rem" }}>
                  <button className="btn ghost" type="button" onClick={backQuestion}>
                    ← Previous answer
                  </button>
                  {currentQ.optional && (
                    <button className="btn ghost" type="button" onClick={() => skip(currentQ.id)}>
                      Skip optional
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <p>Interview complete. Run analysis when ready.</p>
            )}
            {(complete || answers.amount || answers.defect_class) && (
              <button className="btn primary block" type="button" disabled={analyzing} onClick={analyze}>
                {analyzing ? "Analysing…" : "Analyse root causes"}
              </button>
            )}
          </div>
          <aside className="card">
            <h3>Answered so far</h3>
            <ul className="answer-list">
              {history.map((id) => (
                <li key={id}>
                  <span>{pretty(id)}</span>
                  <strong>{pretty(answers[id])}</strong>
                </li>
              ))}
            </ul>
            {(mode === "photo" || mode === "both") && preview && (
              <img className="side-preview" src={preview} alt="Selected dispense" />
            )}
            <button className="btn ghost" type="button" onClick={() => setStep(mode === "questions" ? "mode" : "capture")}>
              ← Back
            </button>
          </aside>
        </section>
      )}

      {step === "results" && result && (
        <section className="results">
          {result.vision?.annotated_image_b64 && (
            <div className="card">
              <div className="card-header">
                <h2>YOLO detection result</h2>
                <span className="pill ok">
                  {result.vision.detection_count ?? 0} box
                  {(result.vision.detection_count ?? 0) === 1 ? "" : "es"}
                </span>
              </div>
              <p className="muted" style={{ marginBottom: "0.75rem" }}>
                Bounding box · defect class · confidence (same style as Ultralytics Colab <code>results[0].plot()</code>)
              </p>
              <img
                className="annot-frame"
                src={`data:image/png;base64,${result.vision.annotated_image_b64}`}
                alt="YOLO annotated detections"
              />
              {(result.vision.detections || []).length > 0 ? (
                <ul className="answer-list" style={{ marginTop: "0.85rem" }}>
                  {result.vision.detections.map((det: any, i: number) => (
                    <li key={`${det.class}-${i}`}>
                      <span>
                        #{i + 1} {pretty(det.class)}
                      </span>
                      <strong>{Math.round((det.confidence || 0) * 100)}%</strong>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted" style={{ marginTop: "0.75rem" }}>
                  No PCB defect boxes found on this image. Ranking used {pretty(result.vision.method)} classification
                  instead — upload a PCB photo (missing hole / spur / copper) to see boxes like Colab.
                </p>
              )}
            </div>
          )}

          <div className="card highlight">
            <h2>Ranked root causes</h2>
            <p className="muted">
              {result.application_title || selectedApp?.title || pretty(result.material)} ·{" "}
              {pretty(result.defect_class)} · quality {result.quality?.score ?? result.quality?.overall_quality_score ?? "—"}
            </p>
            {result.vision && (
              <p>
                Vision: <strong>{pretty(result.vision.yolo_class || result.vision.defect_class)}</strong> (
                {Math.round((result.vision.confidence || 0) * 100)}%, {result.vision.method || result.vision.source})
              </p>
            )}
            <p className="explanation">{result.explanation}</p>
          </div>

          <div className="cause-list">
            {(result.ranked_causes || []).slice(0, 6).map((cause: any, idx: number) => (
              <button
                key={cause.id}
                type="button"
                className={`cause-card ${openCause === cause.id ? "open" : ""}`}
                onClick={() => setOpenCause(openCause === cause.id ? null : cause.id)}
              >
                <div className="cause-top">
                  <span>#{idx + 1}</span>
                  <strong>{cause.name || pretty(cause.id)}</strong>
                  <em>{Math.round(cause.likelihood_pct || cause.likelihood || 0)}%</em>
                </div>
                {openCause === cause.id && (
                  <p className="muted">{cause.check || cause.why || cause.action || "Inspect and verify on the line."}</p>
                )}
              </button>
            ))}
          </div>

          {/* ── Thermal & Rheology Offset Card ─────────────────────────────── */}
          {result.rheology && (
            <div className="card" style={{ marginTop: "1rem" }}>
              <div className="card-header" style={{ marginBottom: "0.85rem" }}>
                <h2 style={{ margin: 0 }}>Thermal &amp; Rheology Offset</h2>
                <span className="pill" style={{ fontSize: "0.7rem", opacity: 0.7 }}>
                  {pretty(result.rheology.material)} · {result.rheology.risk_level?.replace(/_/g, " ")}
                </span>
              </div>

              {/* Pressure offset row with Non-Newtonian badge */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem", alignItems: "center", marginBottom: "0.75rem" }}>
                <div style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "8px",
                  padding: "0.55rem 0.9rem",
                  display: "flex",
                  flexDirection: "column",
                  minWidth: "120px",
                }}>
                  <span className="muted" style={{ fontSize: "0.68rem", marginBottom: "2px" }}>Pressure Offset</span>
                  <strong style={{ fontSize: "1.05rem", color: result.rheology.pressure_offset_mpa < 0 ? "#f59e0b" : result.rheology.pressure_offset_mpa > 0 ? "#60a5fa" : "#94a3b8" }}>
                    {result.rheology.pressure_offset_mpa >= 0 ? "+" : ""}{result.rheology.pressure_offset_mpa?.toFixed(4)} MPa
                  </strong>
                  {result.rheology.non_newtonian_correction && (
                    <span className="badge-tag" style={{ marginTop: "4px", alignSelf: "flex-start" }}>
                      {result.rheology.correction_label}
                    </span>
                  )}
                </div>

                <div style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "8px",
                  padding: "0.55rem 0.9rem",
                  minWidth: "120px",
                }}>
                  <span className="muted" style={{ fontSize: "0.68rem", display: "block", marginBottom: "2px" }}>Non-Linear ΔP</span>
                  <strong style={{ fontSize: "1.05rem", color: "#4cc9f0" }}>
                    {result.rheology.shear_thinning_offset_mpa >= 0 ? "+" : ""}{result.rheology.shear_thinning_offset_mpa?.toFixed(4)} MPa
                  </strong>
                </div>

                <div style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "8px",
                  padding: "0.55rem 0.9rem",
                  minWidth: "120px",
                }}>
                  <span className="muted" style={{ fontSize: "0.68rem", display: "block", marginBottom: "2px" }}>Viscosity Drift</span>
                  <strong style={{ fontSize: "1.05rem" }}>
                    {result.rheology.viscosity_drift_pct >= 0 ? "+" : ""}{result.rheology.viscosity_drift_pct?.toFixed(1)}%
                  </strong>
                </div>

                <div style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "8px",
                  padding: "0.55rem 0.9rem",
                  minWidth: "120px",
                }}>
                  <span className="muted" style={{ fontSize: "0.68rem", display: "block", marginBottom: "2px" }}>Heater Offset</span>
                  <strong style={{ fontSize: "1.05rem" }}>
                    {result.rheology.heater_offset_c >= 0 ? "+" : ""}{result.rheology.heater_offset_c}°C
                  </strong>
                </div>
              </div>

              {/* Alert message */}
              {result.rheology.alert_message && (
                <p className="muted" style={{ fontSize: "0.8rem", marginBottom: "0.75rem", lineHeight: 1.55 }}>
                  {result.rheology.alert_message}
                </p>
              )}

              {/* ── Filler Settling Decay Bar ─────────────────────────── */}
              {result.rheology.settling_risk_pct > 0 && (
                <div style={{ marginTop: "0.75rem" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                    <span style={{ fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.04em" }}>
                      FILLER SETTLING RISK
                    </span>
                    <span style={{ fontSize: "0.72rem" }} className="muted">
                      n={result.rheology.power_law_n} · k={result.rheology.settling_risk_pct?.toFixed(1)}%
                    </span>
                  </div>

                  {/* Decay bar track */}
                  <div className="decay-bar-track">
                    <div
                      className={`decay-bar-fill ${(result.rheology.settling_risk_level ?? "low").toLowerCase()}`}
                      style={{ width: `${Math.min(100, result.rheology.settling_risk_pct)}%` }}
                    />
                  </div>

                  {/* ALERT badge — only when MODERATE or HIGH */}
                  {result.rheology.settling_risk_level !== "LOW" && (
                    <span className="badge-warning" style={{ marginTop: "0.45rem", display: "inline-block" }}>
                      ALERT: {result.rheology.settling_risk_level === "HIGH" ? "High" : "Moderate"} Filler Settling Risk ({result.rheology.settling_risk_pct?.toFixed(0)}%)
                    </span>
                  )}

                  {/* Recovery action text */}
                  {result.rheology.recovery_action_text && (
                    <p className="recovery-text">
                      {result.rheology.recovery_action_text}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {currentTest && !isResolved && (
            <div className="card" style={{ marginTop: "1rem", borderLeft: "3px solid rgba(76,201,240,0.4)" }}>
              {/* Card header */}
              <div className="card-header" style={{ marginBottom: "0.85rem" }}>
                <h3 style={{ margin: 0, fontSize: "0.8rem", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", opacity: 0.7 }}>
                  Recommended Verification Step (Optimized for Minimal Downtime)
                </h3>
                {currentTest.roi_efficiency && currentTest.roi_efficiency !== "N/A" && (
                  <span className={`badge-tag`} style={{
                    background: currentTest.roi_score >= 0.3 ? "rgba(34,197,94,0.12)" : currentTest.roi_score >= 0.1 ? "rgba(245,158,11,0.12)" : "rgba(148,163,184,0.10)",
                    borderColor: currentTest.roi_score >= 0.3 ? "rgba(34,197,94,0.4)" : currentTest.roi_score >= 0.1 ? "rgba(245,158,11,0.4)" : "rgba(148,163,184,0.3)",
                    color: currentTest.roi_score >= 0.3 ? "#166534" : currentTest.roi_score >= 0.1 ? "#7c4400" : "#64748b",
                  }}>
                    {currentTest.roi_efficiency}
                  </span>
                )}
              </div>

              {/* Action title */}
              <p style={{ margin: "0 0 0.65rem", fontWeight: 600, fontSize: "0.97rem" }}>
                {currentTest.title || currentTest.action_title || pretty(currentTest.action_id)}
              </p>

              {/* Cost chip row */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginBottom: "0.7rem" }}>
                {currentTest.time_min != null && (
                  <span className="badge-tag">
                    {currentTest.time_min} Min Est. Time
                  </span>
                )}
                {currentTest.risk_label && (
                  <span className="badge-tag">
                    {currentTest.risk_label}
                  </span>
                )}
                {currentTest.roi_score != null && currentTest.roi_score > 0 && (
                  <span className="badge-tag">
                    ROI: {currentTest.roi_score.toFixed(3)}
                  </span>
                )}
                {currentTest.cost_downtime != null && (
                  <span className="badge-tag" style={{ opacity: 0.7 }}>
                    Cost Index: {currentTest.cost_downtime.toFixed(2)}
                  </span>
                )}
              </div>

              {/* Instruction */}
              <p className="muted" style={{ fontSize: "0.82rem", marginBottom: "0.75rem", lineHeight: 1.6 }}>
                {currentTest.instruction || currentTest.description}
              </p>

              {/* Rationale block */}
              {currentTest.rationale && (
                <p className="rationale-text">
                  {currentTest.rationale}
                </p>
              )}

              {/* Action buttons */}
              <div className="choice-row" style={{ marginTop: "1rem" }}>
                <button className="btn primary" type="button" disabled={verifying} onClick={() => handleCounterTestFeedback("resolved")}>
                  Resolved
                </button>
                <button className="btn ghost" type="button" disabled={verifying} onClick={() => handleCounterTestFeedback("shifted")}>
                  Symptoms Shifted
                </button>
                <button className="btn ghost" type="button" disabled={verifying} onClick={() => handleCounterTestFeedback("unresolved")}>
                  Unresolved
                </button>
              </div>
            </div>
          )}


          {isResolved && (
            <div className="banner ok">Confirmed cause: {pretty(confirmedCause)}</div>
          )}

          {/* SOP Action Plan with Versioned NSW Citations */}
          {(result.sop_plan || []).length > 0 && (
            <div className="card" style={{ marginTop: "1.25rem" }}>
              <div className="card-header" style={{ marginBottom: "1rem" }}>
                <h2 style={{ margin: 0 }}>Troubleshooting Action Plan</h2>
                <span className="pill" style={{ background: "rgba(31,122,140,0.18)", color: "#4cc9f0", fontSize: "0.72rem" }}>
                  NSW Spec DB v2026.1
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                {(result.sop_plan as any[]).map((step: any, idx: number) => {
                  const urgency: "High" | "Medium" | "Low" = step.urgency || "Medium";
                  const urgencyColors: Record<string, string> = {
                    High: "#ef4444",
                    Medium: "#f59e0b",
                    Low: "#22c55e",
                  };
                  const urgencyBg: Record<string, string> = {
                    High: "rgba(239,68,68,0.12)",
                    Medium: "rgba(245,158,11,0.12)",
                    Low: "rgba(34,197,94,0.12)",
                  };
                  return (
                    <div
                      key={idx}
                      style={{
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.07)",
                        borderRadius: "10px",
                        padding: "0.9rem 1.1rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.4rem", flexWrap: "wrap" }}>
                        <span
                          style={{
                            background: "rgba(11,61,92,0.5)",
                            color: "#4cc9f0",
                            borderRadius: "50%",
                            width: "24px",
                            height: "24px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            flexShrink: 0,
                          }}
                        >
                          {step.step_number}
                        </span>
                        <strong style={{ fontSize: "0.95rem", flex: 1 }}>{step.action_title}</strong>
                        <span
                          style={{
                            fontSize: "0.7rem",
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: "99px",
                            background: urgencyBg[urgency],
                            color: urgencyColors[urgency],
                            border: `1px solid ${urgencyColors[urgency]}40`,
                          }}
                        >
                          {urgency.toUpperCase()}
                        </span>
                        {step.estimated_time && (
                          <span className="muted" style={{ fontSize: "0.72rem" }}>
                            ⏱ {step.estimated_time}
                          </span>
                        )}
                      </div>
                      {step.action_details && (
                        <p style={{ margin: "0.3rem 0", fontSize: "0.88rem", lineHeight: 1.55 }}>
                          {step.action_details}
                        </p>
                      )}
                      {step.reasoning && (
                        <p className="muted" style={{ fontSize: "0.8rem", margin: "0.25rem 0", fontStyle: "italic" }}>
                          Why: {step.reasoning}
                        </p>
                      )}
                      {step.spec_citation && (
                        <div
                          style={{
                            marginTop: "0.45rem",
                            fontSize: "0.72rem",
                            color: "#4cc9f0",
                            borderLeft: "2px solid #1F7A8C",
                            paddingLeft: "0.6rem",
                            fontFamily: "monospace",
                            wordBreak: "break-word",
                          }}
                        >
                          {step.spec_citation}
                          {step.spec_db_version && (
                            <span style={{ marginLeft: "0.5rem", opacity: 0.6 }}>
                              · {step.spec_db_version}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}


          <div className="wizard-actions">
            <button className="btn ghost" type="button" onClick={() => setStep("interview")}>
              Adjust answers
            </button>
            <button className="btn primary" type="button" onClick={pdf}>
              Download PDF report
            </button>
            <button className="btn ghost" type="button" onClick={restart}>
              New case
            </button>
          </div>

        </section>
      )}
    </div>
  );
}
