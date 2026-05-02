import time
import os
import json
from dotenv import load_dotenv
from app.jobs import render_jobs
from app.schemas import RenderRequest
from app.main import run_analysis

load_dotenv()

request = RenderRequest(
    youtube_url="https://www.youtube.com/watch?v=w9TAdQxshhg",
    max_clips=1,
    target_rank=1,
    gemini_api_key=os.getenv("GEMINI_API_KEY"),
    youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
    speed=1.1
)

print(f"Starting render job for target rank {request.target_rank}...")
job = render_jobs.create(request, run_analysis)
print(f"Job created: {job.id}")

while True:
    job = render_jobs.get(job.id)
    if not job:
        print("Job lost?")
        break
    
    # Using a simple print that won't overwhelm logs
    print(f"[{time.strftime('%H:%M:%S')}] Status: {job.status} | Phase: {job.phase} | Progress: {job.progress}/{job.total}")
    
    if job.status in ("completed", "failed", "cancelled"):
        break
    time.sleep(10)

if job.status == "completed":
    print("\nSUCCESS: Render complete!")
    print(f"Clip saved at: {job.files[0]}")
    # Print the clip details for confirmation
    if job.clips:
        print(f"Title: {job.clips[0]['title']}")
else:
    print(f"\nERROR: Render failed: {job.error}")
