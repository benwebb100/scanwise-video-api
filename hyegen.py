from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
import subprocess
import uuid
from fastapi.responses import FileResponse

import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="HeyGen Avatar Video API")

HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
BASE_URL = "https://api.heygen.com/v2"

headers = {
    "Accept": "application/json",
    "X-Api-Key": HEYGEN_API_KEY
}

# Pydantic models for request bodies
class VideoRequest(BaseModel):
    avatar_id: str
    voice_id: str
    input_text: str
    width: int = 1280
    height: int = 720
    speed: float = 1.0
    pitch: float = 1.0

def remove_background(input_video, output_video):
    """Remove white background and preserve transparency in a .webm output"""
    
    # Ensure output is .webm
    if not output_video.endswith(".webm"):
        output_video = output_video.rsplit(".", 1)[0] + ".webm"

    command = [
        "ffmpeg", "-i", input_video,
        "-vf", "colorkey=white:0.1:0.5,format=yuva420p",
        "-c:v", "libvpx",              # WebM codec with alpha support
        "-pix_fmt", "yuva420p",
        "-auto-alt-ref", "0",          # required for transparency
        "-an",                         # disable audio for simplicity (optional)
        output_video, "-y"
    ]

    try:
        subprocess.run(command, check=True, capture_output=True)
        if not os.path.exists(output_video) or os.path.getsize(output_video) < 1000:
            raise Exception("Output video file is missing or too small after background removal")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode()}")
        raise HTTPException(status_code=500, detail="Failed to remove background")

@app.get("/avatars")
def list_avatars():
    """Retrieve available avatars."""
    response = requests.get(f"{BASE_URL}/avatars", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch avatars.")
    return response.json()

@app.get("/voices")
def list_voices():
    """Retrieve available voices."""
    response = requests.get(f"{BASE_URL}/voices", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch voices.")
    return response.json()

@app.post("/generate")
def generate_video(request: VideoRequest):
    """Generate an avatar video."""
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": request.avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": request.input_text,
                    "voice_id": request.voice_id,
                    "speed": request.speed,
                    "pitch": request.pitch
                }
            }
        ],
        "dimension": {
            "width": request.width,
            "height": request.height
        }
    }

    response = requests.post(f"{BASE_URL}/video/generate", headers=headers, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to generate video.")
    return response.json()

@app.get("/status/{video_id}")
def check_status(video_id: str):
    """Check the status of a generated video."""
    status_url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
    response = requests.get(status_url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch video status.")
    return response.json()


@app.post("/remove-background")
async def remove_bg(file: UploadFile = File(...)):
    input_path = f"temp/{uuid.uuid4()}.mp4"
    output_path = input_path.replace(".mp4", ".webm")

    with open(input_path, "wb") as f:
        f.write(await file.read())

    remove_background(input_path, output_path)

    return FileResponse(
        output_path,
        media_type="video/webm",
        filename="transparent_avatar.webm"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # To run the server, use the command: uvicorn hyegen:app --reload
    # Ensure you have the required packages installed:
    # pip install fastapi uvicorn requests python-dotenv