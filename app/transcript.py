import re

from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from yt_dlp import YoutubeDL

from app.config import get_ytdlp_cookies_file
from app.schemas import TranscriptItem


class TranscriptError(RuntimeError):
    pass


# Broad language list — we try everything, not just English
_PREFERRED_LANGUAGES = [
    "en", "en-US", "en-GB", "en-AU", "en-IN", "en-CA",
    "hi", "es", "fr", "de", "pt", "pt-BR", "ja", "ko",
    "zh-Hans", "zh-Hant", "ar", "ru", "it", "nl", "tr",
    "pl", "id", "vi", "th", "sv", "da", "fi", "no",
]


def fetch_transcript(video_id: str) -> list[TranscriptItem]:
    """
    Try to get a transcript using three strategies in order:
    1. youtube-transcript-api with a wide list of languages (incl. auto-generated)
    2. youtube-transcript-api: grab ANY available transcript (whatever language)
    3. yt-dlp subtitle download as a final fallback
    """
    # --- Strategy 1: preferred languages via youtube-transcript-api ---
    try:
        rows = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=_PREFERRED_LANGUAGES,
            preserve_formatting=False,
        )
        transcript = _rows_to_items(rows)
        if transcript:
            return transcript
    except (NoTranscriptFound, TranscriptsDisabled, CouldNotRetrieveTranscript):
        pass
    except Exception:
        pass

    # --- Strategy 2: grab ANY available transcript ---
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # prefer manually created, then auto-generated
        chosen = None
        for t in transcript_list:
            if not t.is_generated:
                chosen = t
                break
        if chosen is None:
            for t in transcript_list:
                chosen = t
                break
        if chosen is not None:
            rows = chosen.fetch()
            transcript = _rows_to_items(rows)
            if transcript:
                return transcript
    except (NoTranscriptFound, TranscriptsDisabled, CouldNotRetrieveTranscript):
        pass
    except Exception:
        pass

    # --- Strategy 3: yt-dlp fallback (With Cookies) ---
    try:
        return fetch_transcript_with_ytdlp(video_id, use_cookies=True)
    except TranscriptError as exc_with_cookies:
        # --- Strategy 4: yt-dlp fallback (Without Cookies - in case cookies are poisoned/expired) ---
        try:
            return fetch_transcript_with_ytdlp(video_id, use_cookies=False)
        except TranscriptError:
            # Raise the original error if both failed
            raise exc_with_cookies


def _rows_to_items(rows) -> list[TranscriptItem]:
    items = [
        TranscriptItem(
            start_sec=float(row["start"]),
            duration_sec=float(row.get("duration", 0)),
            text=clean_caption_text(row.get("text", "")),
        )
        for row in rows
        if clean_caption_text(row.get("text", ""))
    ]
    return items


def clean_caption_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def fetch_transcript_with_ytdlp(video_id: str, use_cookies: bool = True) -> list[TranscriptItem]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    cookies_file = get_ytdlp_cookies_file() if use_cookies else None

    options = {
        "quiet": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-orig", "en-US", "all"],
        "noplaylist": True,
        "ignore_no_formats_error": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
    }
    if cookies_file:
        options["cookiefile"] = cookies_file

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise TranscriptError(
            f"This video's transcript could not be retrieved. "
            f"Please try a video with captions enabled. (Detail: {exc})"
        ) from exc

    subtitle_url = choose_subtitle_url(info)
    if not subtitle_url:
        raise TranscriptError(
            "This video has no available captions or transcript. "
            "Please try a different video — ideally one with auto-generated or manual subtitles enabled."
        )

    try:
        subtitle_options = {"quiet": True}
        if cookies_file:
            subtitle_options["cookiefile"] = cookies_file
        with YoutubeDL(subtitle_options) as ydl:
            subtitle_text = ydl.urlopen(subtitle_url).read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise TranscriptError(f"Could not download transcript subtitles: {exc}") from exc

    transcript = parse_vtt(subtitle_text)
    if not transcript:
        raise TranscriptError(
            "Captions were found but appear to be empty. "
            "Please try a video with more spoken content."
        )
    return transcript


def choose_subtitle_url(info: dict) -> str | None:
    # Check manual subtitles first, then auto-generated
    for bucket_name in ("subtitles", "automatic_captions"):
        bucket = info.get(bucket_name) or {}
        if not bucket:
            continue
        # Prefer English variants, then fall back to any language
        language_order = ["en", "en-orig", "en-US", "en-GB"]
        language_order.extend(lang for lang in bucket if lang.startswith("en-") and lang not in language_order)
        language_order.extend(lang for lang in bucket if lang not in language_order)
        for language in language_order:
            entries = bucket.get(language) or []
            # prefer vtt, fall back to json3 or srv3
            for preferred_ext in ("vtt", "json3", "srv3", "srv2", "srv1", "ttml"):
                entry = next((e for e in entries if e.get("ext") == preferred_ext), None)
                if entry and entry.get("url"):
                    return entry["url"]
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
        elif current_start is not None and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
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
        transcript.append(
            TranscriptItem(
                start_sec=start_sec,
                duration_sec=max(0.0, end_sec - start_sec),
                text=text,
            )
        )


def parse_vtt_timestamp(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def strip_vtt_markup(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
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
