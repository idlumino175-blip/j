from app import config
from app.config import Settings, get_ytdlp_cookies_file


def test_vercel_prefers_cookie_content_over_bad_local_path(monkeypatch):
    config.get_settings.cache_clear()
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(
        config,
        "Settings",
        lambda: Settings(
            ytdlp_cookies_file=r"C:\Users\popat\Downloads\youtube.txt",
            ytdlp_cookies_content="# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\ttest",
        ),
    )

    cookies_file = get_ytdlp_cookies_file()

    assert cookies_file
    assert "Downloads" not in cookies_file
    assert "youtube.txt" not in cookies_file
    config.get_settings.cache_clear()
