from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.gemini_client import GeminiClient, GeminiError
from app.jobs import render_jobs
from app.schemas import AnalyzeRequest, AnalyzeResponse, RenderRequest
from app.segments import build_candidate_clips
from app.transcript import TranscriptError, fetch_transcript
from app.youtube_client import YouTubeClient, YouTubeError


app = FastAPI(
    title="Viral Clip Finder",
    version="0.1.0",
    description="Find likely viral YouTube clip moments from transcript and comment evidence.",
)

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
PROJECT_DIR = APP_DIR.parent

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    return run_analysis(request)


def run_analysis(request: AnalyzeRequest) -> AnalyzeResponse:
    settings = get_settings()
    gemini_api_key = request.gemini_api_key or settings.gemini_api_key
    youtube_api_key = request.youtube_api_key or settings.youtube_api_key
    try:
        if not gemini_api_key:
            raise RuntimeError("Missing Gemini API key. Add one in Settings.")
        if not youtube_api_key:
            raise RuntimeError("Missing YouTube API key. Add one in Settings.")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    youtube = YouTubeClient(youtube_api_key)
    gemini = GeminiClient(gemini_api_key, settings.gemini_model, timeout_sec=180)

    try:
        video_id = youtube.parse_video_id(str(request.youtube_url))
        video = youtube.get_video_metadata(video_id)
        comments = youtube.get_comments(video_id)
        transcript = fetch_transcript(video_id)
        candidates = build_candidate_clips(
            transcript=transcript,
            comments=comments,
            min_duration_sec=request.min_duration_sec,
            max_duration_sec=request.max_duration_sec,
        )
        clips = gemini.rank_clips(video, candidates, comments, request.max_clips)
    except YouTubeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TranscriptError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AnalyzeResponse(video=video, clips=clips)


@app.post("/render")
def render(request: RenderRequest) -> dict[str, object]:
    job = render_jobs.create(request, run_analysis)
    return job.to_dict()


@app.get("/render/jobs/{job_id}")
def render_job(job_id: str) -> dict[str, object]:
    job = render_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Render job not found")
    return job.to_dict()


@app.get("/files")
def files(path: str) -> FileResponse:
    resolved = Path(path).resolve()
    allowed_root = (PROJECT_DIR / "renders").resolve()
    if allowed_root not in [resolved, *resolved.parents] or not resolved.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(resolved)
