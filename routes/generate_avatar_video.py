from fastapi import HTTPException, Form, APIRouter, Request
from pydantic import BaseModel
import os
import time
import gc
import requests
import tempfile
import subprocess
import json
from urllib.parse import urlparse
import config
from utils.logging_setup import logger
from utils.file_handler import download_file, check_file_size, clean_temp_files
from services.google_drive import upload_to_drive
import whisper
from moviepy import AudioFileClip
from rembg import remove
from PIL import Image
import glob

router = APIRouter()

class AvatarVideoRequest(BaseModel):
    image_url: str
    input_text: str
    avatar_id: str
    voice_id: str

# HeyGen API configuration
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
HEYGEN_BASE_URL = "https://api.heygen.com"
HEYGEN_HEADERS = {
    "Accept": "application/json",
    "X-Api-Key": HEYGEN_API_KEY
}

@router.post("/generate-avatar-video")
async def generate_avatar_video(request: AvatarVideoRequest):
    image_url = request.image_url
    input_text = request.input_text
    avatar_id = request.avatar_id
    voice_id = request.voice_id

    """Generate video from image with AI avatar generated from input text"""
    
    timestamp = int(time.time())
    temp_files = []
    
    try:
        # Download image
        logger.info("Downloading image...")
        image_data, image_format = download_file(image_url, is_audio=False)
        
        # Validate image format
        if image_format not in config.SUPPORTED_IMAGE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image format: {image_format}"
            )

        # Create temporary file paths
        image_path = os.path.join(config.TEMP_DIR, f"temp_image_{timestamp}.{image_format}")
        avatar_video_path = os.path.join(config.TEMP_DIR, f"avatar_video_{timestamp}.mp4")
        avatar_audio_path = os.path.join(config.TEMP_DIR, f"avatar_audio_{timestamp}.wav")
        transparent_avatar_path = os.path.join(config.TEMP_DIR, f"transparent_avatar_{timestamp}.mp4")
        final_video_path = os.path.join(config.TEMP_DIR, f"output_video_{timestamp}.mp4")
        
        temp_files.extend([image_path, avatar_video_path, avatar_audio_path, transparent_avatar_path, final_video_path])

        # Save downloaded image
        with open(image_path, 'wb') as f:
            f.write(image_data)

        # Check file size
        check_file_size(image_path)

        # Verify file exists
        if not os.path.exists(image_path):
            raise HTTPException(
                status_code=500,
                detail="Failed to save temporary image file"
            )
        
        # Generate HeyGen avatar video
        logger.info("Generating AI avatar video through HeyGen...")
        video_id = generate_heygen_video(input_text, avatar_id, voice_id)
        
        # Poll until video is ready and get download URL
        logger.info(f"Waiting for HeyGen video {video_id} to complete...")
        avatar_video_url, duration = poll_video_status(video_id)
        
        # Download the avatar video
        logger.info(f"Downloading avatar video from: {avatar_video_url}")
        download_heygen_video(avatar_video_url, avatar_video_path)
        
        # Extract audio from the avatar video
        logger.info("Extracting audio from avatar video...")
        extract_audio_from_video(avatar_video_path, avatar_audio_path)
        
        # Remove white background from avatar video
        logger.info("Removing white background from avatar video...")
        remove_background(avatar_video_path, transparent_avatar_path)
        
        # Create final video with avatar overlay and subtitles
        logger.info("Creating final video with avatar overlay and subtitles...")
        create_video_with_avatar_overlay(image_path, transparent_avatar_path, avatar_audio_path, final_video_path)
        
        # Upload to Google Drive
        logger.info("Uploading video to Google Drive...")
        drive_links = upload_to_drive(final_video_path)
        
        # Clean up memory
        gc.collect()
        
        return {
            "status": "success",
            "message": "Avatar video created and uploaded successfully",
            "video_url": drive_links["shareable_link"],
            "download_url": drive_links["download_link"],
            "duration": duration,
            "detected_formats": {
                "image": image_format
            }
        }
            
    except Exception as e:
        logger.error(f"Error in generate_avatar_video: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )
    finally:
        # Clean up temporary files
        clean_temp_files(temp_files)


def generate_heygen_video(input_text, avatar_id, voice_id):
    """Generate avatar video using HeyGen API"""
    
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": input_text,
                    "voice_id": voice_id,
                    "speed": 1.0,
                    "pitch": 1.0
                }
            }
        ],
        "dimension": {
            "width": 1280,
            "height": 720
        }
    }

    response = requests.post(
        f"{HEYGEN_BASE_URL}/v2/video/generate", 
        headers=HEYGEN_HEADERS, 
        json=payload
    )
    
    if response.status_code != 200:
        logger.error(f"HeyGen API error: {response.text}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate avatar video: {response.text}"
        )
    
    response_data = response.json()
    
    if response_data.get("error"):
        raise HTTPException(
            status_code=500,
            detail=f"HeyGen API error: {response_data['error']}"
        )
    
    return response_data["data"]["video_id"]


