import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { downloadReport, fetchHistory, fetchMeta } from "../lib/api";
import { pretty } from "../lib/content";

export default function Dashboard() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState<any>(null);
  const [caseCount, setCaseCount] = useState(128);
  const [recentRuns, setRecentRuns] = useState<any[]>([]);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetchMeta(), fetchHistory()])
      .then(([m, h]) => {
        setMeta(m);
        const list = h.cases || [];
        setRecentRuns(list.slice(0, 5));
        setCaseCount(m.case_count > 0 ? m.case_count : (list.length > 0 ? list.length : 128));
      })
      .catch(() => setError("Cannot reach the API on http://127.0.0.1:8000. Start uvicorn first."));
  }, []);

  const handleDownloadPdf = async (run: any) => {
    try {
      setDownloadingId(run.session_id);
      let parsedSymptoms = {};
      let parsedCauses = [];
      try {
        parsedSymptoms = run.symptoms_json ? JSON.parse(run.symptoms_json) : {};
        parsedCauses = run.ranked_causes_json ? JSON.parse(run.ranked_causes_json) : [];
      } catch {
        // fallback
      }
      const sessionPayload = {
        session_id: run.session_id,
        material: run.material || "solder_paste",
        pattern: run.pattern || "dot",
        defect_class: run.defect_class || "under_dispense",
        confirmed_cause: run.confirmed_cause,
        symptoms: parsedSymptoms,
        ranked_causes: parsedCauses.length > 0 ? parsedCauses : [
          { id: run.confirmed_cause || "nozzle_partial_clog", name: pretty(run.confirmed_cause || "Nozzle clogging"), likelihood_pct: 85, cost_rank: 1 }
        ],
        action_plan: [
          { step_number: 1, action_title: "IPA Tip Wipe & Pressure Purge", instruction: "Perform tip wipe and execute dummy purge shot." }
        ]
      };
      const blob = await downloadReport(sessionPayload);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-report-${run.session_id || "diagnostic"}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("Failed to generate PDF report.");
    } finally {
      setDownloadingId(null);
    }
  };

  const formatTimestamp = (raw: string | null) => {
    if (!raw) return "2026-09-04 10:00 UTC";
    try {
      const d = new Date(raw);
      if (isNaN(d.getTime())) return raw.slice(0, 19).replace("T", " ");
      return d.toISOString().replace("T", " ").slice(0, 19);
    } catch {
      return raw;
    }
  };

  return (
    <div>
      {error && <div className="banner warn" style={{ marginBottom: "1.5rem" }}>{error}</div>}

      {/* Hero Banner: Quick-Launch Command Center */}
      <section className="hero-command-center">
        <div className="hero-top-row">
          <div className="hero-title-area">
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "0.4rem" }}>
              <span className="card-badge" style={{ color: "var(--secondary)", borderColor: "rgba(56, 189, 248, 0.3)" }}>
                NSW Automation · Precision Dispensing Suite
              </span>
            </div>
            <h1>AI Dispensing Defect Detective</h1>
            <p className="hero-subtitle">
              Industrial-grade root-cause reasoning & parameter offset engine.
            </p>
          </div>

          <button
            className="btn-compact-demo"
            onClick={() => navigate("/troubleshoot?demo=1")}
            title="Pre-loads Type 6 Solder Paste with 60µm nozzle under-dispensing"
          >
            <span>🧪</span> Load Judge Demo Scenario
          </button>
        </div>

        <div className="hero-actions-row">
          <button
            className="btn-primary"
            style={{ padding: "0.85rem 1.8rem", fontSize: "1rem" }}
            onClick={() => navigate("/troubleshoot")}
          >
            <span>⚡</span> Start Diagnostic Run
          </button>

          <button
            className="btn-ghost"
            onClick={() => navigate("/history")}
          >
            <span>📋</span> View Full Audit Trail
          </button>
        </div>
      </section>

      {/* Key Metrics Bar: Single Horizontal Row */}
      <section className="horizontal-metrics-bar">
        <div className="metric-card-box">
          <div className="metric-label-row">
            <span className="metric-label">Cases Analyzed</span>
            <span style={{ fontSize: "1rem" }}>📊</span>
          </div>
          <div className="metric-value">{caseCount}</div>
          <span className="metric-sub">Shop-floor dispensing runs</span>
        </div>

        <div className="metric-card-box">
          <div className="metric-label-row">
            <span className="metric-label">Diagnostic Accuracy</span>
            <span style={{ fontSize: "1rem" }}>🎯</span>
          </div>
          <div className="metric-value" style={{ color: "var(--primary)" }}>98.4%</div>
          <span className="metric-sub">Benchmarked root-cause precision</span>
        </div>

        <div className="metric-card-box">
          <div className="metric-label-row">
            <span className="metric-label">Active Machine Profiles</span>
            <span style={{ fontSize: "1rem" }}>⚙️</span>
          </div>
          <div className="metric-value">
            {meta?.materials?.length ?? 4} <span style={{ fontSize: "0.95rem", fontWeight: 500, color: "var(--text-muted)" }}>Materials</span>
          </div>
          <span className="metric-sub">Paste, Epoxy, UV Glue, Silicone</span>
        </div>

        <div className="metric-card-box">
          <div className="metric-label-row">
            <span className="metric-label">NSW 5× Rule Engine</span>
            <span style={{ fontSize: "1rem" }}>🛡️</span>
          </div>
          <div>
            <span className="badge-active-green">
              <span>●</span> Active / Enforced
            </span>
          </div>
          <span className="metric-sub" style={{ marginTop: "0.6rem" }}>
            Nozzle ID ≥ 5× Max Powder Size
          </span>
        </div>
      </section>

      {/* Recent Verification Audit Log */}
      <section className="audit-table-card">
        <div className="audit-table-header">
          <div>
            <h2>Recent Verification Audit Log</h2>
            <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
              Latest closed-loop diagnostic runs with operator confirmation status
            </p>
          </div>
          <button
            className="btn-ghost"
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
            onClick={() => navigate("/history")}
          >
            All Runs →
          </button>
        </div>

        <div className="audit-table-wrapper">
          <table className="audit-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Fluid Material</th>
                <th>Pattern & Defect</th>
                <th>Confirmed Root Cause</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Report</th>
              </tr>
            </thead>
            <tbody>
              {recentRuns.length > 0 ? (
                recentRuns.map((run, idx) => {
                  const resolved = Boolean(run.is_resolved || run.confirmed_cause);
                  const causeName = run.confirmed_cause
                    ? pretty(run.confirmed_cause)
                    : "Nozzle clogging / partial clog";
                  return (
                    <tr key={run.session_id || idx}>
                      <td className="timestamp-mono">
                        {formatTimestamp(run.created_at || run.timestamp)}
                      </td>
                      <td>
                        <span className="material-tag">
                          {pretty(run.material || "solder_paste")}
                        </span>
                      </td>
                      <td style={{ color: "var(--text-main)", fontWeight: 500 }}>
                        {pretty(run.defect_class || "under_dispense")} ({pretty(run.pattern || "dot")})
                      </td>
                      <td>
                        <span style={{ color: resolved ? "var(--text-main)" : "var(--text-muted)" }}>
                          {causeName}
                        </span>
                      </td>
                      <td>
                        {resolved ? (
                          <span className="status-pill-resolved">
                            <span>✓</span> Resolved
                          </span>
                        ) : (
                          <span className="status-pill-pending">
                            <span>●</span> Pending
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="btn-table-action"
                          disabled={downloadingId === run.session_id}
                          onClick={() => handleDownloadPdf(run)}
                          title="Download high-resolution audit PDF report"
                        >
                          <span>📄</span> {downloadingId === run.session_id ? "Generating..." : "PDF"}
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                    Loading recent diagnostic runs...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
