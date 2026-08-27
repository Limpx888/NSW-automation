"""SQLite case log and similar-case lookup (Bonus 3)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "cases.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    material TEXT,
    pattern TEXT,
    defect_class TEXT,
    symptoms_json TEXT,
    ranked_causes_json TEXT,
    confirmed_cause TEXT,
    explanation TEXT,
    created_at TEXT NOT NULL
);
"""

SEED = [
    ("solder_paste", "dot", "under_dispense", "powder_nozzle_mismatch", "T6 through 60 um nozzle"),
    ("solder_paste", "dot", "under_dispense", "nozzle_partial_clog", "Continuous undersize after 2 hours"),
    ("solder_paste", "dot", "inconsistent_volume", "air_trapped_syringe", "Occasional small/large dots"),
    ("solder_paste", "line", "missing", "nozzle_partial_clog", "Line skips on T5"),
    ("solder_paste", "dot", "air_bubble_irregular", "stringing_satellites", "Satellites on retract"),
    ("solder_paste", "dot", "over_dispense", "pressure_time_high", "Pressure bumped after changeover"),
    ("solder_paste", "dot", "spreading", "viscosity_temp_humidity", "Booth ran warm, T3 paste slumped"),
    ("uv_glue", "dot", "under_dispense", "premature_uv_cure", "Clear syringe, gelled tip"),
    ("uv_glue", "dam_fill", "spreading", "viscosity_temp_humidity", "Dam collapse, low-viscosity UV"),
    ("uv_glue", "line", "air_bubble_irregular", "piston_suckback", "Excess vacuum suck-back"),
    ("uv_glue", "dot", "missing", "premature_uv_cure", "Started good, died after runtime"),
    ("silver_epoxy", "dot", "inconsistent_volume", "filler_settling", "Syringe not rolled"),
    ("silver_epoxy", "dot", "under_dispense", "nozzle_partial_clog", "Filled epoxy, small tip"),
    ("silver_epoxy", "line", "missing", "filler_settling", "Settled silver blocked path"),
    ("silicone_gel", "dam_fill", "spreading", "dam_flow_geometry", "Dam path too fast"),
    ("silicone_gel", "dam_fill", "air_bubble_irregular", "air_trapped_syringe", "Void in fill"),
    ("silicone_gel", "line", "over_dispense", "pressure_time_high", "Bead flooded pad"),
    ("silicone_gel", "dot", "inconsistent_volume", "viscosity_temp_humidity", "Gel thinned as valve warmed"),
    ("solder_paste", "line", "under_dispense", "flux_metal_separation", "Syringe stored tip-up"),
    ("solder_paste", "dam_fill", "missing", "z_gap_wrong", "Z too high, paste did not wet"),
]


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def seed_if_empty(db_path: Path | None = None) -> int:
    conn = connect(db_path)
    n = conn.execute("SELECT COUNT(*) AS c FROM cases").fetchone()["c"]
    if n > 0:
        conn.close()
        return 0
    now = datetime.now(timezone.utc).isoformat()
    for material, pattern, defect, cause, note in SEED:
        conn.execute(
            """INSERT INTO cases
               (session_id, material, pattern, defect_class, symptoms_json,
                ranked_causes_json, confirmed_cause, explanation, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"seed-{uuid.uuid4().hex[:8]}",
                material,
                pattern,
                defect,
                json.dumps({"note": note, "material": material, "pattern": pattern}),
                json.dumps([{"id": cause, "likelihood_pct": 70}]),
                cause,
                note,
                now,
            ),
        )
    conn.commit()
    inserted = len(SEED)
    conn.close()
    return inserted


def log_case(payload: dict[str, Any], db_path: Path | None = None) -> str:
    session_id = payload.get("session_id") or uuid.uuid4().hex
    conn = connect(db_path)
    conn.execute(
        """INSERT INTO cases
           (session_id, material, pattern, defect_class, symptoms_json,
            ranked_causes_json, confirmed_cause, explanation, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            payload.get("material"),
            payload.get("pattern"),
            payload.get("defect_class"),
            json.dumps(payload.get("symptoms", payload), default=str),
            json.dumps(payload.get("ranked_causes", []), default=str),
            payload.get("confirmed_cause"),
            payload.get("explanation"),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return session_id


def similar_cases(material: str, defect_class: str, db_path: Path | None = None) -> dict[str, Any]:
    conn = connect(db_path)
    rows = conn.execute(
        """SELECT confirmed_cause, COUNT(*) AS n
           FROM cases
           WHERE material = ? AND defect_class = ? AND confirmed_cause IS NOT NULL
           GROUP BY confirmed_cause
           ORDER BY n DESC""",
        (material, defect_class),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM cases WHERE material = ? AND defect_class = ?",
        (material, defect_class),
    ).fetchone()["c"]
    conn.close()
    breakdown = [{"cause": r["confirmed_cause"], "count": r["n"]} for r in rows]
    top = breakdown[0] if breakdown else None
    summary = (
        f"{total} similar cases occurred before."
        if total
        else "No similar cases logged yet."
    )
    if top:
        summary = (
            f"{total} similar {defect_class.replace('_', ' ')} cases on {material.replace('_', ' ')}. "
            f"In {top['count']} of them the confirmed cause was {top['cause'].replace('_', ' ')}."
        )
    return {"total": total, "breakdown": breakdown, "summary": summary}


def recent_cases(limit: int = 20, db_path: Path | None = None) -> list[dict]:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM cases ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