def poll_video_status(video_id, max_retries=100, retry_delay=25):
    """Poll the video status until it's completed or timeout"""
    
    for _ in range(max_retries):
        status_url = f"{HEYGEN_BASE_URL}/v1/video_status.get?video_id={video_id}"
        response = requests.get(status_url, headers=HEYGEN_HEADERS)
        
        if response.status_code != 200:
            logger.error(f"Error checking video status: {response.text}")
            time.sleep(retry_delay)
            continue
        
        status_data = response.json()
        
        if status_data["code"] != 100:
            logger.error(f"HeyGen status code error: {status_data}")
            time.sleep(retry_delay)
            continue
            
        if status_data["data"]["status"] == "completed":
            video_url = status_data["data"]["video_url"]
            duration = status_data["data"]["duration"]
            return video_url, duration
        
        if status_data["data"]["status"] == "failed" or status_data["data"]["error"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Avatar video generation failed: {status_data['data'].get('error', 'Unknown error')}"
            )
            
        logger.info(f"Video status: {status_data['data']['status']}. Waiting {retry_delay} seconds...")
        time.sleep(retry_delay)
    
    raise HTTPException(
        status_code=500,
        detail=f"Timeout waiting for avatar video to complete processing"
    )


def download_heygen_video(url, output_path):
    """Download the HeyGen video to a local file"""
    response = requests.get(url, stream=True)
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download avatar video"
        )
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    return output_path


def extract_audio_from_video(video_path, audio_path):
    """Extract audio from video file using FFmpeg"""
    command = [
        "ffmpeg", "-i", video_path, 
        "-vn", "-acodec", "pcm_s16le", 
        "-ar", "44100", "-ac", "2", 
        audio_path, "-y"
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode()}")
        raise HTTPException(
            status_code=500,
            detail="Failed to extract audio from avatar video"
        )

# def remove_background(input_video: str, output_video: str, temp_dir: str = "temp_frames"):
#     # Step 1: Create temp directory
#     os.makedirs(temp_dir, exist_ok=True)

#     # Step 2: Extract frames
#     subprocess.run([
#         "ffmpeg", "-i", input_video,
#         os.path.join(temp_dir, "frame_%04d.png"),
#         "-hide_banner", "-loglevel", "error"
#     ], check=True)

#     # Step 3: Process each frame
#     for frame_path in sorted(glob.glob(os.path.join(temp_dir, "frame_*.png"))):
#         with open(frame_path, "rb") as i:
#             input_img = i.read()
#             output_img = remove(input_img)
#             with open(frame_path, "wb") as o:
#                 o.write(output_img)

#     # Step 4: Rebuild video from processed frames
#     subprocess.run([
#         "ffmpeg", "-framerate", "30", "-i", os.path.join(temp_dir, "frame_%04d.png"),
#         "-c:v", "libx264", "-pix_fmt", "yuva420p", output_video,
#         "-y", "-hide_banner", "-loglevel", "error"
#     ], check=True)

#     # Optional: Clean up
#     for f in glob.glob(os.path.join(temp_dir, "*.png")):
#         os.remove(f)
#     os.rmdir(temp_dir)

