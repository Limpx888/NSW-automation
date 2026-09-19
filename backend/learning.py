"""AI learning database for dispensing troubleshooting cases.

Stores:
  - Dispensing Problem
  - Possible Causes
  - Recommended Solutions
  - Successful Solution (confirmed on the line)
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- NEW: Dual-engine database configuration ---
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from backend.history import DEFAULT_DB

load_dotenv()
SUPABASE_URL = os.getenv("DATABASE_URL")
supabase_engine = None
if SUPABASE_URL:
    try:
        supabase_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
    except Exception as e:
        print(f"⚠️ Supabase engine initialization failed, falling back to local SQLite: {e}")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Local SQLite fallback connection"""
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS learning_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL UNIQUE,
            session_id TEXT,
            user_email TEXT,
            dispensing_problem TEXT NOT NULL,
            defect_class TEXT,
            defect_label TEXT,
            possible_causes_json TEXT,
            recommended_solutions_json TEXT,
            successful_solution TEXT,
            successful_cause TEXT,
            source TEXT DEFAULT 'diagnosed',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_learning_defect ON learning_cases(defect_class);
        CREATE INDEX IF NOT EXISTS idx_learning_session ON learning_cases(session_id);
        CREATE INDEX IF NOT EXISTS idx_learning_created ON learning_cases(created_at DESC);
        """
    )
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], default=str)


def _loads(raw: str | None) -> Any:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _tokens(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with",
        "is", "are", "was", "were", "this", "that", "from", "after", "into",
    }
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in stop and len(t) > 2}


def _item_to_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        val = item.get("detail") or item.get("action") or item.get("title") or item.get("name") or item.get("solution") or ""
        return str(val).strip()
    return str(item).strip() if item is not None else ""


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Compatible with SQLite Row and SQLAlchemy Mapping"""
    if not row:
        return {}
    row_dict = dict(row)
    raw_causes = _loads(row_dict.get("possible_causes_json"))
    raw_solutions = _loads(row_dict.get("recommended_solutions_json"))
    return {
        "id": row_dict.get("id"),
        "case_id": row_dict.get("case_id"),
        "session_id": row_dict.get("session_id"),
        "user_email": row_dict.get("user_email"),
        "dispensing_problem": row_dict.get("dispensing_problem"),
        "defect_class": row_dict.get("defect_class"),
        "defect_label": row_dict.get("defect_label"),
        "possible_causes": [_item_to_text(c) for c in raw_causes if _item_to_text(c)],
        "recommended_solutions": [_item_to_text(s) for s in raw_solutions if _item_to_text(s)],
        "successful_solution": row_dict.get("successful_solution"),
        "successful_cause": row_dict.get("successful_cause"),
        "source": row_dict.get("source"),
        "created_at": row_dict.get("created_at"),
        "updated_at": row_dict.get("updated_at"),
    }


def _causes_from_payload(causes: Any) -> list[str]:
    names: list[str] = []
    if not causes:
        return names
    if isinstance(causes, list):
        for item in causes:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("cause") or item.get("cause_id")
                if name:
                    names.append(str(name).strip())
    elif isinstance(causes, str) and causes.strip():
        names.append(causes.strip())
    return names


def _solutions_from_payload(action_plan: Any, recommended: Any = None) -> list[str]:
    out: list[str] = []
    if recommended:
        if isinstance(recommended, list):
            for item in recommended:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
        elif isinstance(recommended, str) and recommended.strip():
            out.append(recommended.strip())
        if out: 
            return out

    if isinstance(action_plan, list):
        for step in action_plan:
            if isinstance(step, str) and step.strip():
                out.append(step.strip())
            elif isinstance(step, dict):
                title = step.get("title") or ""
                detail = step.get("action") or step.get("detail") or ""
                related = step.get("cause") or step.get("related_cause") or ""
                text = detail or title
                if related and detail:
                    text = f"{related}: {detail}"
                elif title and detail:
                    text = f"{title} — {detail}"
                if text:
                    out.append(str(text).strip())
    return out


def _problem_from_payload(payload: dict[str, Any]) -> str:
    answers = payload.get("answers") or {}
    text = (
        payload.get("dispensing_problem")
        or payload.get("problem_description")
        or answers.get("problem_description")
        or answers.get("user_description")
        or ""
    )
    text = str(text).strip()
    if text:
        return text
    label = payload.get("defect_label") or payload.get("defect_class") or "Dispensing defect"
    parts = [str(label)]
    for key in ("amount", "frequency", "recent_change", "location", "material"):
        val = answers.get(key)
        if val:
            parts.append(f"{key}: {val}")
    return ". ".join(parts)


