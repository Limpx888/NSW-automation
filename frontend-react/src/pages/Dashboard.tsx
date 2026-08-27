import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchHistory, fetchMeta } from "../lib/api";
import { FEATURES, pretty } from "../lib/content";

export default function Dashboard() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState<any>(null);
  const [cases, setCases] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetchMeta(), fetchHistory()])
      .then(([m, h]) => {
        setMeta(m);
        setCases(m.case_count ?? h.cases?.length ?? 0);
      })
      .catch(() => setError("Cannot reach the API on http://127.0.0.1:8000. Start uvicorn first."));
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      <p style={{ maxWidth: '800px', fontSize: '1.1rem' }}>
        <strong>AI Dispensing Defect Detective</strong> helps technicians find why a dispense went
        wrong and what to check first. It does not replace engineers.
      </p>
      {error && <div className="banner warn">{error}</div>}

      <div className="bento-grid" style={{ margin: "2rem 0" }}>
        <div className="card metric col-span-3">
          <b>{meta?.defect_classes?.length ?? "–"}</b>
          <span>Defect classes</span>
        </div>
        <div className="card metric col-span-3">
          <b>{meta?.materials?.length ?? "–"}</b>
          <span>Materials</span>
        </div>
        <div className="card metric col-span-3">
          <b>{cases}</b>
          <span>Cases in database</span>
        </div>
        <div className="card metric col-span-3">
          <b>{meta?.vision_ready ? "Ready" : "Heuristic"}</b>
          <span>Vision model</span>
        </div>

        <div className="card col-span-8">
          <h2>How it works</h2>
          <pre className="flow">{`[User symptom + optional photo]
        ↓
[Dynamic Q&A: 3–5 targeted follow-ups]
        ↓
[Reasoning engine: match the failure matrix]
        ↓
[Likelihood scoring + WHY chain]
        ↓
[Action plan + PDF]`}</pre>
          <ol className="muted" style={{ paddingLeft: "1.2rem", marginTop: '1rem' }}>
            <li style={{ marginBottom: '0.5rem' }}>Photo (optional) — vision labels the defect.</li>
            <li style={{ marginBottom: '0.5rem' }}>Guided Q&A — five dimensions, then only high-gain follow-ups.</li>
            <li style={{ marginBottom: '0.5rem' }}>Scoring — material×defect baseline + fuzzy symptom evidence.</li>
            <li>WHY — a reasoning chain, ranked causes, check-first plan.</li>
          </ol>
        </div>

        <div className="card col-span-4" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <h2>Not a chatbot</h2>
          <p>
            A small dot in UV glue is a viscosity/cure problem. The same look in Type 6 solder paste is
            a powder/nozzle clog.
          </p>
          <p className="muted">
            The app uses different cause tables per material and cites NSW:{" "}
            <strong style={{ color: 'var(--primary)' }}>nozzle ID ≥ 5× largest powder particle.</strong>
          </p>
        </div>

        <div className="card col-span-12">
          <h2>Judge demo</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem', alignItems: 'center', justifyContent: 'space-between' }}>
            <p style={{ maxWidth: '600px', margin: 0 }}>
              Type 6 solder paste, 60 µm nozzle (below the NSW 80 µm floor), continuous under-dispense
              after a nozzle change → expect the 5× rule and clog on top.
            </p>
            <button
              className="btn-primary"
              style={{ maxWidth: 300 }}
              onClick={() => navigate("/troubleshoot?demo=1")}
            >
              Load demo on Troubleshoot
            </button>
          </div>
          {meta && (
            <details style={{ marginTop: "2rem" }}>
              <summary>Scope covered</summary>
              <p><strong>Materials:</strong> {meta.materials.map(pretty).join(", ")}</p>
              <p><strong>Patterns:</strong> {meta.patterns.map(pretty).join(", ")}</p>
              <p><strong>Defects:</strong> {meta.defect_classes.map(pretty).join(", ")}</p>
              <p><strong>Demo images:</strong> {meta.sample_count}</p>
            </details>
          )}
        </div>

        {FEATURES.map((f, i) => (
          <div key={f.title} className="feature card col-span-4" style={{ animationDelay: `${i * 0.1}s` }}>
            <p className="kicker">
              {f.icon} {f.bonus}
            </p>
            <h3>{f.title}</h3>
            <p className="muted" style={{ margin: 0 }}>{f.desc}</p>
          </div>
        ))}

      </div>
    </div>
  );
}
