import whisper
import subprocess
from fastapi import HTTPException
from utils.logging_setup import logger
import os

def create_video(image_path: str, audio_path: str, video_path: str) -> float:
    """Create video from image and audio, hard-burn subtitles using ffmpeg and Whisper Tiny"""
    try:
        logger.info("Loading Whisper Tiny model...")
        model = whisper.load_model("tiny")

        logger.info("Transcribing audio...")
        result = model.transcribe(audio_path, verbose=False)
        segments = result['segments']

        # Load audio to get duration
        from moviepy import AudioFileClip
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        # Create temporary subtitle file
        srt_path = "temp_subtitles.srt"
        with open(srt_path, "w", encoding="utf-8") as srt_file:
            for i, seg in enumerate(segments, start=1):
                start = format_timestamp(seg['start'])
                end = format_timestamp(seg['end'])
                text = seg['text'].strip()
                srt_file.write(f"{i}\n{start} --> {end}\n{text}\n\n")

        # Create a temporary video from image and audio
        logger.info("Creating temporary video...")
        temp_video = "temp_video.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-shortest",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-vf", "scale=1280:720",
            temp_video
        ], check=True)

        # Path to watermark image
        watermark_path = "watermark.png"
        
        # Burn subtitles and add watermark to the video
        logger.info("Burning subtitles and adding watermark...")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", temp_video,
            "-i", watermark_path,
            "-filter_complex", 
            # Scale the watermark to 15% of its original size and position it in the bottom left
            f"subtitles={srt_path}[sub];[1:v]scale=iw*0.15:-1[watermark];[sub][watermark]overlay=10:H-h-10[v]",
            "-map", "[v]", 
            "-map", "0:a",
            "-c:a", "copy",
            video_path
        ], check=True)

        # Cleanup
        os.remove(temp_video)
        os.remove(srt_path)

        return duration

    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating video: {str(e)}")


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


def concat_videos(prefix_path: str, main_path: str, output_path: str):
    """Concatenate two videos using ffmpeg"""
    try:
        # Create a temporary file list for ffmpeg concat
        concat_list_path = "concat_list.txt"
        with open(concat_list_path, "w") as f:
            f.write(f"file '{os.path.abspath(prefix_path)}'\n")
            f.write(f"file '{os.path.abspath(main_path)}'\n")
        
        # Concatenate videos
        logger.info("Concatenating prefix and main video...")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ], check=True)
        
        # Cleanup
        os.remove(concat_list_path)
        
    except Exception as e:
        logger.error(f"Error concatenating videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error concatenating videos: {str(e)}")