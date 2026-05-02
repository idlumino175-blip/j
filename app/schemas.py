from pydantic import BaseModel, Field, HttpUrl, field_validator


class AnalyzeRequest(BaseModel):
    youtube_url: HttpUrl
    max_clips: int = Field(default=10, ge=1, le=25)
    min_duration_sec: int = Field(default=20, ge=5, le=180)
    max_duration_sec: int = Field(default=75, ge=10, le=300)
    gemini_api_key: str | None = Field(default=None, min_length=1)
    youtube_api_key: str | None = Field(default=None, min_length=1)

    @field_validator("max_duration_sec")
    @classmethod
    def max_must_exceed_min(cls, value: int, info):
        min_duration = info.data.get("min_duration_sec")
        if min_duration is not None and value < min_duration:
            raise ValueError("max_duration_sec must be greater than or equal to min_duration_sec")
        return value


class RenderRequest(AnalyzeRequest):
    start_rank: int = Field(default=1, ge=1, le=25)
    speed: float = Field(default=1.1, ge=0.75, le=2.0)
    target_rank: int | None = Field(default=None, ge=1, le=25)
    style: str = Field(default="blur")
    add_hook_title: bool = Field(default=False)


class VideoMetadata(BaseModel):
    id: str
    title: str
    duration_sec: int
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0


class ScoreBreakdown(BaseModel):
    hook: int = Field(ge=0, le=20)
    clarity: int = Field(ge=0, le=20)
    novelty: int = Field(ge=0, le=20)
    emotion: int = Field(ge=0, le=20)
    comment_match: int = Field(ge=0, le=20)
    self_contained: int = Field(ge=0, le=20)


class ClipResult(BaseModel):
    rank: int = Field(ge=1)
    start_sec: int = Field(ge=0)
    end_sec: int = Field(ge=0)
    score: int = Field(ge=0, le=100)
    title: str
    hook: str
    reason: str
    comment_evidence: list[str] = Field(default_factory=list)
    score_breakdown: ScoreBreakdown


class AnalyzeResponse(BaseModel):
    video: VideoMetadata
    clips: list[ClipResult]


class TranscriptItem(BaseModel):
    start_sec: float
    duration_sec: float
    text: str


class CandidateClip(BaseModel):
    id: str
    start_sec: int
    end_sec: int
    text: str
    nearby_comment_evidence: list[str] = Field(default_factory=list)


class YouTubeComment(BaseModel):
    text: str
    like_count: int = 0
    published_at: str | None = None
    timestamp_refs_sec: list[int] = Field(default_factory=list)
