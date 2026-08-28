import { useEffect, useState } from "react";
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
      <p>Past troubleshooting sessions stored in SQLite.</p>
      {error && <div className="banner warn">{error}</div>}
      {cases.length === 0 && !error && (
        <div className="card">No cases logged yet. Run an analysis on the Troubleshoot page first.</div>
      )}
      <div className="bento-grid" style={{ marginTop: "1rem" }}>
        {cases.map((row) => (
          <article key={row.session_id || row.id} className="card col-span-4">
            <p className="kicker">{String(row.created_at || "").slice(0, 19)}</p>
            <h3>
              {pretty(row.material)} · {pretty(row.defect_class)}
            </h3>
            <p>
              <strong>Session:</strong> {row.session_id}
            </p>
            <p>
              <strong>Pattern:</strong> {pretty(row.pattern || "n/a")}
            </p>
            <p>
              <strong>Confirmed cause:</strong> {pretty(row.confirmed_cause || "not confirmed")}
            </p>
            {row.explanation && <p>{row.explanation}</p>}
          </article>
        ))}
      </div>
    </div>
  );
}
