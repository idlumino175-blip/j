import argparse
from pathlib import Path

from app.config import get_settings
from app.gemini_client import GeminiClient
from app.renderer import render_clips_from_analysis
from app.segments import build_candidate_clips
from app.transcript import fetch_transcript
from app.youtube_client import YouTubeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a YouTube video and render HD vertical blurred clips.")
    parser.add_argument("youtube_url")
    parser.add_argument("--max-clips", type=int, default=5)
    parser.add_argument("--start-rank", type=int, default=1)
    parser.add_argument("--min-duration-sec", type=int, default=20)
    parser.add_argument("--max-duration-sec", type=int, default=75)
    parser.add_argument("--output-dir", default="renders")
    parser.add_argument("--speed", type=float, default=1.1)
    parser.add_argument("--hook-title", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    settings.require_gemini_key()
    settings.require_youtube_key()

    youtube = YouTubeClient(settings.youtube_api_key)
    video_id = youtube.parse_video_id(args.youtube_url)
    video = youtube.get_video_metadata(video_id)
    comments = youtube.get_comments(video_id)
    transcript = fetch_transcript(video_id)
    candidates = build_candidate_clips(
        transcript=transcript,
        comments=comments,
        min_duration_sec=args.min_duration_sec,
        max_duration_sec=args.max_duration_sec,
    )
    clips = GeminiClient(settings.gemini_api_key, settings.gemini_model).rank_clips(
        video=video,
        candidates=candidates,
        comments=comments,
        max_clips=max(args.max_clips + args.start_rank - 1, args.max_clips),
    )
    clips = [clip for clip in clips if args.start_rank <= clip.rank < args.start_rank + args.max_clips]

    output_root = Path(args.output_dir) / video_id
    rendered = render_clips_from_analysis(
        args.youtube_url,
        clips,
        output_root,
        playback_speed=args.speed,
        add_hook_title=args.hook_title,
    )
    print(f"Rendered {len(rendered)} clips:")
    for path in rendered:
        print(path.resolve())


if __name__ == "__main__":
    main()
