from app.schemas import TranscriptItem, YouTubeComment
from app.segments import build_candidate_clips


def test_build_candidate_clips_uses_timestamp_comment_evidence():
    transcript = [
        TranscriptItem(start_sec=i * 5, duration_sec=5, text=f"This is useful sentence number {i}.")
        for i in range(30)
    ]
    comments = [YouTubeComment(text="The part at 0:45 is wild", timestamp_refs_sec=[45])]

    clips = build_candidate_clips(transcript, comments, min_duration_sec=20, max_duration_sec=45)

    assert clips
    assert any("0:45" in evidence for clip in clips for evidence in clip.nearby_comment_evidence)
    assert all(20 <= clip.end_sec - clip.start_sec <= 45 for clip in clips)
