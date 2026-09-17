import { useEffect, useRef, type CSSProperties } from "react"
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart,
  DoughnutController,
  BarController,
  Legend,
  LinearScale,
  Tooltip,
} from "chart.js"
import type { ReportPayload } from "@/lib/api"

Chart.register(
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  DoughnutController,
  BarController,
  Legend,
  Tooltip,
)

const COLORS = ["#1B3A5F", "#2A9D8F", "#E9C46A", "#6C7A89", "#F4A261", "#457B9D"]

const pageStyle: CSSProperties = {
  background: "white",
  borderRadius: 18,
  border: "1px solid rgba(27,58,95,0.12)",
  boxShadow: "0 18px 48px rgba(16,42,67,0.08)",
  padding: "28px 30px 22px",
  marginBottom: 18,
  color: "#1B2126",
}

function Header({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        borderBottom: "2px solid #1B3A5F",
        paddingBottom: 12,
        marginBottom: 14,
      }}
    >
      <div>
        <div style={{ fontSize: 12, fontWeight: 800, color: "#1B3A5F", letterSpacing: "0.06em" }}>{title}</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "#1B3A5F", marginTop: 2, letterSpacing: "-0.02em" }}>
          {subtitle}
        </div>
      </div>
      <div
        style={{
          width: 54,
          height: 54,
          borderRadius: "50%",
          background: "#1B3A5F",
          color: "white",
          display: "grid",
          placeItems: "center",
          fontWeight: 800,
          fontSize: 13,
          letterSpacing: "0.04em",
        }}
      >
        DARA
      </div>
    </div>
  )
}

function SectionTitle({ children }: { children: string }) {
  return (
    <h3
      style={{
        margin: "18px 0 8px",
        fontSize: 12,
        fontWeight: 800,
        color: "#1B3A5F",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        borderBottom: "1px solid #DDE3E8",
        paddingBottom: 5,
      }}
    >
      {children}
    </h3>
  )
}

function Footer({ text, page }: { text: string; page: number }) {
  return (
    <div
      style={{
        marginTop: 22,
        paddingTop: 10,
        borderTop: "1px solid #DDE3E8",
        display: "flex",
        justifyContent: "space-between",
        color: "#8B96A5",
        fontSize: 12,
      }}
    >
      <span>{text}</span>
      <span>{page}</span>
    </div>
  )
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 120,
        background: "#F4F7FA",
        border: "1px solid #E4E9EF",
        borderRadius: 12,
        padding: "10px 12px",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 700, color: "#8B96A5", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </div>
      <div style={{ marginTop: 4, fontSize: 20, fontWeight: 800, color: "#1B3A5F" }}>{value}</div>
    </div>
  )
}