def remove_background(input_video: str, output_video: str, temp_dir: str = "temp_frames"):
    """Remove background from video frames and create a transparent video"""
    # Create temp directory
    os.makedirs(temp_dir, exist_ok=True)
    temp_files = []
    
    try:
        # Step 1: Extract frames
        logger.info("Extracting frames from avatar video...")
        subprocess.run([
            "ffmpeg", "-i", input_video,
            os.path.join(temp_dir, "frame_%04d.png"),
            "-hide_banner", "-loglevel", "error"
        ], check=True)
        
        # Step 2: Process each frame - remove background
        logger.info("Removing background from frames...")
        frame_files = sorted(glob.glob(os.path.join(temp_dir, "frame_*.png")))
        if not frame_files:
            raise HTTPException(status_code=500, detail="No frames extracted from video")
            
        for frame_path in frame_files:
            with open(frame_path, "rb") as i:
                input_img = i.read()
                output_img = remove(input_img)  # rembg removes background
                with open(frame_path, "wb") as o:
                    o.write(output_img)
        
        # Step 3: Rebuild video from processed frames with alpha channel
        logger.info("Creating transparent video from processed frames...")
        
        # Get original video framerate for more accurate reproduction
        fps_output = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v", "-of", 
            "default=noprint_wrappers=1:nokey=1", "-show_entries", "stream=r_frame_rate", 
            input_video
        ]).decode().strip()
        
        # Parse fps (usually in format "30000/1001" or similar)
        if '/' in fps_output:
            num, den = map(int, fps_output.split('/'))
            fps = num / den
        else:
            fps = float(fps_output)
        
        # Ensure fps is a reasonable value
        if fps <= 0 or fps > 120:
            fps = 30  # Default fallback
        
        # Create video with transparency
        subprocess.run([
            "ffmpeg", "-framerate", str(fps), 
            "-i", os.path.join(temp_dir, "frame_%04d.png"),
            "-c:v", "libx264", 
            "-pix_fmt", "yuva420p", 
            "-filter:v", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure dimensions are even (required by yuva420p)
            "-shortest",
            "-movflags", "+faststart",
            "-y", output_video
        ], check=True)
        
        # Verify output was created
        if not os.path.exists(output_video) or os.path.getsize(output_video) < 1000:
            raise HTTPException(status_code=500, detail="Failed to create transparent avatar video")
        
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
        logger.error(f"FFmpeg error in remove_background: {error_message}")
        raise HTTPException(status_code=500, detail=f"Error removing background: {error_message}")
    finally:
        # Clean up temporary files
        for f in glob.glob(os.path.join(temp_dir, "*.png")):
            os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


# def create_video_with_avatar_overlay(image_path, avatar_path, audio_path, output_path):
#     """Create final video with avatar overlay and subtitles using FFmpeg"""
#     try:
#         # Load Whisper model for transcription
#         logger.info("Loading Whisper Tiny model...")
#         model = whisper.load_model("tiny")
        
#         # Transcribe audio from the avatar
#         logger.info("Transcribing audio...")
#         result = model.transcribe(audio_path, verbose=False)
#         segments = result['segments']
        
#         # Get audio duration
#         audio_clip = AudioFileClip(audio_path)
#         duration = audio_clip.duration
#         audio_clip.close()
        
#         # Create temporary subtitle file
#         timestamp = int(time.time())
#         srt_path = os.path.join(config.TEMP_DIR, f"sub_{timestamp}.srt")
        
#         logger.info(f"Creating subtitle file at: {srt_path}")
#         with open(srt_path, "w", encoding="utf-8") as srt_file:
#             for i, seg in enumerate(segments, start=1):
#                 start = format_timestamp(seg['start'])
#                 end = format_timestamp(seg['end'])
#                 text = seg['text'].strip()
#                 srt_file.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        
#         # Create a temporary video from image and avatar without subtitles first
#         logger.info("Creating video with avatar overlay...")
#         temp_video = os.path.join(config.TEMP_DIR, f"temp_{timestamp}.mp4")
        
#         # Combine background image with transparent avatar overlay
#         subprocess.run([
#             "ffmpeg", "-y",
#             "-loop", "1", "-i", image_path,
#             "-i", avatar_path,
#             "-i", audio_path,
#             "-filter_complex",
#             "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[bg];"
#             "[1:v]scale=480:-1[avatar];"
#             "[bg][avatar]overlay=W-w-50:H-h-50[outv]",
#             "-map", "[outv]",
#             "-map", "2:a",
#             "-c:v", "libx264",
#             "-c:a", "aac",
#             "-shortest",
#             temp_video
#         ], check=True)
        
#         # Create a simpler method for subtitles - burn them directly on the video
#         logger.info("Adding subtitles and watermark to video...")
        
#         # Create a temporary file with simpler name in a known location
#         temp_srt = "temp_sub.srt"
#         with open(temp_srt, "w", encoding="utf-8") as f:
#             with open(srt_path, "r", encoding="utf-8") as original:
#                 f.write(original.read())
        
#         # Now use the watermark if it exists
#         watermark_path = "watermark.png"
#         if os.path.exists(watermark_path):
#             # Use a simpler filter chain for both subtitles and watermark
#              subprocess.run([
#                 "ffmpeg", "-y",
#                 "-i", temp_video,
#                 "-i", watermark_path,
#                 "-filter_complex",
#                 f"subtitles=temp_sub.srt[sub];[1:v]scale=iw*0.15:-1[wm];[sub][wm]overlay=10:H-h-50[v]",
#                 "-map", "[v]",
#                 "-map", "0:a",
#                 "-c:a", "copy",
#                 output_path
#             ], check=True)
#         else:
#             # Just add subtitles if no watermark
#             subprocess.run([
#                 "ffmpeg", "-y",
#                 "-i", temp_video,
#                 "-vf", "subtitles=temp_sub.srt",
#                 "-c:a", "copy",
#                 output_path
#             ], check=True)
        
