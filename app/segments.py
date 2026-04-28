import re

from app.schemas import CandidateClip, TranscriptItem, YouTubeComment


def build_candidate_clips(
    transcript: list[TranscriptItem],
    comments: list[YouTubeComment],
    min_duration_sec: int,
    max_duration_sec: int,
    max_candidates: int = 80,
) -> list[CandidateClip]:
    candidates: list[CandidateClip] = []
    if not transcript:
        return candidates

    stride_sec = max(10, min_duration_sec // 2)
    video_end = int(max(item.start_sec + item.duration_sec for item in transcript))
    starts = list(range(0, max(1, video_end - min_duration_sec + 1), stride_sec))

    timestamp_seconds = sorted({ref for comment in comments for ref in comment.timestamp_refs_sec})
    for ref in timestamp_seconds:
        starts.extend([max(0, ref - 10), max(0, ref - 20)])

    seen: set[tuple[int, int]] = set()
    for raw_start in sorted(set(starts)):
        start = snap_to_caption_start(transcript, raw_start)
        end = choose_window_end(transcript, start, min_duration_sec, max_duration_sec)
        if end <= start or end - start < min_duration_sec:
            continue

        key = (start, end)
        if key in seen:
            continue
        seen.add(key)

        text = transcript_text_between(transcript, start, end)
        if not text or is_low_value_text(text):
            continue

        evidence = evidence_for_window(comments, start, end)
        candidates.append(
            CandidateClip(
                id=f"clip_{len(candidates) + 1}",
                start_sec=start,
                end_sec=end,
                text=text,
                nearby_comment_evidence=evidence[:5],
            )
        )

    candidates.sort(key=lambda candidate: (len(candidate.nearby_comment_evidence), len(candidate.text)), reverse=True)
    return candidates[:max_candidates]


def snap_to_caption_start(transcript: list[TranscriptItem], start_sec: int) -> int:
    nearby = min(transcript, key=lambda item: abs(item.start_sec - start_sec))
    return int(max(0, nearby.start_sec))


def choose_window_end(
    transcript: list[TranscriptItem],
    start_sec: int,
    min_duration_sec: int,
    max_duration_sec: int,
) -> int:
    min_end = start_sec + min_duration_sec
    max_end = start_sec + max_duration_sec
    possible_ends = [
        int(item.start_sec + item.duration_sec)
        for item in transcript
        if min_end <= item.start_sec + item.duration_sec <= max_end and looks_like_sentence_end(item.text)
    ]
    if possible_ends:
        return possible_ends[0]
    return min(max_end, int(max(item.start_sec + item.duration_sec for item in transcript)))


def transcript_text_between(transcript: list[TranscriptItem], start_sec: int, end_sec: int) -> str:
    parts = [
        item.text
        for item in transcript
        if item.start_sec >= start_sec and item.start_sec < end_sec
    ]
    return " ".join(parts)


def evidence_for_window(comments: list[YouTubeComment], start_sec: int, end_sec: int) -> list[str]:
    evidence: list[str] = []
    for comment in comments:
        has_timestamp_hit = any(start_sec - 15 <= ref <= end_sec + 15 for ref in comment.timestamp_refs_sec)
        has_strong_reaction = bool(re.search(r"\b(best|insane|crazy|wild|true|agree|wrong|love|funny|wow|mind blown)\b", comment.text, re.I))
        if has_timestamp_hit or (has_strong_reaction and len(comment.text) <= 220):
            evidence.append(comment.text)
    return evidence


def looks_like_sentence_end(text: str) -> bool:
    return bool(re.search(r"[.!?][\"')\]]?$", text.strip()))


def is_low_value_text(text: str) -> bool:
    words = text.split()
    if len(words) < 20:
        return True
    filler_words = sum(1 for word in words if word.lower().strip(".,!?") in {"um", "uh", "like", "yeah"})
    return filler_words / max(1, len(words)) > 0.18
