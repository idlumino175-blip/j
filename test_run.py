import json
from app.main import run_analysis
from app.schemas import AnalyzeRequest, VideoMetadata, YouTubeComment, CandidateClip
from app.youtube_client import YouTubeClient
from app.gemini_client import GeminiClient
from app.transcript import fetch_transcript
from app.segments import build_candidate_clips
from pydantic import HttpUrl
import os
from dotenv import load_dotenv

load_dotenv()

youtube_api_key = os.getenv("YOUTUBE_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL")
youtube_url = "https://www.youtube.com/watch?v=w9TAdQxshhg"

def test():
    youtube = YouTubeClient(youtube_api_key)
    # Using the model from .env
    gemini = GeminiClient(gemini_api_key, gemini_model, timeout_sec=300)

    print(f"Parsing URL: {youtube_url}")
    video_id = youtube.parse_video_id(youtube_url)
    
    print("Fetching metadata...")
    video = youtube.get_video_metadata(video_id)
    print(f"Video: {video.title}")
    
    print("Fetching comments...")
    comments = youtube.get_comments(video_id)
    print(f"Found {len(comments)} comments")
    
    print("Fetching transcript...")
    transcript = fetch_transcript(video_id)
    print(f"Transcript fetched: {len(transcript)} lines")
    
    print("Building candidates...")
    candidates = build_candidate_clips(transcript, comments, 20, 75, max_candidates=40)
    print(f"Built {len(candidates)} candidates")
    
    print(f"Ranking clips with Gemini ({gemini_model})...")
    clips = gemini.rank_clips(video, candidates, comments, 1)
    print("Ranking complete!")
    
    for clip in clips:
        print(f"\nClip Rank {clip.rank}: {clip.title}")
        print(f"Start: {clip.start_sec}s, End: {clip.end_sec}s")
        print(f"Score: {clip.score}")
        print(f"Hook: {clip.hook}")

if __name__ == "__main__":
    test()
