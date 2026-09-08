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

    yolo_model_path: str = "best (2).pt"
    yolo_conf: float = 0.25
    yolo_iou: float = 0.45
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    cors_origins: str = "http://localhost:8443,http://127.0.0.1:8443"

    @property
    def model_path(self) -> Path:
        path = Path(self.yolo_model_path)
        if not path.is_absolute():
            path = ROOT / path
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
