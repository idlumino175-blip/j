from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    youtube_api_key: str = ""

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
