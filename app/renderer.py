import json
import re
import subprocess
import sys
from pathlib import Path

from app.config import get_ytdlp_cookies_file
from app.schemas import ClipResult


class RenderError(RuntimeError):
    pass


def safe_filename(value: str, fallback: str = "clip") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned[:80] or fallback


def download_source_video(youtube_url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_source = output_dir / "source.mp4"
    if existing_source.exists() and existing_source.stat().st_size > 10_000_000:
        return existing_source

    output_template = str(output_dir / "source.%(ext)s")
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--remote-components",
        "ejs:github",
        "-f",
        "bv*[height<=1080]+ba/b[height<=1080]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        output_template,
        youtube_url,
    ]
    cookies_file = get_ytdlp_cookies_file()
    if cookies_file:
        command[3:3] = ["--cookies", cookies_file]
    run_command(command, cwd=Path.cwd())

    source = output_dir / "source.mp4"
    if source.exists():
        return source

    matches = sorted(output_dir.glob("source.*"))
    if not matches:
        raise RenderError("yt-dlp did not produce a source video")
    return matches[0]


def render_vertical_blur_clip(
    source_video: Path,
    clip: ClipResult,
    output_dir: Path,
    playback_speed: float = 1.1,
    silence_threshold_db: int = -35,
    min_silence_sec: float = 0.45,
    add_hook_title: bool = False,
    top_caption: str | None = None,
    style: str = "blur",
    crop_position: str = "center",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{clip.rank:02d}_{safe_filename(clip.title)}.mp4"
    if output_path.exists() and output_path.stat().st_size > 1_000_000:
        return output_path
    if output_path.exists():
        output_path.unlink()

    tight_start, tight_end = tighten_clip_bounds(
        source_video=source_video,
        start_sec=clip.start_sec,
        end_sec=clip.end_sec,
        silence_threshold_db=silence_threshold_db,
    )
    duration = max(1.0, tight_end - tight_start)

    has_audio = source_has_audio(source_video)
    filter_complex = build_filter_complex(
        has_audio=has_audio,
        playback_speed=playback_speed,
        silence_threshold_db=silence_threshold_db,
        min_silence_sec=min_silence_sec,
        style=style,
        crop_position=crop_position,
    )
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{tight_start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_video),
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
    ]
    if has_audio:
        command.extend(["-map", "[aout]"])
    command.extend(
        [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_path),
        ]
    )
    run_command(command, cwd=Path.cwd())
    return output_path


def render_clips_from_analysis(
    youtube_url: str,
    clips: list[ClipResult],
    output_root: Path,
    playback_speed: float = 1.1,
    add_hook_title: bool = False,
    top_caption: str | None = None,
    style: str = "blur",
    crop_position: str = "center",
) -> list[Path]:
    source_dir = output_root / "source"
    clips_dir = output_root / "clips"
    source_video = download_source_video(youtube_url, source_dir)
    rendered = [
        render_vertical_blur_clip(
            source_video,
            clip,
            clips_dir,
            playback_speed=playback_speed,
            add_hook_title=add_hook_title,
            top_caption=top_caption,
            style=style,
            crop_position=crop_position,
        )
        for clip in clips
    ]
    manifest = {
        "youtube_url": youtube_url,
        "source_video": str(source_video),
        "clips": [str(path) for path in rendered],
    }
    (output_root / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return rendered


def run_command(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Command failed"
        raise RenderError(message)


def build_filter_complex(
    has_audio: bool,
    playback_speed: float,
    silence_threshold_db: int,
    min_silence_sec: float,
    style: str = "blur",
    crop_position: str = "center",
) -> str:
    setpts_factor = 1 / playback_speed
    # We ignore style 'blur' and force black background as requested
    if style == "full":
        video_base = build_full_video_filter(setpts_factor)
    else:
        video_base = build_black_box_video_filter(setpts_factor)
    
    if not has_audio:
        return video_base

    audio = f"; [0:a]{atempo_chain(playback_speed)} [aout]"
    return video_base + audio


def build_blur_video_filter(setpts_factor: float) -> str:
    # Replaced blur with black background
    return build_black_box_video_filter(setpts_factor)


def build_black_box_video_filter(setpts_factor: float) -> str:
    return (
        "color=c=black:s=1080x1920:r=30 [bg]; "
        f"[0:v]setpts={setpts_factor:.6f}*PTS, "
        "scale=1080:1920:force_original_aspect_ratio=decrease, "
        "setsar=1 [fg]; "
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1 [vout]"
    )


def build_full_video_filter(setpts_factor: float) -> str:
    return (
        f"[0:v]setpts={setpts_factor:.6f}*PTS, "
        "scale=1080:1920:force_original_aspect_ratio=increase, "
        "crop=1080:1920, "
        f"setsar=1 [vout]"
    )


def atempo_chain(speed: float) -> str:
    remaining = speed
    filters: list[str] = []
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.6f}")
    return ",".join(filters)


def source_has_audio(source_video: Path) -> bool:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "csv=p=0",
        str(source_video),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0 and "audio" in result.stdout


def tighten_clip_bounds(
    source_video: Path,
    start_sec: int,
    end_sec: int,
    silence_threshold_db: int,
    edge_padding_sec: float = 0.18,
) -> tuple[float, float]:
    duration = max(1, end_sec - start_sec)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-ss",
        str(start_sec),
        "-t",
        str(duration),
        "-i",
        str(source_video),
        "-af",
        f"silencedetect=noise={silence_threshold_db}dB:d=0.25",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return float(start_sec), float(end_sec)

    silences = parse_silencedetect(result.stderr)
    leading_end = 0.0
    trailing_start = float(duration)

    for silence_start, silence_end in silences:
        if silence_start <= 0.08:
            leading_end = max(leading_end, silence_end)
        if silence_end >= duration - 0.08:
            trailing_start = min(trailing_start, silence_start)

    tight_start = min(start_sec + max(0.0, leading_end - edge_padding_sec), end_sec - 1)
    tight_end = max(start_sec + 1, start_sec + min(duration, trailing_start + edge_padding_sec))

    if tight_end - tight_start < 8:
        return float(start_sec), float(end_sec)
    return tight_start, tight_end


def parse_silencedetect(log_text: str) -> list[tuple[float, float]]:
    starts: list[float] = []
    silences: list[tuple[float, float]] = []
    for line in log_text.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            starts.append(float(start_match.group(1)))
            continue
        end_match = re.search(r"silence_end:\s*([0-9.]+)", line)
        if end_match and starts:
            silences.append((starts.pop(0), float(end_match.group(1))))
    return silences
