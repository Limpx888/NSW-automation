from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Prefer backend/.env (where you put the key); also accept project-root .env
        env_file=(str(BACKEND_DIR / ".env"), str(ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    yolo_model_path: str = "backend/weights/best.pt"
    yolo_conf: float = 0.25
    yolo_iou: float = 0.45
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    cors_origins: str = "http://localhost:8443,http://127.0.0.1:8443"

    @property
    def model_path(self) -> Path:
        raw = Path(self.yolo_model_path)
        candidates = [
            raw if raw.is_absolute() else ROOT / raw,
            raw if raw.is_absolute() else BACKEND_DIR / raw,
            BACKEND_DIR / "weights" / "best.pt",
            ROOT / "backend" / "weights" / "best.pt",
            ROOT / "best.pt",
            ROOT / "best (2).pt",
            ROOT / "best (1).pt",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return raw if raw.is_absolute() else ROOT / raw

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