def upsert_from_diagnosis(payload: dict[str, Any], db_path: Path | None = None) -> dict[str, Any]:
    """Create or update a learning row after a diagnose run (Dual-Engine)."""
    session_id = payload.get("session_id")
    problem = _problem_from_payload(payload)
    causes = _causes_from_payload(payload.get("possible_causes") or payload.get("causes"))
    solutions = _solutions_from_payload(payload.get("action_plan"), payload.get("recommended_solutions"))
    now = _now()
    
    # ==== Try writing to cloud Supabase ====
    if supabase_engine:
        try:
            with supabase_engine.begin() as conn: # begin() automatically commits
                existing = None
                if session_id:
                    existing = conn.execute(text("SELECT * FROM learning_cases WHERE session_id = :sid"), {"sid": session_id}).mappings().fetchone()
                if not existing and problem:
                    existing = conn.execute(text("SELECT * FROM learning_cases WHERE LOWER(dispensing_problem) = LOWER(:p)"), {"p": problem}).mappings().fetchone()

                if existing:
                    conn.execute(text("""
                        UPDATE learning_cases SET
                            session_id = COALESCE(:sid, session_id),
                            user_email = COALESCE(:email, user_email),
                            dispensing_problem = :prob,
                            defect_class = :dc,
                            defect_label = :dl,
                            possible_causes_json = :pc,
                            recommended_solutions_json = :rs,
                            updated_at = :now
                        WHERE case_id = :cid
                    """), {
                        "sid": session_id, "email": payload.get("user_email"), "prob": problem,
                        "dc": payload.get("defect_class"), "dl": payload.get("defect_label"),
                        "pc": _dumps(causes), "rs": _dumps(solutions), "now": now, "cid": existing["case_id"]
                    })
                    case_id = existing["case_id"]
                else:
                    case_id = payload.get("case_id") or uuid.uuid4().hex
                    conn.execute(text("""
                        INSERT INTO learning_cases (
                            case_id, session_id, user_email, dispensing_problem, defect_class,
                            defect_label, possible_causes_json, recommended_solutions_json,
                            successful_solution, successful_cause, source, created_at, updated_at
                        ) VALUES (:cid, :sid, :email, :prob, :dc, :dl, :pc, :rs, :ss, :sc, :src, :now, :now)
                    """), {
                        "cid": case_id, "sid": session_id, "email": payload.get("user_email"),
                        "prob": problem, "dc": payload.get("defect_class"), "dl": payload.get("defect_label"),
                        "pc": _dumps(causes), "rs": _dumps(solutions),
                        "ss": payload.get("successful_solution"), "sc": payload.get("successful_cause"),
                        "src": payload.get("source") or "diagnosed", "now": now
                    })
                
                row = conn.execute(text("SELECT * FROM learning_cases WHERE case_id = :cid"), {"cid": case_id}).mappings().fetchone()
                return _row_to_dict(row)
        except Exception as e:
            print(f"⚠️ Failed to write to cloud learning_cases, downgrading to local: {e}")

    # ==== Downgrade to write to local SQLite ====
    conn_sq = connect(db_path)
    existing = None
    if session_id:
        existing = conn_sq.execute("SELECT * FROM learning_cases WHERE session_id = ?", (session_id,)).fetchone()
    if not existing and problem:
        existing = conn_sq.execute("SELECT * FROM learning_cases WHERE LOWER(dispensing_problem) = LOWER(?)", (problem,)).fetchone()

    if existing:
        conn_sq.execute(
            """
            UPDATE learning_cases SET
                session_id = COALESCE(?, session_id),
                user_email = COALESCE(?, user_email),
                dispensing_problem = ?,
                defect_class = ?,
                defect_label = ?,
                possible_causes_json = ?,
                recommended_solutions_json = ?,
                updated_at = ?
            WHERE case_id = ?
            """,
            (session_id, payload.get("user_email"), problem, payload.get("defect_class"), payload.get("defect_label"), _dumps(causes), _dumps(solutions), now, existing["case_id"]),
        )
        conn_sq.commit()
        row = conn_sq.execute("SELECT * FROM learning_cases WHERE case_id = ?", (existing["case_id"],)).fetchone()
        conn_sq.close()
        return _row_to_dict(row)

    case_id = payload.get("case_id") or uuid.uuid4().hex
    conn_sq.execute(
        """
        INSERT INTO learning_cases (
            case_id, session_id, user_email, dispensing_problem, defect_class,
            defect_label, possible_causes_json, recommended_solutions_json,
            successful_solution, successful_cause, source, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (case_id, session_id, payload.get("user_email"), problem, payload.get("defect_class"), payload.get("defect_label"), _dumps(causes), _dumps(solutions), payload.get("successful_solution"), payload.get("successful_cause"), payload.get("source") or "diagnosed", now, now),
    )
    conn_sq.commit()
    row = conn_sq.execute("SELECT * FROM learning_cases WHERE case_id = ?", (case_id,)).fetchone()
    conn_sq.close()
    return _row_to_dict(row)


def create_manual_case(payload: dict[str, Any], db_path: Path | None = None) -> dict[str, Any]:
    problem = str(payload.get("dispensing_problem") or "").strip()
    if not problem:
        raise ValueError("dispensing_problem is required")
        
    duplicate = None
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                duplicate = conn.execute(text("SELECT case_id FROM learning_cases WHERE LOWER(dispensing_problem) = LOWER(:p)"), {"p": problem}).fetchone()
        except Exception:
            pass
            
    if not duplicate:
        conn_sq = connect(db_path)
        duplicate = conn_sq.execute("SELECT case_id FROM learning_cases WHERE LOWER(dispensing_problem) = LOWER(?)", (problem,)).fetchone()
        conn_sq.close()
    
    if duplicate:
        raise ValueError("This dispensing problem already exists in the Case Library.")

    return upsert_from_diagnosis({**payload, "session_id": payload.get("session_id"), "source": payload.get("source") or "manual"}, db_path=db_path)


def mark_successful_solution(
    *, case_id: str | None = None, session_id: str | None = None,
    successful_solution: str, successful_cause: str | None = None, db_path: Path | None = None,
) -> dict[str, Any] | None:
    solution = (successful_solution or "").strip()
    if not solution:
        raise ValueError("successful_solution is required")
    if not case_id and not session_id:
        raise ValueError("case_id or session_id is required")

    # ==== Try cloud ====
    if supabase_engine:
        try:
            with supabase_engine.begin() as conn:
                if case_id:
                    row = conn.execute(text("SELECT * FROM learning_cases WHERE case_id = :cid"), {"cid": case_id}).mappings().fetchone()
                else:
                    row = conn.execute(text("SELECT * FROM learning_cases WHERE session_id = :sid"), {"sid": session_id}).mappings().fetchone()
                
                if row:
                    cause = (successful_cause or "").strip() or row.get("successful_cause")
                    conn.execute(text("""
                        UPDATE learning_cases
                        SET successful_solution = :ss, successful_cause = :sc, updated_at = :now
                        WHERE case_id = :cid
                    """), {"ss": solution, "sc": cause or None, "now": _now(), "cid": row["case_id"]})
                    
                    updated = conn.execute(text("SELECT * FROM learning_cases WHERE case_id = :cid"), {"cid": row["case_id"]}).mappings().fetchone()
                    return _row_to_dict(updated)
        except Exception as e:
            print(f"⚠️ Cloud mark_successful_solution failed: {e}")

    # ==== Downgrade to local ====
    conn_sq = connect(db_path)
    if case_id:
        row = conn_sq.execute("SELECT * FROM learning_cases WHERE case_id = ?", (case_id,)).fetchone()
    else:
        row = conn_sq.execute("SELECT * FROM learning_cases WHERE session_id = ?", (session_id,)).fetchone()
        
    if not row:
        conn_sq.close()
        return None

    cause = (successful_cause or "").strip() or row["successful_cause"]
    conn_sq.execute(
        """
        UPDATE learning_cases
        SET successful_solution = ?, successful_cause = ?, updated_at = ?
        WHERE case_id = ?
        """,
        (solution, cause or None, _now(), row["case_id"]),
    )
    conn_sq.commit()
    updated = conn_sq.execute("SELECT * FROM learning_cases WHERE case_id = ?", (row["case_id"],)).fetchone()
    conn_sq.close()
    return _row_to_dict(updated)


def list_cases(limit: int = 100, defect_class: str | None = None, db_path: Path | None = None) -> list[dict[str, Any]]:
    # ==== Try cloud ====
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                if defect_class:
                    rows = conn.execute(text("SELECT * FROM learning_cases WHERE defect_class = :dc ORDER BY updated_at DESC LIMIT :l"), {"dc": defect_class, "l": limit}).mappings().all()
                else:
                    rows = conn.execute(text("SELECT * FROM learning_cases ORDER BY updated_at DESC LIMIT :l"), {"l": limit}).mappings().all()
                return [_row_to_dict(r) for r in rows]
        except Exception as e:
            print(f"⚠️ Cloud list_cases failed: {e}")

    # ==== Downgrade to local ====
    conn_sq = connect(db_path)
    if defect_class:
        rows = conn_sq.execute("SELECT * FROM learning_cases WHERE defect_class = ? ORDER BY updated_at DESC LIMIT ?", (defect_class, int(limit))).fetchall()
    else:
        rows = conn_sq.execute("SELECT * FROM learning_cases ORDER BY updated_at DESC LIMIT ?", (int(limit),)).fetchall()
    conn_sq.close()
    return [_row_to_dict(r) for r in rows]


def _is_similar(row: dict | sqlite3.Row, defect_class: str | None, problem_tokens: set[str]) -> bool:
    row_class = (row.get("defect_class") or "").strip()
    if defect_class and row_class and row_class.lower() == defect_class.lower():
        return True
    if problem_tokens:
        overlap = len(problem_tokens & _tokens(row.get("dispensing_problem") or ""))
        return overlap >= 2
    return False


def get_insights(
    defect_class: str | None = None, dispensing_problem: str | None = None,
    exclude_case_id: str | None = None, exclude_session_id: str | None = None, db_path: Path | None = None,
) -> dict[str, Any]:
    rows = None
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                rows = conn.execute(text("SELECT * FROM learning_cases")).mappings().all()
        except Exception:
            pass
            
    if rows is None:
        conn_sq = connect(db_path)
        rows = conn_sq.execute("SELECT * FROM learning_cases").fetchall()
        conn_sq.close()

    problem_tokens = _tokens(dispensing_problem or "")
    matched = []
    for r in rows:
        row = dict(r)
        if exclude_case_id and row.get("case_id") == exclude_case_id:
            continue
        if exclude_session_id and row.get("session_id") == exclude_session_id:
            continue
        if _is_similar(row, defect_class, problem_tokens):
            matched.append(row)

    cause_counter: Counter[str] = Counter()
    solution_counter: Counter[str] = Counter()
    for row in matched:
        cause = (row.get("successful_cause") or "").strip()
        if not cause:
            possibles = _loads(row.get("possible_causes_json"))
            if possibles:
                first = possibles[0]
                cause = first if isinstance(first, str) else str((first or {}).get("name") or "")
        if cause:
            cause_counter[cause] += 1
        sol = (row.get("successful_solution") or "").strip()
        if sol:
            solution_counter[sol] += 1

    total = len(matched)
    top_cause, top_cause_count = cause_counter.most_common(1)[0] if cause_counter else (None, 0)
    top_solution, top_solution_count = solution_counter.most_common(1)[0] if solution_counter else (None, 0)

    insight = None
    if total > 0:
        insight = f"Similar problems occurred {total} time{'s' if total != 1 else ''} previously."
        if top_cause and top_cause_count:
            insight += f" In {top_cause_count} case{'s' if top_cause_count != 1 else ''}, the main cause was {top_cause}."
        if top_solution and top_solution_count:
            insight += f" The most successful fix was: {top_solution}"

    return {
        "similar_count": total, "top_cause": top_cause, "top_cause_count": top_cause_count,
        "top_solution": top_solution, "top_solution_count": top_solution_count, "insight": insight,
        "cause_breakdown": [{"name": name, "count": count, "pct": round(count / total * 100, 1)} for name, count in cause_counter.most_common(8)],
        "solution_breakdown": [{"name": name, "count": count, "pct": round(count / total * 100, 1)} for name, count in solution_counter.most_common(8)],
    }


def attach_to_diagnosis(payload: dict[str, Any], db_path: Path | None = None) -> dict[str, Any]:
    row = upsert_from_diagnosis(payload, db_path=db_path)
    insights = get_insights(
        defect_class=payload.get("defect_class"),
        dispensing_problem=row.get("dispensing_problem"),
        exclude_case_id=row.get("case_id"),
        exclude_session_id=payload.get("session_id"),
        db_path=db_path,
    )
    return {"learning_case": row, "insights": insights}


def get_stats(db_path: Path | None = None) -> dict[str, Any]:
    rows = None
    if supabase_engine:
        try:
            with supabase_engine.connect() as conn:
                rows = conn.execute(text("SELECT * FROM learning_cases")).mappings().all()
        except Exception:
            pass
            
    if rows is None:
        conn_sq = connect(db_path)
        rows = conn_sq.execute("SELECT * FROM learning_cases").fetchall()
        conn_sq.close()

    total = len(rows)
    resolved = sum(1 for r in rows if (dict(r).get("successful_solution") or "").strip())
    cause_counter: Counter[str] = Counter()
    for r in rows:
        cause = (dict(r).get("successful_cause") or "").strip()
        if cause:
            cause_counter[cause] += 1
    top_cause = cause_counter.most_common(1)[0][0] if cause_counter else None
    return {
        "total_cases": total, "resolved_count": resolved, "top_cause": top_cause,
        "cause_breakdown": [{"name": name, "count": count, "pct": round(count / total * 100, 1) if total else 0} for name, count in cause_counter.most_common(8)],
    }