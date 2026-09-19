"""SQLite & Supabase dual-engine history log for DARA solder-paste scan cases."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- NEW: Dual-engine database configuration ---
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "scan_cases.db"
DB_PATH = DEFAULT_DB

load_dotenv()
SUPABASE_URL = os.getenv("DATABASE_URL")
supabase_engine = None
if SUPABASE_URL:
    try:
        supabase_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
    except Exception as e:
        print(f"⚠️ Supabase engine initialization failed, falling back to local SQLite: {e}")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Local SQLite fallback connection"""
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # Bootstrap table without user_email index (safe for old DBs)
    conn.executescript("""
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
    """)

    existing_cols = [r["name"] for r in conn.execute("PRAGMA table_info(scan_cases)").fetchall()]
    if "user_email" not in existing_cols:
        conn.execute("ALTER TABLE scan_cases ADD COLUMN user_email TEXT")
        conn.commit()

    conn.execute("CREATE INDEX IF NOT EXISTS idx_scan_cases_user ON scan_cases(user_email)")
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else None, default=str)


def _loads(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _row_to_summary(row: Any) -> dict[str, Any]:
    row_dict = dict(row)
    causes = _loads(row_dict.get("causes_json")) or []
    top = causes[0] if isinstance(causes, list) and causes else None
    return {
        "session_id": row_dict.get("session_id"),
        "user_email": row_dict.get("user_email"),
        "filename": row_dict.get("filename"),
        "defect_class": row_dict.get("defect_class"),
        "defect_label": row_dict.get("defect_label"),
        "confidence": row_dict.get("confidence"),
        "detection_count": row_dict.get("detection_count"),
        "quality_score": row_dict.get("quality_score"),
        "top_cause": (top or {}).get("name") if isinstance(top, dict) else None,
        "top_cause_pct": (top or {}).get("likelihood_pct") if isinstance(top, dict) else None,
        "annotated_image_base64": row_dict.get("annotated_image_base64"),
        "status": row_dict.get("status"),
        "created_at": row_dict.get("created_at"),
        "updated_at": row_dict.get("updated_at"),
    }


def _row_to_detail(row: Any) -> dict[str, Any]:
    row_dict = dict(row)
    summary = _row_to_summary(row_dict)
    answers = _loads(row_dict.get("answers_json")) or {}
    problem_desc = answers.get("problem_description") or answers.get("user_description") or answers.get("description")
    summary.update(
        {
            "problem_description": problem_desc,
            "shape_consistency": row_dict.get("shape_consistency"),
            "size_consistency": row_dict.get("size_consistency"),
            "dispensing_position": row_dict.get("dispensing_position"),
            "defect_risk": row_dict.get("defect_risk"),
            "answers": answers,
            "causes": _loads(row_dict.get("causes_json")) or [],
            "action_plan": _loads(row_dict.get("action_plan_json")) or [],
            "detections": _loads(row_dict.get("detections_json")) or [],
            "annotated_image_base64": row_dict.get("annotated_image_base64"),
        }
    )
    return summary


def create_case(payload: dict[str, Any], db_path: Path | None = None) -> str:
    session_id = payload.get("session_id") or uuid.uuid4().hex
    now = _now()
    vision = payload.get("vision") or {}
    quality = payload.get("quality") or {}

    values_dict = {
        "sid": session_id,
        "email": payload.get("user_email"),
        "fname": payload.get("filename"),
        "dclass": payload.get("defect_class") or vision.get("defect_class"),
        "dlabel": payload.get("defect_label") or vision.get("defect_label"),
        "conf": float(payload.get("confidence") or vision.get("confidence") or 0),
        "dcount": int(payload.get("detection_count") or vision.get("detection_count") or len(payload.get("detections") or []) or 0),
        "qscore": quality.get("overall_quality_score") or payload.get("overall_quality_score"),
        "sconsist": quality.get("shape_consistency") or payload.get("shape_consistency"),
        "szconsist": quality.get("size_consistency") or payload.get("size_consistency"),
        "dpos": quality.get("dispensing_position") or payload.get("dispensing_position"),
        "drisk": quality.get("defect_risk") or payload.get("defect_risk"),
        "ans": _dumps(payload.get("answers")),
        "cau": _dumps(payload.get("causes")),
        "act": _dumps(payload.get("action_plan")),
        "det": _dumps(payload.get("detections") or vision.get("detections") or []),
        "img": payload.get("annotated_image_base64") or vision.get("annotated_image_base64"),
        "stat": payload.get("status") or "analyzed",
        "now": now
    }

    # ==== Cloud Supabase priority ====
    if supabase_engine:
        try:
            with supabase_engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO scan_cases (
                        session_id, user_email, filename, defect_class, defect_label, confidence,
                        detection_count, quality_score, shape_consistency, size_consistency,
                        dispensing_position, defect_risk, answers_json, causes_json,
                        action_plan_json, detections_json, annotated_image_base64,
                        status, created_at, updated_at
                    ) VALUES (
                        :sid, :email, :fname, :dclass, :dlabel, :conf,
                        :dcount, :qscore, :sconsist, :szconsist,
                        :dpos, :drisk, :ans, :cau,
                        :act, :det, :img, :stat, :now, :now
                    )
                """), values_dict)
            return session_id
        except Exception as e:
            print(f"⚠️ Cloud create_case failed, downgrading to local: {e}")

    # ==== Downgrade to local SQLite ====
    conn = connect(db_path)
    conn.execute(
        """
        INSERT INTO scan_cases (
            session_id, user_email, filename, defect_class, defect_label, confidence,
            detection_count, quality_score, shape_consistency, size_consistency,
            dispensing_position, defect_risk, answers_json, causes_json,
            action_plan_json, detections_json, annotated_image_base64,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            values_dict["sid"], values_dict["email"], values_dict["fname"], values_dict["dclass"], 
            values_dict["dlabel"], values_dict["conf"], values_dict["dcount"], values_dict["qscore"], 
            values_dict["sconsist"], values_dict["szconsist"], values_dict["dpos"], values_dict["drisk"], 
            values_dict["ans"], values_dict["cau"], values_dict["act"], values_dict["det"], 
            values_dict["img"], values_dict["stat"], values_dict["now"], values_dict["now"]
        ),
    )
    conn.commit()
    conn.close()
    return session_id


