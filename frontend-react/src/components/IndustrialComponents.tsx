// Industrial Design Components Library
// Reusable components for the NSW Automation AI Dispensing Defect Detective

import { useState } from "react";
import { motion } from "framer-motion";

// Status Pill Component
export const StatusPill = ({ status, label }: { status: "healthy" | "attention" | "critical"; label: string }) => {
  const statusStyles = {
    healthy: "bg-green-950 text-green-300 border-green-800",
    attention: "bg-yellow-950 text-yellow-300 border-yellow-800",
    critical: "bg-red-950 text-red-300 border-red-800",
  };

  return (
    <span className={`status-pill ${status} ${statusStyles[status]}`}>
      {label}
    </span>
  );
};

// NSW 5X Nozzle Gauge Component
export const NozzleGauge = ({ particleSize, nozzleSize }: { particleSize: number; nozzleSize: number }) => {
  const ratio = nozzleSize / particleSize;
  const isCompliant = ratio >= 5;

  return (
    <div className="nozzle-gauge">
      <div className="gauge-metric">
        <span className="gauge-metric-label">Particle Size</span>
        <span className="gauge-metric-value">{particleSize} µm</span>
      </div>
      <div className="gauge-metric">
        <span className="gauge-metric-label">Nozzle Diameter</span>
        <span className="gauge-metric-value">{nozzleSize} µm</span>
      </div>
      <div className="gauge-metric">
        <span className="gauge-metric-label">Ratio</span>
        <div>
          <span className="gauge-metric-value">{ratio.toFixed(1)}×</span>
          <span className={`gauge-status-indicator ${isCompliant ? "" : "warning"}`}>
            {isCompliant ? "✓ Compliant" : "⚠ Undersized"}
          </span>
        </div>
      </div>
    </div>
  );
};

// Root Causes List Component
export const RankedCausesList = ({ 
  causes, 
  openCause, 
  onSelectCause 
}: { 
  causes: any[]; 
  openCause: string | null; 
  onSelectCause: (id: string) => void 
}) => {
  return (
    <div className="causes-list">
      {(causes || []).slice(0, 6).map((cause: any, idx: number) => (
        <motion.button
          key={cause.id}
          className={`cause-item ${idx === 0 ? "top" : ""}`}
          onClick={() => onSelectCause(openCause === cause.id ? "" : cause.id)}
          whileHover={{ x: 4 }}
        >
          <div className="cause-rank-header">
            <span className="text-xs text-text-secondary font-mono">#{idx + 1}</span>
            <span className="cause-rank-title">{cause.name}</span>
            <span className="cause-probability">{Math.round(cause.likelihood_pct || 0)}%</span>
          </div>
          <div className="cause-progress-bar">
            <div 
              className="cause-progress-fill"
              style={{ width: `${cause.likelihood_pct || 0}%` }}
            />
          </div>
          {openCause === cause.id && (
            <motion.p 
              className="text-sm text-text-secondary mt-2"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
            >
              {cause.check || cause.why || "Inspect and verify on the line."}
            </motion.p>
          )}
        </motion.button>
      ))}
    </div>
  );
};

// Counter-Test Card Component
export const CounterTestCard = ({
  test,
  onFeedback,
  disabled
}: {
  test: any;
  onFeedback: (feedback: "resolved" | "unresolved" | "shifted") => void;
  disabled?: boolean;
}) => {
  return (
    <motion.div 
      className="counter-test-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="counter-test-header">
        <div>
          <h3 className="counter-test-name">{test.title || test.action_title}</h3>
          <p className="text-xs text-text-secondary mt-1">{test.instruction || test.description}</p>
        </div>
      </div>
      
      {test.roi_score && (
        <div className={`roi-badge ${test.roi_score >= 0.3 ? "" : "medium"}`}>
          ROI: {test.roi_score.toFixed(2)}
        </div>
      )}

      <div className="counter-test-actions">
        <button
          className="counter-test-btn pass"
          onClick={() => onFeedback("resolved")}
          disabled={disabled}
        >
          ✓ Resolved
        </button>
        <button
          className="counter-test-btn"
          onClick={() => onFeedback("shifted")}
          disabled={disabled}
        >
          ↻ Shifted
        </button>
        <button
          className="counter-test-btn"
          onClick={() => onFeedback("unresolved")}
          disabled={disabled}
        >
          ✗ Unresolved
        </button>
      </div>
    </motion.div>
  );
};

// Explainable AI Accordion Component
export const XAIAccordion = ({ explanation, evidence }: { explanation: string; evidence?: any[] }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div className="xai-accordion">
      <div className="xai-item">
        <motion.button
          className="xai-trigger"
          onClick={() => setExpanded(!expanded)}
        >
          <span>Why this root cause?</span>
          <motion.span
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            ▼
          </motion.span>
        </motion.button>
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: expanded ? "auto" : 0, opacity: expanded ? 1 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <div className="xai-content">
            <p className="mb-3">{explanation}</p>
            {evidence && evidence.length > 0 && (
              <div className="xai-evidence-tree">
                <p className="text-xs font-semibold text-text-secondary mb-2">Evidence:</p>
                {evidence.map((item, i) => (
                  <div key={i} className="xai-evidence-item">
                    <span>{item.rule || item.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};

// Pipeline Loader Component
export const PipelineLoader = () => {
  const steps = [
    "Running Vision Pipeline...",
    "Computing Rheology Offset...",
    "Ranking Root Causes...",
  ];

  return (
    <div className="pipeline-loader">
      {steps.map((step, i) => (
        <motion.div
          key={i}
          className="pipeline-step"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.2 }}
        >
          <div className="pipeline-step-number">{i + 1}</div>
          <span className="pipeline-step-text">{step}</span>
          {i === steps.length - 1 && (
            <motion.div className="pipeline-step-spinner" />
          )}
        </motion.div>
      ))}
    </div>
  );
};
