from fastapi import FastAPI, Request
import requests
from moviepy.editor import ImageClip, AudioFileClip
import uuid
import os

app = FastAPI()

@app.post("/generate-video")
async def generate_video(req: Request):
    data = await req.json()
    image_url = data["image_url"]
    audio_url = data["audio_url"]

    # Download image
    image_path = f"{uuid.uuid4()}.jpg"
    with open(image_path, "wb") as f:
        f.write(requests.get(image_url).content)

    # Download audio
    audio_path = f"{uuid.uuid4()}.mp3"
    with open(audio_path, "wb") as f:
        f.write(requests.get(audio_url).content)

    # Create video
    video_path = f"{uuid.uuid4()}.mp4"
    clip = ImageClip(image_path).set_duration(AudioFileClip(audio_path).duration)
    clip = clip.set_audio(AudioFileClip(audio_path))
    clip.write_videofile(video_path, fps=24)

    # For now, return dummy success response
    return {"status": "success", "video": video_path}