def update_case(session_id: str, payload: dict[str, Any], db_path: Path | None = None) -> bool:
    mapping = {
        "user_email": payload.get("user_email"),
        "defect_class": payload.get("defect_class"),
        "defect_label": payload.get("defect_label"),
        "confidence": payload.get("confidence"),
        "detection_count": payload.get("detection_count"),
        "quality_score": payload.get("overall_quality_score") or (payload.get("quality") or {}).get("overall_quality_score"),
        "answers_json": _dumps(payload["answers"]) if "answers" in payload else None,
        "causes_json": _dumps(payload["causes"]) if "causes" in payload else None,
        "action_plan_json": _dumps(payload["action_plan"]) if "action_plan" in payload else None,
        "status": payload.get("status"),
    }

    # ==== Cloud Supabase priority ====
    if supabase_engine:
        try:
            with supabase_engine.begin() as conn:
                row = conn.execute(text("SELECT session_id FROM scan_cases WHERE session_id = :sid"), {"sid": session_id}).fetchone()
                if row:
                    fields = []
                    values = {"sid": session_id, "now": _now()}
                    for col, val in mapping.items():
                        if val is not None or col in {"answers_json", "causes_json", "action_plan_json"}:
                            fields.append(f"{col} = :{col}")
                            values[col] = val
                    fields.append("updated_at = :now")
                    
                    conn.execute(text(f"UPDATE scan_cases SET {', '.join(fields)} WHERE session_id = :sid"), values)
                    return True
        except Exception as e:
            print(f"⚠️ Cloud update_case failed, downgrading to local: {e}")

    # ==== Downgrade to local SQLite ====
    conn = connect(db_path)
    row = conn.execute("SELECT session_id FROM scan_cases WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        conn.close()
        return False

    fields_sq = []
    values_sq = []
    for col, val in mapping.items():
        if val is not None or col in {"answers_json", "causes_json", "action_plan_json"}:
            fields_sq.append(f"{col} = ?")
            values_sq.append(val)

    fields_sq.append("updated_at = ?")
    values_sq.append(_now())
    values_sq.append(session_id)

    conn.execute(f"UPDATE scan_cases SET {', '.join(fields_sq)} WHERE session_id = ?", values_sq)
    conn.commit()
    conn.close()
    return True


def upsert_diagnosed_case(payload: dict[str, Any], db_path: Path | None = None) -> str:
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


def list_cases(limit: int = 50, user_email: str | None = None, db_path: Path | None = None) -> list[dict[str, Any]]:
    if not user_email or not user_email.strip():
        return []
        
    query_str = """
        SELECT session_id, user_email, filename, defect_class, defect_label, confidence,
               detection_count, quality_score, shape_consistency, size_consistency,
               dispensing_position, defect_risk, answers_json, causes_json,
               action_plan_json, annotated_image_base64, status, created_at, updated_at
        FROM scan_cases
        WHERE user_email = :email
        ORDER BY created_at DESC
        LIMIT :lim
    """

    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                rows = conn.execute(text(query_str), {"email": user_email.strip(), "lim": int(limit)}).mappings().all()
                return [_row_to_summary(r) for r in rows]
        except Exception as e:
            print(f"⚠️ Cloud list_cases failed, downgrading to local: {e}")

    conn = connect(db_path)
    rows = conn.execute(query_str.replace(":email", "?").replace(":lim", "?"), (user_email.strip(), int(limit))).fetchall()
    conn.close()
    return [_row_to_summary(r) for r in rows]


def get_case(session_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                row = conn.execute(text("SELECT * FROM scan_cases WHERE session_id = :sid"), {"sid": session_id}).mappings().fetchone()
                if row:
                    return _row_to_detail(row)
        except Exception as e:
            print(f"⚠️ Cloud get_case failed, downgrading to local: {e}")

    conn = connect(db_path)
    row = conn.execute("SELECT * FROM scan_cases WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return _row_to_detail(row) if row else None


def count_cases(user_email: str | None = None, db_path: Path | None = None) -> int:
    if not user_email or not user_email.strip():
        return 0

    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM scan_cases WHERE user_email = :email"), {"email": user_email.strip()}).scalar()
                return int(count or 0)
        except Exception as e:
            print(f"⚠️ Cloud count_cases failed, downgrading to local: {e}")

    conn = connect(db_path)
    row = conn.execute("SELECT COUNT(*) AS n FROM scan_cases WHERE user_email = ?", (user_email.strip(),)).fetchone()
    conn.close()
    return int(row["n"] if row else 0)


def count_similar_cases(defect_class: str, exclude_session_id: str | None = None, db_path: Path | None = None) -> tuple[int, str | None, int]:
    rows = None
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                rows = conn.execute(text("SELECT session_id, causes_json FROM scan_cases WHERE defect_class = :dc ORDER BY created_at DESC"), {"dc": defect_class}).mappings().all()
        except Exception as e:
            print(f"⚠️ Cloud count_similar_cases failed, downgrading to local: {e}")
            
    if rows is None:
        conn = connect(db_path)
        rows = conn.execute("SELECT session_id, causes_json FROM scan_cases WHERE defect_class = ? ORDER BY created_at DESC", (defect_class,)).fetchall()
        conn.close()

    cause_counts: dict[str, int] = {}
    total = 0
    for r in rows:
        row = dict(r)
        if exclude_session_id and row["session_id"] == exclude_session_id:
            continue
        total += 1
        causes = _loads(row["causes_json"]) or []
        if isinstance(causes, list) and causes and isinstance(causes[0], dict):
            name = causes[0].get("name")
            if name:
                cause_counts[name] = cause_counts.get(name, 0) + 1

    if not cause_counts:
        return total, None, 0
    top_name = max(cause_counts, key=cause_counts.get)
    return total, top_name, cause_counts[top_name]


def get_history_analytics(user_email: str | None = None, year: int | None = None, month: int | None = None, db_path: Path | None = None) -> dict[str, Any]:
    if not user_email or not user_email.strip():
        return {"total_scans": 0, "diagnosed_count": 0, "top_defect": None, "defect_distribution": [], "available_years": [], "available_months": []}

    rows = None
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                rows = conn.execute(text("SELECT session_id, defect_class, defect_label, status, created_at FROM scan_cases WHERE user_email = :email ORDER BY created_at DESC"), {"email": user_email.strip()}).mappings().all()
        except Exception as e:
            print(f"⚠️ Cloud get_history_analytics failed, downgrading to local: {e}")

    if rows is None:
        conn = connect(db_path)
        rows = conn.execute("SELECT session_id, defect_class, defect_label, status, created_at FROM scan_cases WHERE user_email = ? ORDER BY created_at DESC", (user_email.strip(),)).fetchall()
        conn.close()

    if not rows:
        return {"total_scans": 0, "diagnosed_count": 0, "top_defect": None, "defect_distribution": [], "available_years": [], "available_months": []}

    years_set: set[int] = set()
    months_set: set[str] = set()
    for r in rows:
        row = dict(r)
        created = str(row["created_at"])
        if len(created) >= 4 and created[:4].isdigit():
            years_set.add(int(created[:4]))
        if len(created) >= 7 and created[:7].replace("-", "").isdigit():
            months_set.add(created[:7])

    available_years = sorted(years_set, reverse=True)
    available_months = sorted(months_set, reverse=True)

    filtered_rows = []
    for r in rows:
        row = dict(r)
        created = str(row["created_at"])
        if year is not None:
            if not created.startswith(str(year)):
                continue
            if month is not None:
                m_str = f"{year}-{month:02d}"
                if not created.startswith(m_str):
                    continue
        filtered_rows.append(row)

    total_scans = len(filtered_rows)
    diagnosed_count = sum(1 for r in filtered_rows if r["status"] == "diagnosed")

    defect_counts: dict[str, int] = {}
    for r in filtered_rows:
        label = r["defect_label"] or r["defect_class"] or "Unknown"
        label_clean = label.replace("_", " ").upper()
        defect_counts[label_clean] = defect_counts.get(label_clean, 0) + 1

    distribution = []
    top_defect = None
    if total_scans > 0 and defect_counts:
        sorted_counts = sorted(defect_counts.items(), key=lambda x: x[1], reverse=True)
        top_defect = sorted_counts[0][0]
        for label, cnt in sorted_counts:
            pct = round((cnt / total_scans) * 100, 1)
            distribution.append({"label": label, "count": cnt, "pct": pct})

    return {
        "total_scans": total_scans,
        "diagnosed_count": diagnosed_count,
        "top_defect": top_defect,
        "defect_distribution": distribution,
        "available_years": available_years,
        "available_months": available_months,
    }


def get_monthly_volume(user_email: str | None = None, months_back: int = 6, db_path: Path | None = None) -> dict[str, Any]:
    from datetime import date
    
    today = date.today()
    year = today.year
    month = today.month
    total_months = year * 12 + month - 1
    start_total = total_months - (months_back - 1)
    start_year = start_total // 12
    start_month = start_total % 12 + 1
    start_date = f"{start_year}-{start_month:02d}-01"

    rows = None
    # ==== Cloud Supabase ====
    # PostgreSQL uses TO_CHAR instead of SQLite's strftime
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                where_clause = "WHERE created_at::timestamp >= :sd"
                params = {"sd": start_date}
                if user_email and user_email.strip():
                    where_clause += " AND user_email = :email"
                    params["email"] = user_email.strip()
                
                rows = conn.execute(text(f"""
                    SELECT TO_CHAR(created_at::timestamp, 'YYYY-MM') AS month_key, COUNT(*) AS scan_count
                    FROM scan_cases {where_clause} GROUP BY month_key ORDER BY month_key ASC
                """), params).mappings().all()
        except Exception as e:
            print(f"⚠️ Cloud get_monthly_volume failed, downgrading to local: {e}")

    # ==== Downgrade to local SQLite ====
    if rows is None:
        conn = connect(db_path)
        where_clause = "WHERE created_at >= ?"
        params_sq = [start_date]
        if user_email and user_email.strip():
            where_clause += " AND user_email = ?"
            params_sq.append(user_email.strip())

        rows = conn.execute(f"""
            SELECT strftime('%Y-%m', created_at) AS month_key, COUNT(*) AS scan_count
            FROM scan_cases {where_clause} GROUP BY month_key ORDER BY month_key ASC
        """, params_sq).fetchall()
        conn.close()

    db_map: dict[str, int] = {dict(r)["month_key"]: dict(r)["scan_count"] for r in rows}

    month_labels: list[str] = []
    month_values: list[int] = []
    for i in range(months_back):
        offset = total_months - (months_back - 1) + i
        y = offset // 12
        m = offset % 12 + 1
        key = f"{y}-{m:02d}"
        short_label = date(y, m, 1).strftime("%b")
        month_labels.append(short_label)
        month_values.append(db_map.get(key, 0))

    trend_pct: float | None = None
    if len(month_values) >= 2:
        prev = month_values[-2]
        curr = month_values[-1]
        if prev > 0:
            trend_pct = round((curr - prev) / prev * 100, 1)
        elif curr > 0:
            trend_pct = 100.0

    current_month_total = month_values[-1] if month_values else 0

    return {
        "labels": month_labels,
        "values": month_values,
        "trend_pct": trend_pct,
        "current_month_total": current_month_total,
    }