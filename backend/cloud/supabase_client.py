"""
backend/cloud/supabase_client.py
Singleton Supabase client, lazily initialised from Settings.

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from backend/.env (or the root .env).
Falls back gracefully when credentials are absent so the rest of the app still works.
"""

from __future__ import annotations

from typing import Any

_client = None
_client_error: str | None = None


def get_client():
    """Return a cached supabase Client instance (lazy-loaded)."""
    global _client, _client_error
    if _client is not None:
        return _client
    try:
        from backend.config import get_settings  # imported here to avoid circular imports at module level
        from supabase import create_client  # type: ignore

        settings = get_settings()
        url = settings.supabase_url.strip()
        key = settings.supabase_service_key.strip()

        if not url or not key or "your-project" in url:
            _client_error = (
                "Supabase credentials not configured. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in backend/.env"
            )
            return None

        _client = create_client(url, key)
        _client_error = None
    except ImportError:
        _client_error = "supabase package not installed. Run: pip install supabase"
    except Exception as exc:  # noqa: BLE001
        _client_error = str(exc)
    return _client


def client_status() -> dict[str, Any]:
    get_client()
    from backend.config import get_settings
    settings = get_settings()
    return {
        "ready": _client is not None,
        "url": settings.supabase_url or "(not set)",
        "error": _client_error,
    }
