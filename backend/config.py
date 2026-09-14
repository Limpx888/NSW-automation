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
    yolo_dispense_path: str = "backend/weights/best_dispense.pt"
    yolo_pcb_aoi_path: str = "backend/weights/best_pcb_aoi.pt"
    yolo_conf: float = 0.25
    yolo_iou: float = 0.45
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"
    cors_origins: str = "http://localhost:8443,http://127.0.0.1:8443"

    # Supabase cloud knowledge-base (optional — leave blank to disable cloud features)
    supabase_url: str = ""
    supabase_service_key: str = ""


    def _resolve_model_path(self, raw_path: str, default_name: str) -> Path:
        raw = Path(raw_path)
        candidates = [
            raw if raw.is_absolute() else ROOT / raw,
            raw if raw.is_absolute() else BACKEND_DIR / raw,
            BACKEND_DIR / "weights" / default_name,
            ROOT / "backend" / "weights" / default_name,
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return raw if raw.is_absolute() else ROOT / raw

    @property
    def model_path(self) -> Path:
        return self._resolve_model_path(self.yolo_model_path, "best.pt")

    @property
    def dispense_model_path(self) -> Path:
        return self._resolve_model_path(self.yolo_dispense_path, "best_dispense.pt")

    @property
    def pcb_aoi_model_path(self) -> Path:
        return self._resolve_model_path(self.yolo_pcb_aoi_path, "best_pcb_aoi.pt")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
