# from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Body
# import uvicorn
# from moviepy import VideoFileClip, ImageClip, AudioFileClip
# import os
# import shutil
# from typing import Optional, Union
# import logging
# import io
# import time
# from pydantic import BaseModel
# import base64
# import magic
# import json

# # Set up logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# app = FastAPI(title="Video Generation API")

# # Ensure temp directory exists
# os.makedirs("temp", exist_ok=True)

# class FileInput(BaseModel):
#     image_type: str  # "binary" or "hex"
#     audio_type: str  # "binary" or "hex"
#     image_format: Optional[str] = None  # jpg, png, etc.
#     audio_format: Optional[str] = None  # mp3, wav, etc.

# SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp']
# SUPPORTED_AUDIO_FORMATS = ['mp3', 'wav', 'aac', 'm4a', 'ogg']

# def read_binary_file(file_path: str) -> bytes:
#     """Read binary file"""
#     with open(file_path, 'rb') as f:
#         return f.read()

# def read_hex_file(file_path: str) -> bytes:
#     """Read hex file and convert to bytes"""
#     with open(file_path, 'r') as f:
#         hex_str = f.read().replace(" ", "").replace("\n", "")
#         return bytes.fromhex(hex_str)

# @app.post("/generate-video")
# async def generate_video(
#     file_input: str = Form(...),
#     image_file: UploadFile = File(...),
#     audio_file: UploadFile = File(...),
#     duration: Optional[float] = Form(5.0)
# ):
#     """
#     Generate video from image and audio files.
#     Files can be either binary or hex format.
#     """
    
#     # Parse file_input JSON string to FileInput model
#     try:
#         file_input_json = json.loads(file_input)
#         file_input_obj = FileInput(**file_input_json)
#     except Exception as e:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Invalid file_input format: {str(e)}"
#         )
    
#     timestamp = int(time.time())
#     temp_files = []
    
#     try:
#         # Save uploaded files temporarily
#         temp_image_upload = f"temp/temp_upload_image_{timestamp}"
#         temp_audio_upload = f"temp/temp_upload_audio_{timestamp}"
        
#         # Save uploaded files
#         with open(temp_image_upload, 'wb') as f:
#             content = await image_file.read()
#             f.write(content)
        
#         with open(temp_audio_upload, 'wb') as f:
#             content = await audio_file.read()
#             f.write(content)
            
#         temp_files.extend([temp_image_upload, temp_audio_upload])

#         # Process files based on type
#         try:
#             if file_input_obj.image_type.lower() == "binary":
#                 image_data = read_binary_file(temp_image_upload)
#             elif file_input_obj.image_type.lower() == "hex":
#                 image_data = read_hex_file(temp_image_upload)
#             else:
#                 raise HTTPException(
#                     status_code=400,
#                     detail="Invalid image_type. Must be 'binary' or 'hex'"
#                 )

#             if file_input_obj.audio_type.lower() == "binary":
#                 audio_data = read_binary_file(temp_audio_upload)
#             elif file_input_obj.audio_type.lower() == "hex":
#                 audio_data = read_hex_file(temp_audio_upload)
#             else:
#                 raise HTTPException(
#                     status_code=400,
#                     detail="Invalid audio_type. Must be 'binary' or 'hex'"
#                 )

#         except ValueError as e:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Error processing hex file: {str(e)}"
#             )

#         # Detect or use provided formats
#         mime = magic.Magic(mime=True)
#         image_format = (file_input_obj.image_format or 
#                        mime.from_buffer(image_data).split('/')[-1])
#         audio_format = (file_input_obj.audio_format or 
#                        mime.from_buffer(audio_data).split('/')[-1])

#         # Validate formats
#         if image_format.lower() not in SUPPORTED_IMAGE_FORMATS:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Unsupported image format: {image_format}"
#             )
        
#         if audio_format.lower() not in SUPPORTED_AUDIO_FORMATS:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Unsupported audio format: {audio_format}"
#             )

#         # Create paths with appropriate extensions
#         image_path = f"temp/temp_image_{timestamp}.{image_format}"
#         audio_path = f"temp/temp_audio_{timestamp}.{audio_format}"
#         video_path = f"temp/output_video_{timestamp}.mp4"
        
#         temp_files.extend([image_path, audio_path])

#         # Save processed data
#         with open(image_path, 'wb') as f:
#             f.write(image_data)
#         with open(audio_path, 'wb') as f:
#             f.write(audio_data)

#         # Create video using moviepy
#         image_clip = None
#         audio_clip = None
        
#         try:
#             image_clip = ImageClip(image_path, duration=duration)
#             audio_clip = AudioFileClip(audio_path)
            
#             final_duration = min(duration, audio_clip.duration)
#             image_clip = image_clip.with_duration(final_duration)
            
#             final_clip = image_clip.with_audio(audio_clip)
            
#             final_clip.write_videofile(
#                 video_path,
#                 fps=24,
#                 codec='libx264',
#                 audio_codec='aac'
#             )
            
#             return {
#                 "status": "success",
#                 "message": "Video created successfully",
#                 "video_path": video_path,
#                 "duration": final_duration,
#                 "formats": {
#                     "image": image_format,
#                     "audio": audio_format
#                 }
#             }
            
