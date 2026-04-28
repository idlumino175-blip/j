import re
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import requests

from app.schemas import VideoMetadata, YouTubeComment


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeError(RuntimeError):
    pass


@dataclass
class YouTubeClient:
    api_key: str
    timeout_sec: int = 20

    def parse_video_id(self, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")

        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]
        elif host.endswith("youtube.com"):
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif parsed.path.startswith("/shorts/"):
                video_id = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else ""
            elif parsed.path.startswith("/embed/"):
                video_id = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else ""
            else:
                video_id = ""
        else:
            video_id = ""

        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
            raise YouTubeError("Invalid YouTube video URL")
        return video_id

    def get_video_metadata(self, video_id: str) -> VideoMetadata:
        data = self._get(
            "videos",
            {
                "part": "snippet,contentDetails,statistics",
                "id": video_id,
                "maxResults": 1,
            },
        )
        items = data.get("items", [])
        if not items:
            raise YouTubeError("Video not found or unavailable")

        item = items[0]
        stats = item.get("statistics", {})
        return VideoMetadata(
            id=video_id,
            title=item["snippet"]["title"],
            duration_sec=parse_iso8601_duration(item["contentDetails"]["duration"]),
            view_count=int(stats.get("viewCount", 0)),
            like_count=int(stats.get("likeCount", 0)),
            comment_count=int(stats.get("commentCount", 0)),
        )

    def get_comments(self, video_id: str, max_comments: int = 150) -> list[YouTubeComment]:
        comments: list[YouTubeComment] = []
        page_token: str | None = None

        while len(comments) < max_comments:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, max_comments - len(comments)),
                "order": "relevance",
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                data = self._get("commentThreads", params)
            except YouTubeError as exc:
                if "commentsDisabled" in str(exc) or "disabled comments" in str(exc).lower():
                    return []
                raise

            for item in data.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                text = snippet.get("textDisplay") or snippet.get("textOriginal") or ""
                comments.append(
                    YouTubeComment(
                        text=text,
                        like_count=int(snippet.get("likeCount", 0)),
                        published_at=snippet.get("publishedAt"),
                        timestamp_refs_sec=extract_timestamp_refs(text),
                    )
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return comments

    def _get(self, resource: str, params: dict) -> dict:
        params = {**params, "key": self.api_key}
        response = requests.get(f"{YOUTUBE_API_BASE}/{resource}", params=params, timeout=self.timeout_sec)
        if response.status_code >= 400:
            raise YouTubeError(response.text)
        return response.json()


def extract_timestamp_refs(text: str) -> list[int]:
    refs: list[int] = []
    for match in re.finditer(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b", text):
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        refs.append(hours * 3600 + minutes * 60 + seconds)
    return refs


def parse_iso8601_duration(value: str) -> int:
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return 0
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return int(timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds())
