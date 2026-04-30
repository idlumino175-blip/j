from functools import lru_cache
import hashlib
import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    youtube_api_key: str = ""
    ytdlp_cookies_file: str = ""
    ytdlp_cookies_content: str = ""

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
    if settings.ytdlp_cookies_file:
        return settings.ytdlp_cookies_file

    cookies_content = settings.ytdlp_cookies_content.strip()
    if not cookies_content:
        return ""

    normalized_content = cookies_content.replace("\\n", "\n")
    digest = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()[:16]
    cookies_path = Path(tempfile.gettempdir()) / f"yt_dlp_cookies_{digest}.txt"
    if not cookies_path.exists():
        cookies_path.write_text(normalized_content + "\n", encoding="utf-8")
    return str(cookies_path)
