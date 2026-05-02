from functools import lru_cache
import hashlib
import os
import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    youtube_api_key: str = ""
    ytdlp_cookies_file: str = ""
    ytdlp_cookies_content: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    daily_free_renders: int = 3
    auth_enabled: bool = True
    
    firebase_api_key: str = ""
    firebase_auth_domain: str = ""
    firebase_project_id: str = ""
    firebase_storage_bucket: str = ""
    firebase_messaging_sender_id: str = ""
    firebase_app_id: str = ""
    firebase_measurement_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def require_gemini_key(self) -> None:
        if not self.gemini_api_key:
            raise RuntimeError("Missing GEMINI_API_KEY in .env")

    def require_youtube_key(self) -> None:
        if not self.youtube_api_key:
            raise RuntimeError("Missing YOUTUBE_API_KEY in .env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_ytdlp_cookies_file() -> str:
    settings = get_settings()
    cookies_content_file = write_ytdlp_cookies_content(settings.ytdlp_cookies_content)
    if os.getenv("VERCEL") and cookies_content_file:
        return cookies_content_file

    if settings.ytdlp_cookies_file and Path(settings.ytdlp_cookies_file).exists():
        return settings.ytdlp_cookies_file

    return cookies_content_file


def write_ytdlp_cookies_content(cookies_content: str) -> str:
    cookies_content = cookies_content.strip()
    if not cookies_content:
        return ""

    normalized_content = cookies_content.replace("\\n", "\n")
    digest = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()[:16]
    cookies_path = Path(tempfile.gettempdir()) / f"yt_dlp_cookies_{digest}.txt"
    if not cookies_path.exists():
        cookies_path.write_text(normalized_content + "\n", encoding="utf-8")
    return str(cookies_path)
