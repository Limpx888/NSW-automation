"""SQLite history log for DARA solder-paste scan cases."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "scan_cases.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    filename TEXT,
    defect_class TEXT,
    defect_label TEXT,
    confidence REAL,
    detection_count INTEGER DEFAULT 0,
    quality_score INTEGER,
    shape_consistency REAL,
    size_consistency REAL,
    dispensing_position REAL,
    defect_risk REAL,
    answers_json TEXT,
    causes_json TEXT,
    action_plan_json TEXT,
    detections_json TEXT,
    annotated_image_base64 TEXT,
    status TEXT DEFAULT 'analyzed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scan_cases_created ON scan_cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_cases_defect ON scan_cases(defect_class);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else None, default=str)


def create_case(payload: dict[str, Any], db_path: Path | None = None) -> str:
    """Create a history row after YOLO analyze."""
    session_id = payload.get("session_id") or uuid.uuid4().hex
    now = _now()
    vision = payload.get("vision") or {}
    quality = payload.get("quality") or {}

    conn = connect(db_path)
    conn.execute(
        """
        INSERT INTO scan_cases (
            session_id, filename, defect_class, defect_label, confidence,
            detection_count, quality_score, shape_consistency, size_consistency,
            dispensing_position, defect_risk, answers_json, causes_json,
            action_plan_json, detections_json, annotated_image_base64,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            payload.get("filename"),
            payload.get("defect_class") or vision.get("defect_class"),
            payload.get("defect_label") or vision.get("defect_label"),
            float(payload.get("confidence") or vision.get("confidence") or 0),
            int(
                payload.get("detection_count")
                or vision.get("detection_count")
                or len(payload.get("detections") or [])
                or 0
            ),
            quality.get("overall_quality_score") or payload.get("overall_quality_score"),
            quality.get("shape_consistency") or payload.get("shape_consistency"),
            quality.get("size_consistency") or payload.get("size_consistency"),
            quality.get("dispensing_position") or payload.get("dispensing_position"),
            quality.get("defect_risk") or payload.get("defect_risk"),
            _dumps(payload.get("answers")),
            _dumps(payload.get("causes")),
            _dumps(payload.get("action_plan")),
            _dumps(payload.get("detections") or vision.get("detections") or []),
            # Keep thumbnail-capable image; can be large but useful for history replay
            payload.get("annotated_image_base64") or vision.get("annotated_image_base64"),
            payload.get("status") or "analyzed",
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return session_id


def update_case(session_id: str, payload: dict[str, Any], db_path: Path | None = None) -> bool:
    """Update an existing case after diagnose / Q&A."""
    conn = connect(db_path)
    row = conn.execute(
        "SELECT session_id FROM scan_cases WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False

    fields: list[str] = []
    values: list[Any] = []

    mapping = {
        "defect_class": payload.get("defect_class"),
        "defect_label": payload.get("defect_label"),
        "confidence": payload.get("confidence"),
        "detection_count": payload.get("detection_count"),
        "quality_score": payload.get("overall_quality_score")
        or (payload.get("quality") or {}).get("overall_quality_score"),
        "answers_json": _dumps(payload["answers"]) if "answers" in payload else None,
        "causes_json": _dumps(payload["causes"]) if "causes" in payload else None,
        "action_plan_json": _dumps(payload["action_plan"]) if "action_plan" in payload else None,
        "status": payload.get("status"),
    }
    for col, val in mapping.items():
        if val is None and col not in {"answers_json", "causes_json", "action_plan_json"}:
            # allow explicit null only for JSON when key present — handled above
            if col.endswith("_json"):
                fields.append(f"{col} = ?")
                values.append(val)
            continue
        if col.endswith("_json") or val is not None:
            fields.append(f"{col} = ?")
            values.append(val)

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(session_id)

    conn.execute(
        f"UPDATE scan_cases SET {', '.join(fields)} WHERE session_id = ?",
        values,
    )
    conn.commit()
    conn.close()
    return True


def upsert_diagnosed_case(payload: dict[str, Any], db_path: Path | None = None) -> str:
    """
    Save a diagnosed case.
    If session_id exists → update; else create a new diagnosed row.
    """
    session_id = payload.get("session_id")
    if session_id and update_case(
        session_id,
        {
            **payload,
            "status": "diagnosed",
            "answers": payload.get("answers"),
            "causes": payload.get("causes"),
            "action_plan": payload.get("action_plan"),
        },
        db_path=db_path,
    ):
        return session_id

    return create_case({**payload, "status": "diagnosed"}, db_path=db_path)


def list_cases(limit: int = 50, db_path: Path | None = None) -> list[dict[str, Any]]:
    conn = connect(db_path)
    rows = conn.execute(
        """
        SELECT session_id, filename, defect_class, defect_label, confidence,
               detection_count, quality_score, shape_consistency, size_consistency,
               dispensing_position, defect_risk, answers_json, causes_json,
               action_plan_json, status, created_at, updated_at
        FROM scan_cases
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    conn.close()
    return [_row_to_summary(r) for r in rows]


def get_case(session_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT * FROM scan_cases WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_detail(row)


def _loads(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _row_to_summary(row: sqlite3.Row) -> dict[str, Any]:
    causes = _loads(row["causes_json"]) or []
    top = causes[0] if isinstance(causes, list) and causes else None
    return {
        "session_id": row["session_id"],
        "filename": row["filename"],
        "defect_class": row["defect_class"],
        "defect_label": row["defect_label"],
        "confidence": row["confidence"],
        "detection_count": row["detection_count"],
        "quality_score": row["quality_score"],
        "top_cause": (top or {}).get("name") if isinstance(top, dict) else None,
        "top_cause_pct": (top or {}).get("likelihood_pct") if isinstance(top, dict) else None,
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_detail(row: sqlite3.Row) -> dict[str, Any]:
    summary = _row_to_summary(row)
    summary.update(
        {
            "shape_consistency": row["shape_consistency"],
            "size_consistency": row["size_consistency"],
            "dispensing_position": row["dispensing_position"],
            "defect_risk": row["defect_risk"],
            "answers": _loads(row["answers_json"]) or {},
            "causes": _loads(row["causes_json"]) or [],
            "action_plan": _loads(row["action_plan_json"]) or [],
            "detections": _loads(row["detections_json"]) or [],
            "annotated_image_base64": row["annotated_image_base64"],
        }
    )
    return summary