#         # Clean up temporary files
#         if os.path.exists(temp_video):
#             os.remove(temp_video)
#         if os.path.exists(srt_path):
#             os.remove(srt_path)
#         if os.path.exists(temp_srt):
#             os.remove(temp_srt)
        
#         return duration
        
#     except subprocess.CalledProcessError as e:
#         error_message = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
#         logger.error(f"FFmpeg error: {error_message}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to create final video: {error_message}"
#         )
#     except Exception as e:
#         logger.error(f"Error creating video with avatar: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Error creating video with avatar: {str(e)}"
#         )

def create_video_with_avatar_overlay(image_path, avatar_path, audio_path, output_path):
    """Create final video with avatar overlay and subtitles using FFmpeg"""
    try:
        # Load Whisper model for transcription
        logger.info("Loading Whisper Tiny model...")
        model = whisper.load_model("tiny")
        
        # Transcribe audio from the avatar
        logger.info("Transcribing audio...")
        result = model.transcribe(audio_path, verbose=False)
        segments = result['segments']
        
        # Get audio duration
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        audio_clip.close()
        
        # Create temporary subtitle file
        timestamp = int(time.time())
        srt_path = os.path.join(config.TEMP_DIR, f"sub_{timestamp}.srt")
        
        logger.info(f"Creating subtitle file at: {srt_path}")
        with open(srt_path, "w", encoding="utf-8") as srt_file:
            for i, seg in enumerate(segments, start=1):
                start = format_timestamp(seg['start'])
                end = format_timestamp(seg['end'])
                text = seg['text'].strip()
                srt_file.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        
        # Create a temporary video from image and avatar without subtitles first
        logger.info("Creating video with avatar overlay...")
        temp_video = os.path.join(config.TEMP_DIR, f"temp_{timestamp}.mp4")
        
        # Combine background image with transparent avatar overlay
        # The key is to ensure the avatar's alpha channel is respected
        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-i", avatar_path,
            "-i", audio_path,
            "-filter_complex",
            "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[bg];"
            "[1:v]format=yuva420p,scale=480:-1[avatar];"  # Ensure format maintains alpha
            "[bg][avatar]overlay=W-w-50:H-h-70:format=yuv420p[outv]",  # Position higher up (70px from bottom)
            "-map", "[outv]",
            "-map", "2:a",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            temp_video
        ], check=True)
        
        # Create a simpler method for subtitles - burn them directly on the video
        logger.info("Adding subtitles and watermark to video...")
        
        # Create a temporary file with simpler name in a known location
        temp_srt = "temp_sub.srt"
        with open(temp_srt, "w", encoding="utf-8") as f:
            with open(srt_path, "r", encoding="utf-8") as original:
                f.write(original.read())
        
        # Now use the watermark if it exists
        watermark_path = "watermark.png"
        if os.path.exists(watermark_path):
            # Use a simpler filter chain for both subtitles and watermark
            # Position watermark higher up (50px from bottom)
            subprocess.run([
                "ffmpeg", "-y",
                "-i", temp_video,
                "-i", watermark_path,
                "-filter_complex",
                f"subtitles=temp_sub.srt[sub];[1:v]scale=iw*0.15:-1[wm];[sub][wm]overlay=10:H-h-50[v]",
                "-map", "[v]",
                "-map", "0:a",
                "-c:a", "copy",
                output_path
            ], check=True)
        else:
            # Just add subtitles if no watermark
            subprocess.run([
                "ffmpeg", "-y",
                "-i", temp_video,
                "-vf", "subtitles=temp_sub.srt",
                "-c:a", "copy",
                output_path
            ], check=True)
        
        # Clean up temporary files
        if os.path.exists(temp_video):
            os.remove(temp_video)
        if os.path.exists(srt_path):
            os.remove(srt_path)
        if os.path.exists(temp_srt):
            os.remove(temp_srt)
        
        return duration
        
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
        logger.error(f"FFmpeg error: {error_message}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create final video: {error_message}"
        )
    except Exception as e:
        logger.error(f"Error creating video with avatar: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating video with avatar: {str(e)}"
        )
    

def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


@router.get("/available-voices")
async def get_available_voices():
    """Get available voices from HeyGen"""
    try:
        response = requests.get(f"{HEYGEN_BASE_URL}/v2/voices", headers=HEYGEN_HEADERS)
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code, 
                detail="Failed to fetch voices from HeyGen"
            )
        return response.json()
    except Exception as e:
        logger.error(f"Error getting voices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching voices: {str(e)}"
        )