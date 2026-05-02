from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.renderer import RenderError, download_source_video, render_vertical_blur_clip
from app.schemas import AnalyzeResponse, ClipResult, RenderRequest


JobRunner = Callable[[RenderRequest, str], AnalyzeResponse]


@dataclass
class RenderJob:
    id: str
    status: str
    phase: str
    progress: int
    total: int
    files: list[str] = field(default_factory=list)
    clips: list[dict] = field(default_factory=list)
    logs: list[dict] = field(default_factory=list)
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
            "logs": self.logs,
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
            # Immediate heartbeat log
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            job.logs.append({"time": timestamp, "msg": "Job received. Initializing background thread..."})

        thread = threading.Thread(target=self._run, args=(job.id, request, runner), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in ("completed", "failed", "cancelled"):
                return False
            job.status = "cancelled"
            job.phase = "Cancelled by user"
            job.updated_at = datetime.now(timezone.utc).isoformat()
            # Explicit cancel log
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            job.logs.append({"time": timestamp, "msg": "STOP: Process killed by user."})
            return True

    def add_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
                job.logs.append({"time": timestamp, "msg": message})
                job.updated_at = datetime.now(timezone.utc).isoformat()

    def _run(self, job_id: str, request: RenderRequest, runner: JobRunner) -> None:
        try:
            self._update(job_id, status="running", phase="Connecting")
            self.add_log(job_id, "System online. Connecting to intelligence stream...")
            if self._is_cancelled(job_id): return
            
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
            # Pass job_id so run_analysis can log internal steps
            analysis = runner(analysis_request, job_id)
            if self._is_cancelled(job_id): return

            if request.target_rank is not None:
                selected = [clip for clip in analysis.clips if clip.rank == request.target_rank]
            else:
                selected = [
                    clip for clip in analysis.clips if request.start_rank <= clip.rank < request.start_rank + request.max_clips
                ]
            
            self._update(job_id, total=len(selected), phase="Preparing forge")
            self.add_log(job_id, f"Found {len(selected)} moments to forge.")

            if self._is_cancelled(job_id): return

            output_root = Path("renders") / analysis.video.id
            source = download_source_video(str(request.youtube_url), output_root / "source")
            self.add_log(job_id, "Source video downloaded successfully.")

            clips_dir = output_root / "clips"

            for index, clip in enumerate(selected, start=1):
                if self._is_cancelled(job_id): return
                self._update(job_id, phase=f"Rendering clip {index}/{len(selected)}")
                self.add_log(job_id, f"Forging asset {index}: {clip.title}")
                path = render_vertical_blur_clip(
                    source_video=source,
                    clip=clip,
                    output_dir=clips_dir,
                    playback_speed=request.speed,
                    add_hook_title=request.add_hook_title,
                    style=request.style,
                )
                self._append_file(job_id, path, clip, index)

            if self._is_cancelled(job_id): return
            self._update(job_id, status="completed", phase="Completed")
            self.add_log(job_id, "All assets forged successfully.")
        except Exception as exc:
            if self._is_cancelled(job_id): return
            import traceback
            traceback.print_exc()
            self._update(job_id, status="failed", phase="Failed", error=str(exc))
            self.add_log(job_id, f"FATAL ERROR: {str(exc)}")

    def _is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return job is not None and job.status == "cancelled"

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
