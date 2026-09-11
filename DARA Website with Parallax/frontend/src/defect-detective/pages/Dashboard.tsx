import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchHistory, fetchMeta } from "../lib/api";
import { pretty } from "../lib/content";

export default function Dashboard() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState<any>(null);
  const [recent, setRecent] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetchMeta(), fetchHistory()])
      .then(([m, h]) => {
        setMeta(m);
        setRecent((h.cases || []).slice(0, 6));
      })
      .catch(() => setError("Cannot reach the API on http://127.0.0.1:8000. Start uvicorn first."));
  }, []);

  return (
    <div>
      {error && <div className="banner warn">{error}</div>}

      <section className="card highlight">
        <p className="eyebrow">NSW Automation · AI Horizon 2026</p>
        <h1>AI Dispensing Defect Detective</h1>
        <p className="lede">
          Workers pick the NSW pasting application first (solder paste, liquid metal, micro-dam, UV,
          silver epoxy, silicone/phosphor), then diagnose with a photo, questionnaire, or both.
        </p>
        <div className="wizard-actions" style={{ marginTop: "1rem" }}>
          <button className="btn primary" type="button" onClick={() => navigate("/troubleshoot")}>
            Start troubleshooting
          </button>
          <button className="btn ghost" type="button" onClick={() => navigate("/troubleshoot")}>
            Load judge demo from Troubleshoot
          </button>
        </div>
      </section>

      <div className="app-grid">
        <div className="card">
          <h3>Vision model</h3>
          <p className="muted">{meta?.vision_ready ? "MobileNetV2 checkpoint loaded" : "Heuristic fallback"}</p>
          <strong>{meta?.vision_ready ? "Ready" : "Not loaded"}</strong>
        </div>
        <div className="card">
          <h3>Applications</h3>
          <p className="muted">From NSW Application & Solutions</p>
          <strong>{meta?.applications?.length ?? 6}</strong>
        </div>
        <div className="card">
          <h3>Logged cases</h3>
          <p className="muted">SQLite shop-floor history</p>
          <strong>{meta?.case_count ?? recent.length}</strong>
        </div>
        <div className="card">
          <h3>NSW 5× rule</h3>
          <p className="muted">Nozzle ID vs powder particle size</p>
          <strong>Active</strong>
        </div>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Recent cases</h2>
          <button className="btn ghost" type="button" onClick={() => navigate("/history")}>
            View all
          </button>
        </div>
        {recent.length === 0 ? (
          <p className="muted">No cases yet — run a diagnosis from Troubleshoot.</p>
        ) : (
          <ul className="answer-list">
            {recent.map((c) => (
              <li key={c.session_id || c.id}>
                <span>
                  {pretty(c.material)} · {pretty(c.defect_class)}
                </span>
                <strong>{pretty(c.confirmed_cause || c.top_cause || "open")}</strong>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
