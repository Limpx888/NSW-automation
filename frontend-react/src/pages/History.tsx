import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchHistory } from "../lib/api";
import { pretty } from "../lib/content";

export default function HistoryPage() {
  const [cases, setCases] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchHistory()
      .then((res) => setCases(res.cases || []))
      .catch(() => setError("Cannot load history. Is the API running on port 8000?"));
  }, []);

  return (
    <div>
      <h1>Case history</h1>
      <p>Past troubleshooting sessions and ground-truth verified resolutions stored in SQLite.</p>
      {error && <div className="banner warn">{error}</div>}
      {cases.length === 0 && !error && (
        <div className="card">No cases logged yet. Run an analysis on the Troubleshoot page first.</div>
      )}
      <div className="bento-grid" style={{ marginTop: "1rem" }}>
        {cases.map((row) => (
          <article key={row.session_id || row.id} className="card col-span-4" style={{ position: "relative" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
              <p className="kicker" style={{ margin: 0 }}>{String(row.created_at || "").slice(0, 19)}</p>
              {row.is_resolved ? (
                <span style={{ fontSize: "0.75rem", background: "rgba(0, 255, 170, 0.15)", color: "var(--success)", border: "1px solid rgba(0, 255, 170, 0.3)", padding: "2px 8px", borderRadius: "12px", fontWeight: 700 }}>
                  ✓ Ground-Truth Verified
                </span>
              ) : (
                <span style={{ fontSize: "0.75rem", background: "rgba(255, 255, 255, 0.05)", color: "var(--text-muted)", padding: "2px 8px", borderRadius: "12px" }}>
                  Diagnostic
                </span>
              )}
            </div>

            <h3>
              {pretty(row.material)} · {pretty(row.defect_class)}
            </h3>
            <p>
              <strong>Session:</strong> <code style={{ fontSize: "0.8rem" }}>{String(row.session_id || "").slice(0, 14)}...</code>
            </p>
            <p>
              <strong>Pattern:</strong> {pretty(row.pattern || "n/a")}
            </p>
            <p>
              <strong>Confirmed cause:</strong>{" "}
              <span style={{ color: row.confirmed_cause ? "var(--primary)" : "inherit", fontWeight: row.confirmed_cause ? 600 : 400 }}>
                {pretty(row.confirmed_cause || "Pending confirmation")}
              </span>
            </p>
            {row.operator_notes && (
              <p style={{ background: "rgba(0,0,0,0.3)", padding: "0.5rem 0.75rem", borderRadius: "6px", fontSize: "0.85rem", margin: "0.5rem 0" }}>
                <strong>📝 Shop-floor notes:</strong> {row.operator_notes}
              </p>
            )}
            {row.explanation && <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>{row.explanation}</p>}

            <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid var(--glass-border)", display: "flex", justifyContent: "space-between" }}>
              <Link to={`/quick-feedback?session_id=${row.session_id}`} style={{ fontSize: "0.85rem", color: "var(--primary)", textDecoration: "none", fontWeight: 600 }}>
                📱 Open Mobile Sheet ➔
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
