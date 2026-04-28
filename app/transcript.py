from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi
from yt_dlp import YoutubeDL

from app.schemas import TranscriptItem


class TranscriptError(RuntimeError):
    pass


def fetch_transcript(video_id: str) -> list[TranscriptItem]:
    try:
        rows = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        return fetch_transcript_with_ytdlp(video_id, exc)
    except Exception as exc:
        return fetch_transcript_with_ytdlp(video_id, exc)

    transcript = [
        TranscriptItem(
            start_sec=float(row["start"]),
            duration_sec=float(row.get("duration", 0)),
            text=clean_caption_text(row.get("text", "")),
        )
        for row in rows
        if clean_caption_text(row.get("text", ""))
    ]
    if not transcript:
        raise TranscriptError("Transcript is empty")
    return transcript


def clean_caption_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def fetch_transcript_with_ytdlp(video_id: str, original_error: Exception) -> list[TranscriptItem]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    options = {
        "quiet": True,
        "skip_download": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "noplaylist": True,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise TranscriptError(f"Could not fetch transcript: {original_error}; yt-dlp fallback also failed: {exc}") from exc

    subtitle_url = choose_subtitle_url(info)
    if not subtitle_url:
        raise TranscriptError("Transcript is unavailable for this video")

    try:
        with YoutubeDL({"quiet": True}) as ydl:
            subtitle_text = ydl.urlopen(subtitle_url).read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise TranscriptError(f"Could not download transcript subtitles: {exc}") from exc

    transcript = parse_vtt(subtitle_text)
    if not transcript:
        raise TranscriptError("Transcript is empty")
    return transcript


def choose_subtitle_url(info: dict) -> str | None:
    for bucket_name in ("subtitles", "automatic_captions"):
        bucket = info.get(bucket_name) or {}
        for language in ("en", "en-US", "en-GB"):
            entries = bucket.get(language) or []
            vtt_entry = next((entry for entry in entries if entry.get("ext") == "vtt"), None)
            if vtt_entry and vtt_entry.get("url"):
                return vtt_entry["url"]
    return None


def parse_vtt(text: str) -> list[TranscriptItem]:
    transcript: list[TranscriptItem] = []
    current_start: float | None = None
    current_end: float | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "-->" in line:
            flush_vtt_block(transcript, current_start, current_end, current_lines)
            start_text, end_text = line.split("-->", 1)
            current_start = parse_vtt_timestamp(start_text.strip())
            current_end = parse_vtt_timestamp(end_text.strip().split()[0])
            current_lines = []
        elif not line:
            flush_vtt_block(transcript, current_start, current_end, current_lines)
            current_start = None
            current_end = None
            current_lines = []
        elif current_start is not None and not line.startswith(("WEBVTT", "Kind:", "Language:")):
            current_lines.append(strip_vtt_markup(line))

    flush_vtt_block(transcript, current_start, current_end, current_lines)
    return dedupe_transcript(transcript)


def flush_vtt_block(
    transcript: list[TranscriptItem],
    start_sec: float | None,
    end_sec: float | None,
    lines: list[str],
) -> None:
    if start_sec is None or end_sec is None or not lines:
        return
    text = clean_caption_text(" ".join(lines))
    if text:
        transcript.append(TranscriptItem(start_sec=start_sec, duration_sec=max(0.0, end_sec - start_sec), text=text))


def parse_vtt_timestamp(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def strip_vtt_markup(text: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text


def dedupe_transcript(transcript: list[TranscriptItem]) -> list[TranscriptItem]:
    cleaned: list[TranscriptItem] = []
    seen: set[tuple[float, str]] = set()
    for item in transcript:
        key = (round(item.start_sec, 2), item.text)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned
