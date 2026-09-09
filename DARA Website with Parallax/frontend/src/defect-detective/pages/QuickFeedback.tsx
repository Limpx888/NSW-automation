import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchCaseBySession, postCaseFeedback } from "../lib/api";
import { pretty } from "../lib/content";

export default function QuickFeedback() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id") || "";

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [caseData, setCaseData] = useState<any>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  // Form states
  const [status, setStatus] = useState<"RESOLVED" | "UNRESOLVED">("RESOLVED");
  const [selectedCause, setSelectedCause] = useState<string>("");
  const [customCause, setCustomCause] = useState<string>("");
  const [operatorNotes, setOperatorNotes] = useState<string>("");

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    (async () => {
      try {
        setLoading(true);
        setError("");
        const data = await fetchCaseBySession(sessionId);
        if (isMounted) {
          setCaseData(data);
          // Pre-select top ranked cause or existing confirmed cause
          const topCause = data.confirmed_cause || data.ranked_causes?.[0]?.id || "";
          setSelectedCause(topCause);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Failed to load case session.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [sessionId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId) return;

    const finalCause = selectedCause === "custom" ? customCause.trim() : selectedCause;
    if (!finalCause) {
      setError("Please select or enter the confirmed root cause.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await postCaseFeedback({
        session_id: sessionId,
        status,
        confirmed_cause: finalCause,
        operator_notes: operatorNotes.trim(),
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Failed to submit resolution feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!sessionId) {
    return (
      <div style={{ maxWidth: "600px", margin: "3rem auto", padding: "1.5rem" }}>
        <div className="card" style={{ textAlign: "center", padding: "3rem 2rem" }}>
          <div style={{ fontSize: "3.5rem", marginBottom: "1rem" }}>📱</div>
          <h2 style={{ color: "var(--primary)", marginBottom: "0.75rem" }}>Scan QR Code from Report</h2>
          <p className="muted" style={{ marginBottom: "2rem" }}>
            This page is designed for mobile shop-floor verification. Please scan the QR code located on the top-right header of your printed maintenance sheet.
          </p>
          <Link to="/troubleshoot" className="btn-primary" style={{ display: "inline-block" }}>
            Go to Troubleshooter
          </Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ maxWidth: "600px", margin: "3rem auto", textAlign: "center", padding: "2rem" }}>
        <div style={{ fontSize: "2rem", marginBottom: "1rem", animation: "spin 1s linear infinite" }}>🔄</div>
        <p className="muted">Retrieving diagnostic session #{sessionId.slice(0, 8)}…</p>
      </div>
    );
  }

  if (success) {
    return (
      <div style={{ maxWidth: "600px", margin: "3rem auto", padding: "1.5rem" }}>
        <div className="card" style={{ textAlign: "center", padding: "3rem 2rem", borderTop: "4px solid var(--success)" }}>
          <div style={{ fontSize: "3.5rem", marginBottom: "1rem" }}>🎉</div>
          <h2 style={{ color: "var(--success)", marginBottom: "0.5rem" }}>Resolution Recorded!</h2>
          <p style={{ fontSize: "1.05rem", marginBottom: "1.5rem" }}>
            Thank you for verifying on-site. Verified ground-truth data has been fed into the SQLite knowledge database.
          </p>
          <div style={{ background: "rgba(255,255,255,0.03)", padding: "1rem", borderRadius: "10px", textAlign: "left", marginBottom: "2rem" }}>
            <p style={{ margin: "0 0 0.4rem 0" }}><strong>Status:</strong> <span style={{ color: "var(--success)" }}>{status}</span></p>
            <p style={{ margin: "0 0 0.4rem 0" }}><strong>Confirmed Root Cause:</strong> {pretty(selectedCause === "custom" ? customCause : selectedCause)}</p>
            {operatorNotes && <p style={{ margin: 0 }}><strong>Notes:</strong> {operatorNotes}</p>}
          </div>
          <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
            <Link to="/history" className="btn-primary">
              View Audit History
            </Link>
            <Link to="/troubleshoot" className="btn-ghost">
              New Inspection
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const causesList = caseData?.ranked_causes || [];

  return (
    <div style={{ maxWidth: "620px", margin: "1.5rem auto", padding: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.25rem" }}>
        <span style={{ fontSize: "1.8rem" }}>📋</span>
        <div>
          <h1 style={{ fontSize: "1.4rem", margin: 0, color: "var(--primary)" }}>
            Shop-Floor Maintenance Feedback
          </h1>
          <span className="muted" style={{ fontSize: "0.8rem" }}>
            Session ID: {sessionId.slice(0, 16)}...
          </span>
        </div>
      </div>

      {error && <div className="banner warn" style={{ marginBottom: "1rem" }}>{error}</div>}

      {/* Case Summary Card */}
      <div className="card" style={{ marginBottom: "1.25rem", padding: "1.25rem", background: "rgba(20,20,35,0.6)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
          <div>
            <span className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase" }}>Material</span>
            <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{pretty(caseData?.material || "Unknown")}</div>
          </div>
          <div>
            <span className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase" }}>Pattern</span>
            <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{pretty(caseData?.pattern || "Unknown")}</div>
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <span className="muted" style={{ fontSize: "0.75rem", textTransform: "uppercase" }}>Defect Classification</span>
            <div style={{ fontWeight: 700, fontSize: "1rem", color: "var(--primary)" }}>
              {pretty(caseData?.defect_class || "Inspection")}
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Mobile Feedback Form */}
      <form onSubmit={handleSubmit} className="card" style={{ display: "flex", flexDirection: "column", gap: "1.4rem" }}>
        {/* 1. Maintenance Status */}
        <div>
          <label style={{ display: "block", fontWeight: 700, marginBottom: "0.6rem", fontSize: "0.95rem" }}>
            1. Machine Maintenance Outcome
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <button
              type="button"
              className="btn-feedback"
              style={{
                padding: "1rem",
                borderRadius: "10px",
                border: status === "RESOLVED" ? "2px solid var(--success)" : "1px solid var(--glass-border)",
                background: status === "RESOLVED" ? "rgba(0, 255, 170, 0.15)" : "rgba(255,255,255,0.03)",
                color: status === "RESOLVED" ? "var(--success)" : "var(--text-muted)",
                fontWeight: 700,
                fontSize: "0.9rem",
                cursor: "pointer",
              }}
              onClick={() => setStatus("RESOLVED")}
            >
              🟢 Successfully Resolved
            </button>
            <button
              type="button"
              className="btn-feedback"
              style={{
                padding: "1rem",
                borderRadius: "10px",
                border: status === "UNRESOLVED" ? "2px solid var(--danger)" : "1px solid var(--glass-border)",
                background: status === "UNRESOLVED" ? "rgba(255, 51, 102, 0.15)" : "rgba(255,255,255,0.03)",
                color: status === "UNRESOLVED" ? "var(--danger)" : "var(--text-muted)",
                fontWeight: 700,
                fontSize: "0.9rem",
                cursor: "pointer",
              }}
              onClick={() => setStatus("UNRESOLVED")}
            >
              🔴 Unresolved / Escalated
            </button>
          </div>
        </div>

        {/* 2. Confirmed True Root Cause */}
        <div>
          <label style={{ display: "block", fontWeight: 700, marginBottom: "0.6rem", fontSize: "0.95rem" }}>
            2. Confirmed True Root Cause (Ground-Truth)
          </label>
          <p className="muted" style={{ fontSize: "0.8rem", marginTop: "-0.3rem", marginBottom: "0.75rem" }}>
            Select what actually solved the problem on the machine floor:
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            {causesList.map((c: any) => {
              const isSelected = selectedCause === c.id;
              return (
                <label
                  key={c.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.75rem",
                    padding: "0.85rem 1rem",
                    borderRadius: "8px",
                    background: isSelected ? "rgba(0, 240, 255, 0.1)" : "rgba(255,255,255,0.03)",
                    border: isSelected ? "1px solid var(--primary)" : "1px solid var(--glass-border)",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  <input
                    type="radio"
                    name="confirmed_cause"
                    value={c.id}
                    checked={isSelected}
                    onChange={() => setSelectedCause(c.id)}
                    style={{ accentColor: "var(--primary)", width: "18px", height: "18px" }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{c.name}</div>
                    <span className="muted" style={{ fontSize: "0.75rem" }}>AI Diagnostic Likelihood: {c.likelihood_pct}%</span>
                  </div>
                </label>
              );
            })}

            {/* Custom Cause Option */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.85rem 1rem",
                borderRadius: "8px",
                background: selectedCause === "custom" ? "rgba(0, 240, 255, 0.1)" : "rgba(255,255,255,0.03)",
                border: selectedCause === "custom" ? "1px solid var(--primary)" : "1px solid var(--glass-border)",
                cursor: "pointer",
              }}
            >
              <input
                type="radio"
                name="confirmed_cause"
                value="custom"
                checked={selectedCause === "custom"}
                onChange={() => setSelectedCause("custom")}
                style={{ accentColor: "var(--primary)", width: "18px", height: "18px" }}
              />
              <div style={{ flex: 1, fontWeight: 600, fontSize: "0.9rem" }}>
                Other / Unlisted Root Cause
              </div>
            </label>

            {selectedCause === "custom" && (
              <input
                type="text"
                className="input"
                placeholder="Enter root cause (e.g. Broken syringe heater cable)"
                value={customCause}
                onChange={(e) => setCustomCause(e.target.value)}
                style={{ marginTop: "0.25rem", background: "rgba(0,0,0,0.4)" }}
                required
              />
            )}
          </div>
        </div>

        {/* 3. Operator Repair Notes */}
        <div>
          <label style={{ display: "block", fontWeight: 700, marginBottom: "0.4rem", fontSize: "0.95rem" }}>
            3. Technician Action Notes (Optional)
          </label>
          <textarea
            className="input"
            rows={3}
            placeholder="e.g. Swapped to 80µm gauge nozzle, executed 2s purge, dot diameter returned to nominal."
            value={operatorNotes}
            onChange={(e) => setOperatorNotes(e.target.value)}
            style={{ width: "100%", resize: "vertical", fontSize: "0.85rem", background: "rgba(0,0,0,0.4)" }}
          />
        </div>

        {/* Submit */}
        <button
          type="submit"
          className="btn-primary"
          disabled={submitting}
          style={{ width: "100%", padding: "1.1rem", fontSize: "1rem", fontWeight: 700 }}
        >
          {submitting ? "Writing Ground-Truth to DB…" : "✅ Confirm Resolution & Update Knowledge DB"}
        </button>
      </form>
    </div>
  );
}
