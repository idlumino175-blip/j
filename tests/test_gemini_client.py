import pytest

from app.gemini_client import GeminiError, normalize_clip_ranking, parse_json
from app.schemas import ClipResult, ScoreBreakdown


def make_clip(rank: int, start: int, end: int, score: int) -> ClipResult:
    return ClipResult(
        rank=rank,
        start_sec=start,
        end_sec=end,
        score=score,
        title="Title",
        hook="Hook",
        reason="Reason",
        comment_evidence=[],
        score_breakdown=ScoreBreakdown(
            hook=10,
            clarity=10,
            novelty=10,
            emotion=10,
            comment_match=10,
            self_contained=10,
        ),
    )


def test_parse_json_accepts_code_fence():
    assert parse_json('```json\n{"clips":[]}\n```') == {"clips": []}


def test_parse_json_rejects_invalid_json():
    with pytest.raises(GeminiError):
        parse_json("not json")


def test_normalize_clip_ranking_filters_invalid_and_sorts():
    clips = [
        make_clip(1, 0, 20, 70),
        make_clip(2, 30, 20, 99),
        make_clip(3, 10, 40, 90),
    ]
    ranked = normalize_clip_ranking(clips, video_duration_sec=100, max_clips=10)
    assert [clip.score for clip in ranked] == [90, 70]
    assert [clip.rank for clip in ranked] == [1, 2]
