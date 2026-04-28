import pytest

from app.youtube_client import YouTubeClient, YouTubeError, extract_timestamp_refs, parse_iso8601_duration


def test_parse_video_id_variants():
    client = YouTubeClient("key")
    assert client.parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert client.parse_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert client.parse_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert client.parse_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_parse_video_id_invalid():
    client = YouTubeClient("key")
    with pytest.raises(YouTubeError):
        client.parse_video_id("https://example.com/watch?v=dQw4w9WgXcQ")


def test_extract_timestamp_refs():
    assert extract_timestamp_refs("best part 4:21 and 1:02:03") == [261, 3723]


def test_parse_iso8601_duration():
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration("PT45S") == 45
