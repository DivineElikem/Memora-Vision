from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Memora Vision"
    database_path: Path = Path("data/vision_assistant.sqlite3")
    upload_dir: Path = Path("data/uploads")
    keyframe_dir: Path = Path("data/keyframes")
    vision_mock_mode: bool = False
    frame_sample_seconds: float = 1.5
    alert_cooldown_seconds: int = 20
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    vlm_base_url: str | None = None
    vlm_api_key: str | None = None
    vlm_model: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    cors_origins: list[str] = ["*"]

    # SMTP Settings (Mock by default)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_sender: str = "alerts@agenticvision.com"
    alert_email_receiver: str = "user@example.com"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.keyframe_dir.mkdir(parents=True, exist_ok=True)
    return settings

