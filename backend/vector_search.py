"""
backend/vector_search.py
Semantic-Based Vector Search (RAG / Vector Search) for DARA.

Embeds problem descriptions (384-dimension) and calculates cosine similarity
against historical learning_cases to retrieve high-confidence confirmed fixes.
"""

from __future__ import annotations

import math
import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.history import DEFAULT_DB

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with",
    "is", "are", "was", "were", "this", "that", "from", "after", "into", "at", "by"
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _fallback_vector_similarity(text1: str, text2: str) -> float:
    """Cosine similarity fallback using term-frequency vectors when PyTorch/transformer is offline."""
    tokens1 = [t for t in _TOKEN_RE.findall(text1.lower()) if t not in _STOPWORDS]
    tokens2 = [t for t in _TOKEN_RE.findall(text2.lower()) if t not in _STOPWORDS]
    if not tokens1 or not tokens2:
        return 0.0

    all_vocab = list(set(tokens1 + tokens2))
    v1 = [tokens1.count(w) for w in all_vocab]
    v2 = [tokens2.count(w) for w in all_vocab]

    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))


def find_similar_historical_solution(
    new_problem_description: str,
    db_path: Path | str | None = None,
    similarity_threshold: float = 0.70,
) -> tuple[str | None, float, str | None]:
    """
    Find the most similar historical confirmed fix from learning_cases.
    
    Returns:
        (best_solution, highest_similarity, best_cause)
    """
    if not new_problem_description or not new_problem_description.strip():
        return None, 0.0, None

    path = Path(db_path) if db_path else DEFAULT_DB
    if not path.exists():
        fallback_path = Path("data/dara.db")
        if fallback_path.exists():
            path = fallback_path

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT dispensing_problem, successful_solution, successful_cause 
            FROM learning_cases 
            WHERE successful_solution IS NOT NULL 
              AND TRIM(successful_solution) != ''
            """
        )
        history = cursor.fetchall()
        conn.close()
    except Exception:
        return None, 0.0, None

    if not history:
        return None, 0.0, None

    # Try sentence_transformers if available
    embedder = None
    try:
        from backend.cloud.embeddings import get_embedder
        embedder = get_embedder()
    except Exception:
        embedder = None

    best_match_sol: str | None = None
    best_match_cause: str | None = None
    highest_similarity = -1.0

    if embedder is not None:
        try:
            import numpy as np
            new_vector = embedder.encode(new_problem_description)
            new_norm = np.linalg.norm(new_vector)

            for prob, sol, cause in history:
                if not prob or not sol:
                    continue
                hist_vector = embedder.encode(prob)
                hist_norm = np.linalg.norm(hist_vector)
                if new_norm == 0 or hist_norm == 0:
                    continue
                sim = float(np.dot(new_vector, hist_vector) / (new_norm * hist_norm))
                if sim > highest_similarity:
                    highest_similarity = sim
                    best_match_sol = sol
                    best_match_cause = cause
        except Exception:
            embedder = None

    # Fallback to lexical/cosine term vector similarity if transformer had an issue
    if embedder is None:
        for prob, sol, cause in history:
            if not prob or not sol:
                continue
            sim = _fallback_vector_similarity(new_problem_description, prob)
            if sim > highest_similarity:
                highest_similarity = sim
                best_match_sol = sol
                best_match_cause = cause

    if highest_similarity >= similarity_threshold:
        return best_match_sol, float(highest_similarity), best_match_cause

    return None, float(max(0.0, highest_similarity)), None
