from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.renderer import RenderError, download_source_video, render_vertical_blur_clip
from app.schemas import AnalyzeResponse, ClipResult, RenderRequest


JobRunner = Callable[[RenderRequest], AnalyzeResponse]


@dataclass
class RenderJob:
    id: str
    status: str
    phase: str
    progress: int
    total: int
    files: list[str] = field(default_factory=list)
    clips: list[dict] = field(default_factory=list)
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "phase": self.phase,
            "progress": self.progress,
            "total": self.total,
            "files": self.files,
            "clips": self.clips,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class RenderJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, RenderJob] = {}
        self._lock = threading.Lock()

    def create(self, request: RenderRequest, runner: JobRunner) -> RenderJob:
        job = RenderJob(
            id=uuid.uuid4().hex,
            status="queued",
            phase="Queued",
            progress=0,
            total=request.max_clips,
        )
        with self._lock:
            self._jobs[job.id] = job

        thread = threading.Thread(target=self._run, args=(job.id, request, runner), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job_id: str, request: RenderRequest, runner: JobRunner) -> None:
        try:
            self._update(job_id, status="running", phase="Analyzing video")
            analysis_request = RenderRequest(
                youtube_url=request.youtube_url,
                max_clips=max(request.max_clips + request.start_rank - 1, request.max_clips),
                min_duration_sec=request.min_duration_sec,
                max_duration_sec=request.max_duration_sec,
                gemini_api_key=request.gemini_api_key,
                youtube_api_key=request.youtube_api_key,
                start_rank=request.start_rank,
                speed=request.speed,
                target_rank=request.target_rank,
            )
            analysis = runner(analysis_request)
            if request.target_rank is not None:
                selected = [clip for clip in analysis.clips if clip.rank == request.target_rank]
            else:
                selected = [
                    clip for clip in analysis.clips if request.start_rank <= clip.rank < request.start_rank + request.max_clips
                ]
            self._update(job_id, total=len(selected), phase="Downloading source")

            output_root = Path("renders") / analysis.video.id
            source = download_source_video(str(request.youtube_url), output_root / "source")
            clips_dir = output_root / "clips"

            for index, clip in enumerate(selected, start=1):
                self._update(job_id, phase=f"Rendering clip {index}/{len(selected)}")
                path = render_vertical_blur_clip(
                    source_video=source,
                    clip=clip,
                    output_dir=clips_dir,
                    playback_speed=request.speed,
                    add_hook_title=False,
                    style="black-box",
                )
                self._append_file(job_id, path, clip, index)

            self._update(job_id, status="completed", phase="Completed")
        except (RenderError, Exception) as exc:
            self._update(job_id, status="failed", phase="Failed", error=str(exc))

    def _append_file(self, job_id: str, path: Path, clip: ClipResult, progress: int) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.files.append(str(path.resolve()))
            job.clips.append(clip.model_dump())
            job.progress = progress
            job.updated_at = datetime.now(timezone.utc).isoformat()

    def _update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        phase: str | None = None,
        progress: int | None = None,
        total: int | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if status is not None:
                job.status = status
            if phase is not None:
                job.phase = phase
            if progress is not None:
                job.progress = progress
            if total is not None:
                job.total = total
            if error is not None:
                job.error = error
            job.updated_at = datetime.now(timezone.utc).isoformat()


render_jobs = RenderJobStore()
