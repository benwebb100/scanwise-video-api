from flask import Flask, request, jsonify
from flask_cors import CORS
from moviepy.editor import ImageClip, AudioFileClip
import os

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "./content"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/generate-video", methods=["POST"])
def generate_video():
    image = request.files.get("image")
    audio = request.files.get("audio")

    if not image or not audio:
        return jsonify({"error": "Both image and audio are required"}), 400

    image_path = os.path.join(UPLOAD_FOLDER, "input.jpg")
    audio_path = os.path.join(UPLOAD_FOLDER, "input.mp3")
    video_path = os.path.join(UPLOAD_FOLDER, "output.mp4")

    image.save(image_path)
    audio.save(audio_path)

    audio_clip = AudioFileClip(audio_path)
    image_clip = ImageClip(image_path, duration=audio_clip.duration)
    video = image_clip.set_audio(audio_clip)
    video.write_videofile(video_path, fps=24)

    return jsonify({"status": "success", "message": "Video created successfully"})
