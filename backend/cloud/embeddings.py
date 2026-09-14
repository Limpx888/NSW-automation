"""
backend/cloud/embeddings.py
Shared sentence-transformer embedder for vector generation.

Lazily loads the model on first use so the backend doesn't pay the
startup cost unless a cloud feature is actually triggered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

_embedder = None
_embedder_error: str | None = None

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def get_embedder():
    """Return a cached SentenceTransformer instance (lazy-loaded)."""
    global _embedder, _embedder_error
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _embedder = SentenceTransformer(MODEL_NAME)
        _embedder_error = None
    except ImportError:
        _embedder_error = "sentence-transformers is not installed. Run: pip install sentence-transformers"
    except Exception as exc:  # noqa: BLE001
        _embedder_error = str(exc)
    return _embedder


def embed(text: str) -> list[float] | None:
    """
    Convert a text string into a 384-dimension float vector.
    Returns None if the embedder is unavailable.
    """
    model = get_embedder()
    if model is None:
        return None
    vector = model.encode(text)
    return vector.tolist()


def embedder_status() -> dict:
    get_embedder()
    return {
        "model": MODEL_NAME,
        "dim": EMBEDDING_DIM,
        "ready": _embedder is not None,
        "error": _embedder_error,
    }
