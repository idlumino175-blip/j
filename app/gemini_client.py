import json
import re
from dataclasses import dataclass

import requests
from pydantic import ValidationError

from app.schemas import CandidateClip, ClipResult, VideoMetadata, YouTubeComment


class GeminiError(RuntimeError):
    pass


@dataclass
class GeminiClient:
    api_key: str
    model: str = "gemini-3-flash-preview"
    timeout_sec: int = 60

    @property
    def endpoint(self) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def rank_clips(
        self,
        video: VideoMetadata,
        candidates: list[CandidateClip],
        comments: list[YouTubeComment],
        max_clips: int,
        focus: str | None = None,
    ) -> list[ClipResult]:
        if not candidates:
            return []

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_prompt(video, candidates, comments, max_clips, focus)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        response = requests.post(
            self.endpoint,
            params={"key": self.api_key},
            json=payload,
            timeout=self.timeout_sec,
        )
        if response.status_code >= 400:
            raise GeminiError(response.text)

        text = extract_gemini_text(response.json())
        raw = parse_json(text)
        clips_data = raw.get("clips") if isinstance(raw, dict) else raw
        if not isinstance(clips_data, list):
            raise GeminiError("Gemini response did not contain a clips array")

        clips: list[ClipResult] = []
        for index, item in enumerate(clips_data[:max_clips], start=1):
            try:
                item["rank"] = index
                normalize_score_breakdown(item)
                clips.append(ClipResult.model_validate(item))
            except ValidationError as exc:
                raise GeminiError(f"Gemini returned invalid clip JSON: {exc}") from exc

        return normalize_clip_ranking(clips, video.duration_sec, max_clips)


def build_prompt(
    video: VideoMetadata,
    candidates: list[CandidateClip],
    comments: list[YouTubeComment],
    max_clips: int,
    focus: str | None = None,
) -> str:
    compact_candidates = [
        {
            "id": candidate.id,
            "start_sec": candidate.start_sec,
            "end_sec": candidate.end_sec,
            "text": candidate.text[:1800],
            "nearby_comment_evidence": candidate.nearby_comment_evidence[:5],
        }
        for candidate in candidates
    ]
    compact_comments = [
        {
            "text": comment.text[:300],
            "like_count": comment.like_count,
            "timestamp_refs_sec": comment.timestamp_refs_sec,
        }
        for comment in comments[:80]
    ]

    focus_text = f"Special focus for this run: {focus.strip()}\n\n" if focus else ""

    return (
        "You are a viral short-form video analyst. Rank candidate clips from a YouTube video. "
        "Do not guess randomly. Prefer clips that are self-contained, hook fast, have clear payoff, "
        "and are supported by viewer comment evidence. Penalize slow starts, vague context, and clips "
        "that require previous video context.\n\n"
        f"{focus_text}"
        f"Return exactly {max_clips} or fewer clips as strict JSON with this shape:\n"
        '{"clips":[{"rank":1,"start_sec":0,"end_sec":45,"score":90,"title":"...",'
        '"hook":"...","reason":"...","comment_evidence":["..."],'
        '"score_breakdown":{"hook":0,"clarity":0,"novelty":0,"emotion":0,'
        '"comment_match":0,"self_contained":0}}]}\n\n'
        "Each score_breakdown field must be an integer from 0 to 20. Total score must be 0 to 100. "
        "Use only candidate start/end timestamps. Keep reasons short and evidence-based.\n\n"
        f"Video:\n{video.model_dump_json()}\n\n"
        f"Top comments:\n{json.dumps(compact_comments, ensure_ascii=True)}\n\n"
        f"Candidate clips:\n{json.dumps(compact_candidates, ensure_ascii=True)}"
    )


def extract_gemini_text(response: dict) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiError("Gemini response did not include text") from exc


def parse_json(text: str):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiError("Gemini returned invalid JSON") from exc


def normalize_clip_ranking(clips: list[ClipResult], video_duration_sec: int, max_clips: int) -> list[ClipResult]:
    valid = [
        clip
        for clip in clips
        if 0 <= clip.start_sec < clip.end_sec <= video_duration_sec
    ]
    valid.sort(key=lambda clip: clip.score, reverse=True)
    for index, clip in enumerate(valid[:max_clips], start=1):
        clip.rank = index
    return valid[:max_clips]


def normalize_score_breakdown(item: dict) -> None:
    breakdown = item.setdefault("score_breakdown", {})
    for key in ("hook", "clarity", "novelty", "emotion", "comment_match", "self_contained"):
        breakdown.setdefault(key, 0)
