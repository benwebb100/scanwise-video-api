from fastapi import HTTPException, Form, APIRouter
import os
import time
import gc
from typing import Optional
import config
from utils.logging_setup import logger
from utils.file_handler import download_file, check_file_size, clean_temp_files
from services.google_drive import upload_to_drive
from services.video import create_video


router = APIRouter()

@router.post("/generate-video")
async def generate_video(
    image_url: str = Form(...),
    audio_url: str = Form(...),
    duration: Optional[float] = Form(5.0)
):
    """Generate video from image and audio URLs"""
    
    timestamp = int(time.time())
    temp_files = []
    
    try:
        # Download files and detect formats
        logger.info("Downloading image...")
        image_data, image_format = download_file(image_url, is_audio=False)
        
        logger.info("Downloading audio...")
        audio_data, audio_format = download_file(audio_url, is_audio=True)
        
        # Validate formats
        if image_format not in config.SUPPORTED_IMAGE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image format: {image_format}"
            )
        
        if audio_format not in config.SUPPORTED_AUDIO_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {audio_format}"
            )

        # Create temporary file paths
        image_path = os.path.join(config.TEMP_DIR, f"temp_image_{timestamp}.{image_format}")
        audio_path = os.path.join(config.TEMP_DIR, f"temp_audio_{timestamp}.{audio_format}")
        video_path = os.path.join(config.TEMP_DIR, f"output_video_{timestamp}.mp4")
        
        temp_files.extend([image_path, audio_path, video_path])

        # Save downloaded files
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        with open(audio_path, 'wb') as f:
            f.write(audio_data)

        # Check file sizes
        check_file_size(image_path)
        check_file_size(audio_path)

        # Verify files exist
        if not os.path.exists(image_path) or not os.path.exists(audio_path):
            raise HTTPException(
                status_code=500,
                detail="Failed to save temporary files"
            )

        # Create video
        final_duration = create_video(image_path, audio_path, video_path, duration)
        
        # Upload to Google Drive
        logger.info("Uploading video to Google Drive...")
        drive_links = upload_to_drive(video_path)
        
        # Clean up memory
        gc.collect()
        
        return {
            "status": "success",
            "message": "Video created and uploaded successfully",
            "video_url": drive_links["shareable_link"],
            "download_url": drive_links["download_link"],
            "duration": final_duration,
            "detected_formats": {
                "image": image_format,
                "audio": audio_format
            }
        }
            
    except Exception as e:
        logger.error(f"Error in generate_video: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )
    finally:
        # Clean up temporary files
        clean_temp_files(temp_files)


@router.get("/supported-formats")
async def get_supported_formats():
    """Get supported image and audio formats"""
    return {
        "image_formats": config.SUPPORTED_IMAGE_FORMATS,
        "audio_formats": config.SUPPORTED_AUDIO_FORMATS
    }