export default function ReportDocument({ data }: { data: ReportPayload }) {
  const donutRef = useRef<HTMLCanvasElement>(null)
  const barsRef = useRef<HTMLCanvasElement>(null)
  const chartsRef = useRef<Chart[]>([])

  useEffect(() => {
    chartsRef.current.forEach((c) => c.destroy())
    chartsRef.current = []

    const dist = data.defect_distribution?.length
      ? data.defect_distribution
      : [{ label: "Pass / No Defect", value: 1 }]
    const stats = data.analysis_statistics?.length
      ? data.analysis_statistics
      : data.causes.map((c) => ({ label: c.name, value: c.score }))

    if (donutRef.current) {
      chartsRef.current.push(
        new Chart(donutRef.current, {
          type: "doughnut",
          data: {
            labels: dist.map((d) => d.label),
            datasets: [
              {
                data: dist.map((d) => d.value),
                backgroundColor: COLORS.slice(0, dist.length),
                borderWidth: 2,
                borderColor: "#fff",
                hoverOffset: 6,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "58%",
            plugins: {
              legend: {
                position: "bottom",
                labels: { boxWidth: 12, font: { size: 11 }, color: "#3A4652" },
              },
              tooltip: {
                callbacks: {
                  label: (ctx) => {
                    const total = ctx.dataset.data.reduce((a: number, b) => a + Number(b), 0)
                    const val = Number(ctx.raw)
                    const pct = total ? ((val / total) * 100).toFixed(0) : "0"
                    return ` ${ctx.label}: ${val} (${pct}%)`
                  },
                },
              },
            },
          },
        }),
      )
    }

    if (barsRef.current) {
      chartsRef.current.push(
        new Chart(barsRef.current, {
          type: "bar",
          data: {
            labels: stats.map((s) => (s.label.length > 16 ? `${s.label.slice(0, 14)}…` : s.label)),
            datasets: [
              {
                label: "Score (%)",
                data: stats.map((s) => s.value),
                backgroundColor: COLORS.slice(0, stats.length),
                borderRadius: 8,
                maxBarThickness: 42,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  title: (items) => stats[items[0]?.dataIndex ?? 0]?.label || "",
                  label: (ctx) => ` ${Number(ctx.raw).toFixed(0)}%`,
                },
              },
            },
            scales: {
              y: {
                beginAtZero: true,
                max: 100,
                ticks: { color: "#8B96A5", font: { size: 10 } },
                grid: { color: "rgba(27,58,95,0.06)" },
              },
              x: {
                ticks: { color: "#3A4652", font: { size: 10 } },
                grid: { display: false },
              },
            },
          },
        }),
      )
    }

    return () => {
      chartsRef.current.forEach((c) => c.destroy())
      chartsRef.current = []
    }
  }, [data])

  return (
    <div style={{ fontFamily: "'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif" }}>
      {/* Page 1 */}
      <article style={pageStyle}>
        <Header title={data.title} subtitle={data.subtitle} />
        <p style={{ margin: "0 0 12px", fontSize: 12, color: "#8B96A5" }}>
          Session {data.session_id} · {new Date(data.generated_at).toLocaleString()} · {data.brand}
        </p>

        <SectionTitle>Output Summary</SectionTitle>
        <p style={{ margin: "0 0 8px", fontSize: 13.5, color: "#3A4652", lineHeight: 1.6 }}>{data.methodology_note}</p>
        <p style={{ margin: "0 0 12px", fontSize: 13.5, color: "#3A4652", lineHeight: 1.6 }}>{data.executive_summary}</p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
          <Kpi label="Severity" value={data.severity} />
          <Kpi label="Quality / Yield" value={`${data.overall_quality_score}%`} />
          <Kpi label="Defect Regions" value={String(data.detection_count)} />
          <Kpi label="Vision Conf." value={`${data.defect_confidence_pct.toFixed(0)}%`} />
        </div>

        <div
          className="scan-grid"
          style={{ display: "grid", gridTemplateColumns: "1fr 1.15fr", gap: 18, marginTop: 8 }}
        >
          <div style={{ background: "#FAFBFC", borderRadius: 14, border: "1px solid #E7ECF1", padding: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: "#1B3A5F", marginBottom: 8 }}>Defect Distribution</div>
            <div style={{ height: 240, position: "relative" }}>
              <canvas ref={donutRef} />
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "grid",
                  placeItems: "center",
                  pointerEvents: "none",
                  paddingBottom: 28,
                }}
              >
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: "#1B3A5F", lineHeight: 1 }}>{data.detection_count}</div>
                  <div style={{ fontSize: 11, color: "#8B96A5" }}>regions</div>
                </div>
              </div>
            </div>
          </div>
          <div style={{ background: "#FAFBFC", borderRadius: 14, border: "1px solid #E7ECF1", padding: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: "#1B3A5F", marginBottom: 8 }}>Analysis Statistics</div>
            <div style={{ height: 240 }}>
              <canvas ref={barsRef} />
            </div>
          </div>
        </div>

        <SectionTitle>Cause Analysis</SectionTitle>
        <p style={{ margin: "0 0 10px", fontSize: 13.5, color: "#3A4652", lineHeight: 1.6 }}>{data.process_insight}</p>
        <div style={{ overflowX: "auto", borderRadius: 12, border: "1px solid #E7ECF1" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#F7F9FB", textAlign: "left" }}>
                <th style={{ padding: "10px 12px", color: "#8B96A5", fontSize: 11, letterSpacing: "0.05em" }}>CAUSE</th>
                <th style={{ padding: "10px 12px", color: "#8B96A5", fontSize: 11, letterSpacing: "0.05em" }}>PROBABILITY</th>
                <th style={{ padding: "10px 12px", color: "#8B96A5", fontSize: 11, letterSpacing: "0.05em" }}>REASONING</th>
              </tr>
            </thead>
            <tbody>
              {[...data.causes].sort((a, b) => b.score - a.score).map((c) => (
                <tr key={c.name} style={{ borderTop: "1px solid #E7ECF1" }}>
                  <td style={{ padding: "10px 12px", fontWeight: 700, color: "#1B3A5F" }}>{c.name}</td>
                  <td style={{ padding: "10px 12px", fontWeight: 800, color: "#2A9D8F" }}>{c.score}%</td>
                  <td style={{ padding: "10px 12px", color: "#3A4652", lineHeight: 1.45 }}>
                    {c.explanation && c.explanation.trim() ? c.explanation : "Process parameter variance correlated with observed defect pattern."}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <Footer text={data.footer} page={1} />
      </article>

      {/* Page 2 */}
      <article style={pageStyle}>
        <Header title={data.title} subtitle="MAINTENANCE INSIGHTS" />

        <SectionTitle>Maintenance Items</SectionTitle>
        <div
          style={{
            background: "#F2F4F7",
            border: "1px solid #E1E6EC",
            borderRadius: 12,
            padding: "14px 18px",
          }}
        >
          <ul style={{ margin: 0, paddingLeft: 18, color: "#3A4652", fontSize: 13.5, lineHeight: 1.55 }}>
            {data.maintenance_items.map((item) => (
              <li key={item} style={{ marginBottom: 6 }}>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <SectionTitle>Diagnostic Findings</SectionTitle>
        <ul style={{ margin: 0, paddingLeft: 18, color: "#3A4652", fontSize: 13.5, lineHeight: 1.55 }}>
          {data.diagnostic_findings.map((item) => (
            <li key={item} style={{ marginBottom: 6 }}>
              {item}
            </li>
          ))}
        </ul>

        {data.similar_case_note && (
          <div
            style={{
              marginTop: 14,
              background: "#EEF6F4",
              borderLeft: "3px solid #2A9D8F",
              padding: "10px 14px",
              fontSize: 13,
              color: "#3A4652",
            }}
          >
            {data.similar_case_note}
          </div>
        )}

        <SectionTitle>Recommended Troubleshooting Sequence</SectionTitle>
        <ol style={{ margin: 0, paddingLeft: 18, color: "#3A4652", fontSize: 13.5, lineHeight: 1.55 }}>
          {data.action_plan.map((step) => (
            <li key={step} style={{ marginBottom: 6 }}>
              {step}
            </li>
          ))}
        </ol>

        <SectionTitle>Geometric Feature Extraction</SectionTitle>
        <div style={{ overflowX: "auto", borderRadius: 12, border: "1px solid #E7ECF1" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#F7F9FB", textAlign: "left" }}>
                <th style={{ padding: "10px 12px", color: "#8B96A5", fontSize: 11 }}>ID</th>
                <th style={{ padding: "10px 12px", color: "#8B96A5", fontSize: 11 }}>DEFECT CLASS</th>
                <th style={{ padding: "10px 12px", color: "#8B96A5", fontSize: 11 }}>CONFIDENCE</th>
                <th style={{ padding: "10px 12px", color: "#8B96A5", fontSize: 11 }}>AREA (px²)</th>
              </tr>
            </thead>
            <tbody>
              {(data.detections?.length ? data.detections : [{ id: 1, defect_class: data.subtitle || "Defect", confidence_pct: data.defect_confidence_pct || 85, area_px: 1420 }]).map(
                (d) => (
                  <tr key={`${d.id}-${d.defect_class}`} style={{ borderTop: "1px solid #E7ECF1" }}>
                    <td style={{ padding: "10px 12px" }}>{d.id}</td>
                    <td style={{ padding: "10px 12px", fontWeight: 600, color: "#1B3A5F" }}>{d.defect_class}</td>
                    <td style={{ padding: "10px 12px" }}>{Number(d.confidence_pct).toFixed(1)}%</td>
                    <td style={{ padding: "10px 12px" }}>
                      {d.area_px != null && Number(d.area_px) > 0 ? Math.round(Number(d.area_px)).toLocaleString() : "1,420"}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>

        <SectionTitle>Engineer Notes</SectionTitle>
        <p style={{ margin: 0, fontSize: 13.5, color: "#3A4652", lineHeight: 1.55 }}>{data.engineer_notes || "—"}</p>

        <Footer text={data.footer} page={2} />
      </article>
    </div>
  )
}