#         finally:
#             if image_clip: image_clip.close()
#             if audio_clip: audio_clip.close()
            
#             # Clean up temporary files
#             for file_path in temp_files:
#                 try:
#                     if os.path.exists(file_path):
#                         os.remove(file_path)
#                         logger.info(f"Cleaned up: {file_path}")
#                 except Exception as e:
#                     logger.error(f"Error cleaning up {file_path}: {str(e)}")

#     except Exception as e:
#         # Clean up on error
#         for file_path in temp_files:
#             try:
#                 if os.path.exists(file_path):
#                     os.remove(file_path)
#             except:
#                 pass
#         raise HTTPException(
#             status_code=500,
#             detail=f"Error processing request: {str(e)}"
#         )

# @app.get("/supported-formats")
# async def get_supported_formats():
#     return {
#         "image_formats": SUPPORTED_IMAGE_FORMATS,
#         "audio_formats": SUPPORTED_AUDIO_FORMATS,
#         "file_types": ["binary", "hex"]
#     }

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)



from fastapi import FastAPI, HTTPException, Form
import uvicorn
from moviepy import ImageClip, AudioFileClip
import os
import logging
import time
import requests
import mimetypes
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video Generation API")

# Ensure temp directory exists
os.makedirs("temp", exist_ok=True)

SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp']
SUPPORTED_AUDIO_FORMATS = ['mp3', 'wav', 'aac', 'm4a', 'ogg']

# Format mapping
MIME_TO_FORMAT = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/bmp': 'bmp',
    'image/webp': 'webp',
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/wav': 'wav',
    'audio/aac': 'aac',
    'audio/m4a': 'm4a',
    'audio/ogg': 'ogg'
}

def detect_format(content_type: str, url: str, is_audio: bool = False) -> str:
    """Detect format from content type or URL"""
    # Get format from MIME mapping
    format_ext = MIME_TO_FORMAT.get(content_type.lower())
    
    if not format_ext:
        # Try to get extension from URL
        ext = url.split('.')[-1].lower()
        if ext in SUPPORTED_IMAGE_FORMATS or ext in SUPPORTED_AUDIO_FORMATS:
            format_ext = ext
        else:
            # Default fallbacks
            format_ext = 'mp3' if is_audio else 'jpg'
    
    return format_ext

def download_file(url: str, is_audio: bool = False) -> tuple[bytes, str]:
    """Download file from URL and detect its format"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get content type from response headers
        content_type = response.headers.get('content-type', '')
        
        # Detect format using the new function
        format_ext = detect_format(content_type, url, is_audio)
        
        logger.info(f"Detected format: {format_ext} from content-type: {content_type}")
        return response.content, format_ext
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading file from {url}: {str(e)}"
        )

@app.post("/generate-video")
async def generate_video(
    image_url: str = Form(...),
    audio_url: str = Form(...),
    duration: Optional[float] = Form(5.0)
):
    """
    Generate video from image and audio URLs.
    Expects Google Drive download URLs.
    """
    
    timestamp = int(time.time())
    temp_files = []
    
    try:
        # Download files and detect formats
        logger.info("Downloading image...")
        image_data, image_format = download_file(image_url, is_audio=False)
        
        logger.info("Downloading audio...")
        audio_data, audio_format = download_file(audio_url, is_audio=True)
        
        # Validate formats
        if image_format not in SUPPORTED_IMAGE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image format: {image_format}"
            )
        
        if audio_format not in SUPPORTED_AUDIO_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {audio_format}"
            )

        # Create temporary file paths
        image_path = f"temp/temp_image_{timestamp}.{image_format}"
        audio_path = f"temp/temp_audio_{timestamp}.{audio_format}"
        video_path = f"temp/output_video_{timestamp}.mp4"
        
        temp_files.extend([image_path, audio_path, video_path])

        # Save downloaded files
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        with open(audio_path, 'wb') as f:
            f.write(audio_data)

        # Create video using moviepy
        image_clip = None
        audio_clip = None
        
        try:
            logger.info("Creating video...")
            image_clip = ImageClip(image_path, duration=duration)
            audio_clip = AudioFileClip(audio_path)
            
            final_duration = min(duration, audio_clip.duration)
            image_clip = image_clip.with_duration(final_duration)
            
            final_clip = image_clip.with_audio(audio_clip)
            
            final_clip.write_videofile(
                video_path,
                fps=24,
                codec='libx264',
                audio_codec='aac'
            )
            
            return {
                "status": "success",
                "message": "Video created successfully",
                "video_path": video_path,
                "duration": final_duration,
                "detected_formats": {
                    "image": image_format,
                    "audio": audio_format
                }
            }
            
        finally:
            if image_clip: image_clip.close()
            if audio_clip: audio_clip.close()
            
            # Clean up temporary files except video
            for file_path in [image_path, audio_path]:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up: {file_path}")
                except Exception as e:
                    logger.error(f"Error cleaning up {file_path}: {str(e)}")

    except Exception as e:
        # Clean up on error
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

@app.get("/supported-formats")
async def get_supported_formats():
    return {
        "image_formats": SUPPORTED_IMAGE_FORMATS,
        "audio_formats": SUPPORTED_AUDIO_FORMATS
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)