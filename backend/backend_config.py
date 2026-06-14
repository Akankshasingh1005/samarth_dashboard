"""
Samarth Backend Configuration
Loads all settings from environment variables (.env file).
"""
import os
import sys
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "Samarth"
    APP_ENV: Literal["development", "production"] = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "info"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # --- MongoDB ---
    MONGO_URI: str
    MONGO_DB_NAME: str = "samarth"

    # --- Authentication ---
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Storage ---
    STORAGE_BACKEND: Literal["local", "cloudinary"] = "local"
    LOCAL_UPLOAD_DIR: str = "./uploads"

    # Cloudinary (optional — only needed in production)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # --- PS1 Pipeline ---
    PS1_PIPELINE_PATH: str = "../pipeline"
    PS1_STRIDE: int = 2
    PS1_ENHANCE: bool = True
    PS1_ENHANCE_LEVEL: Literal["auto", "light", "aggressive"] = "auto"
    PS1_SAVE_ANNOTATED_VIDEO: bool = False

    # --- PS2 Exercise Analysis ---
    PS2_MODEL_PATH: str = ""
    PS2_USE_REAL_MODEL: bool = False

    # --- PS3 Sensor Hub ---
    PS3_SENSOR_PORT: str = ""
    PS3_USE_REAL_SENSOR: bool = False
    PS3_BAUD_RATE: int = 115200

    # --- Email ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@samarth.health"

    # --- Reports ---
    REPORTS_DIR: str = "./reports"
    WEASYPRINT_ENABLED: bool = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, v):
        """Accept common deployment labels that may be supplied as DEBUG values."""
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "on"}:
                return True
        return v

    @field_validator("PS2_USE_REAL_MODEL", mode="before")
    @classmethod
    def auto_detect_ps2(cls, v, info):
        """Auto-enable real PS2 model if model path is set and file exists."""
        model_path = os.getenv("PS2_MODEL_PATH", "")
        if model_path:
            # Resolve relative paths from backend directory
            base = Path(__file__).parent
            resolved = (base / model_path).resolve()
            if resolved.exists():
                return True
        return v

    def get_ps1_path(self) -> Path:
        """Return absolute Path to the PS1 pipeline directory."""
        base = Path(__file__).parent
        return (base / self.PS1_PIPELINE_PATH).resolve()

    def get_ps2_model_path(self) -> str:
        """Return resolved absolute path to the PS2 model weights file."""
        if not self.PS2_MODEL_PATH:
            return ""
        base = Path(__file__).parent
        resolved = (base / self.PS2_MODEL_PATH).resolve()
        return str(resolved)

    def ensure_dirs(self):
        """Create necessary local directories."""
        os.makedirs(self.LOCAL_UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.REPORTS_DIR, exist_ok=True)
        os.makedirs("./static/exercises", exist_ok=True)


# Singleton settings instance used everywhere
settings = Settings()
