"""
Charts are rendered ONCE as PNG bytes here, then embedded as plain images
into both the DOCX and the PDF.
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backend.report.schemas import ReportData

NAVY = "#1B3A5F"
TEAL = "#2A9D8F"
AMBER = "#E9C46A"
SLATE = "#6C7A89"
CORAL = "#F4A261"
MUTED = "#8B96A5"
PALETTE = [NAVY, TEAL, AMBER, SLATE, CORAL, "#457B9D"]


def _fig_to_png_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_defect_donut(data: ReportData) -> bytes:
    if not data.defect_distribution:
        labels, values = ["Pass / No Defect"], [1.0]
    else:
        labels = [s.label for s in data.defect_distribution]
        values = [max(float(s.value), 0.01) for s in data.defect_distribution]

    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    colors = PALETTE[: len(labels)]
    wedges, _texts, autotexts = ax.pie(
        values,
        labels=None,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
        autopct=lambda pct: f"{pct:.0f}%" if pct >= 8 else "",
        pctdistance=0.75,
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(8)
        t.set_fontweight("bold")
    ax.legend(
        wedges,
        labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=8,
        frameon=False,
    )
    ax.set_title("Defect Distribution", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.text(
        0,
        0.05,
        str(data.detection_count),
        ha="center",
        va="center",
        fontsize=22,
        fontweight="bold",
        color=NAVY,
    )
    ax.text(0, -0.22, "regions", ha="center", va="center", fontsize=9, color=MUTED)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def render_analysis_bars(data: ReportData) -> bytes:
    if data.analysis_statistics:
        labels = [s.label for s in data.analysis_statistics]
        values = [float(s.value) for s in data.analysis_statistics]
    elif data.causes:
        labels = [c.name for c in data.causes[:5]]
        values = [float(c.score) for c in data.causes[:5]]
    else:
        labels, values = ["No data"], [0.0]

    fig, ax = plt.subplots(figsize=(4.4, 3.4))
    colors = PALETTE[: len(labels)]
    x = range(len(labels))
    bars = ax.bar(x, values, color=colors, width=0.62, edgecolor="white")
    ax.set_ylim(0, 100)
    ax.set_xticks(list(x))
    ax.set_xticklabels(
        [lbl if len(lbl) <= 14 else lbl[:12] + "…" for lbl in labels],
        fontsize=7,
        rotation=18,
        ha="right",
    )
    ax.set_ylabel("Score (%)", fontsize=8, color=MUTED)
    ax.set_title("Analysis Statistics", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", labelsize=8, colors=MUTED)
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.5,
            f"{val:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color=NAVY,
            fontweight="bold",
        )
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def render_cause_chart(data: ReportData) -> bytes:
    causes = sorted(data.causes, key=lambda c: c.score)
    fig, ax = plt.subplots(figsize=(6, 3))
    bars = ax.barh([c.name for c in causes], [c.score for c in causes], color=TEAL)
    ax.set_xlim(0, 100)
    ax.set_xlabel("AI Likelihood Score (%)")
    ax.spines[["top", "right"]].set_visible(False)
    for bar, cause in zip(bars, causes):
        ax.text(
            bar.get_width() + 2,
            bar.get_y() + bar.get_height() / 2,
            f"{cause.score}%",
            va="center",
            fontsize=9,
            color=MUTED,
        )
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def render_quality_donut(data: ReportData) -> bytes:
    fig, ax = plt.subplots(figsize=(3, 3))
    score = data.overall_quality_score
    ax.pie(
        [score, max(100 - score, 0.01)],
        colors=[TEAL, "#E7ECF1"],
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.32),
    )
    ax.text(0, 0, f"{score}", ha="center", va="center", fontsize=26, fontweight="bold", color=NAVY)
    ax.text(0, -0.28, "/ 100", ha="center", va="center", fontsize=11, color=MUTED)
    return _fig_to_png_bytes(fig)
