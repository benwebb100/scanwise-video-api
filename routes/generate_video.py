from fastapi import HTTPException, Form, APIRouter
import os
import time
import gc
import config
from utils.logging_setup import logger
from utils.file_handler import download_file, check_file_size, clean_temp_files
from services.google_drive import upload_to_drive
from services.video import create_video, concat_videos


router = APIRouter()

@router.post("/generate-video")
async def generate_video(
    image_url: str = Form(...),
    audio_url: str = Form(...)
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
        final_duration = create_video(image_path, audio_path, video_path)
        
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


@router.post("/generate-video-with-prefix")
async def generate_video_with_prefix(
    image_url: str = Form(...),
    audio_url: str = Form(...),
    prefix_video_url: str = Form(...)
):
    """Generate video from image and audio URLs with a prefix video"""
    
    timestamp = int(time.time())
    temp_files = []
    
    try:
        # Download prefix video from Google Drive
        logger.info("Downloading prefix video...")
        prefix_video_data, prefix_format = download_file(prefix_video_url, is_audio=False)
        
        # Validate prefix video format
        if prefix_format not in ['mp4', 'mov', 'avi', 'mkv']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported prefix video format: {prefix_format}"
            )
        
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
        prefix_video_path = os.path.join(config.TEMP_DIR, f"temp_prefix_{timestamp}.{prefix_format}")
        image_path = os.path.join(config.TEMP_DIR, f"temp_image_{timestamp}.{image_format}")
        audio_path = os.path.join(config.TEMP_DIR, f"temp_audio_{timestamp}.{audio_format}")
        generated_video_path = os.path.join(config.TEMP_DIR, f"generated_video_{timestamp}.mp4")
        final_video_path = os.path.join(config.TEMP_DIR, f"final_video_{timestamp}.mp4")
        
        temp_files.extend([prefix_video_path, image_path, audio_path, generated_video_path, final_video_path])

        # Save downloaded files
        with open(prefix_video_path, 'wb') as f:
            f.write(prefix_video_data)
            
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        with open(audio_path, 'wb') as f:
            f.write(audio_data)

        # Check file sizes
        check_file_size(prefix_video_path)
        check_file_size(image_path)
        check_file_size(audio_path)

        # Create main video with subtitles
        logger.info("Creating main video...")
        main_duration = create_video(image_path, audio_path, generated_video_path)
        
        # Concatenate prefix video with generated video
        logger.info("Concatenating videos...")
        concat_videos(prefix_video_path, generated_video_path, final_video_path)
        
        # Get total duration
        from moviepy import VideoFileClip
        final_clip = VideoFileClip(final_video_path)
        total_duration = final_clip.duration
        final_clip.close()
        
        # Upload to Google Drive
        logger.info("Uploading final video to Google Drive...")
        drive_links = upload_to_drive(final_video_path)
        
        # Clean up memory
        gc.collect()
        
        return {
            "status": "success",
            "message": "Video with prefix created and uploaded successfully",
            "video_url": drive_links["shareable_link"],
            "download_url": drive_links["download_link"],
            "total_duration": total_duration,
            "main_video_duration": main_duration,
            "detected_formats": {
                "prefix_video": prefix_format,
                "image": image_format,
                "audio": audio_format
            }
        }
            
    except Exception as e:
        logger.error(f"Error in generate_video_with_prefix: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )
    finally:
        # Clean up temporary files
        clean_temp_files(temp_files)