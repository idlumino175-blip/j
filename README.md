# Viral Clip Finder Web

Clean FastAPI web app for finding likely viral YouTube clip moments from transcript and comment evidence, then rendering vertical HD clips.

## Setup

```powershell
cd viral-clip-finder-web
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Fill `.env` with:

```env
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3-flash-preview
YOUTUBE_API_KEY=...
YTDLP_COOKIES_FILE=
YTDLP_COOKIES_CONTENT=
```

Use `YTDLP_COOKIES_FILE` locally when you have a cookie file path. On Vercel, use `YTDLP_COOKIES_CONTENT` and paste the Netscape cookie text as the secret value.

## Run

```powershell
uvicorn app.main:app --reload --port 8010
```

Open `http://127.0.0.1:8010`.

## Render Style

Rendered clips are saved under `renders/<video_id>/clips/` as 1080x1920 MP4 files with:

- blurred background
- centered original video
- no hook title overlay by default
- lip-sync-safe start/end trimming
- 1.1x playback speed by default
