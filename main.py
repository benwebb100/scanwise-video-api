from fastapi import FastAPI, File, UploadFile
import uvicorn
from moviepy.editor import ImageClip, AudioFileClip
import os

app = FastAPI()

@app.post("/generate-video")
async def generate_video(image: UploadFile = File(...), audio: UploadFile = File(...)):
    # Save the uploaded image
    image_path = f"temp_image_{image.filename}"
    with open(image_path, "wb") as f:
        f.write(await image.read())

    # Save the uploaded audio
    audio_path = f"temp_audio_{audio.filename}"
    with open(audio_path, "wb") as f:
        f.write(await audio.read())

    # Create video using moviepy
    video_path = "output_video.mp4"
    clip = ImageClip(image_path, duration=5)  # show image for 5 seconds
    clip = clip.set_audio(AudioFileClip(audio_path))
    clip.write_videofile(video_path, fps=24)

    # Clean up
    os.remove(image_path)
    os.remove(audio_path)

    return {"message": "Video created", "video_path": video_path}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
