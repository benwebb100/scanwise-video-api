import os
import requests
from fastapi import HTTPException
from utils.logging_setup import logger
from config import MIME_TO_FORMAT, SUPPORTED_IMAGE_FORMATS, SUPPORTED_AUDIO_FORMATS, MAX_FILE_SIZE_MB

def check_file_size(file_path: str, max_size_mb: int = MAX_FILE_SIZE_MB):
    """Check if file size is within limits"""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.2f}MB (max {max_size_mb}MB)"
        )

# def detect_format(content_type: str, url: str, is_audio: bool = False) -> str:
#     """Detect format from content type or URL"""
#     format_ext = MIME_TO_FORMAT.get(content_type.lower())
    
#     if not format_ext:
#         ext = url.split('.')[-1].lower()
#         if ext in SUPPORTED_IMAGE_FORMATS or ext in SUPPORTED_AUDIO_FORMATS:
#             format_ext = ext
#         else:
#             format_ext = 'mp3' if is_audio else 'jpg'
    
#     return format_ext

def detect_format(content_type: str, url: str, is_audio: bool = False) -> str:
    """Detect file format from content-type or URL"""
    
    # First, try to detect from content-type
    content_type = content_type.lower()
    
    # Video formats
    if 'video/mp4' in content_type:
        return 'mp4'
    elif 'video/quicktime' in content_type:
        return 'mov'
    elif 'video/x-msvideo' in content_type:
        return 'avi'
    elif 'video/x-matroska' in content_type:
        return 'mkv'
    
    # Image formats
    elif 'image/jpeg' in content_type or 'image/jpg' in content_type:
        return 'jpg'
    elif 'image/png' in content_type:
        return 'png'
    elif 'image/gif' in content_type:
        return 'gif'
    elif 'image/webp' in content_type:
        return 'webp'
    
    # Audio formats
    elif 'audio/mpeg' in content_type or 'audio/mp3' in content_type:
        return 'mp3'
    elif 'audio/wav' in content_type or 'audio/x-wav' in content_type:
        return 'wav'
    elif 'audio/mp4' in content_type or 'audio/m4a' in content_type:
        return 'm4a'
    elif 'audio/aac' in content_type:
        return 'aac'
    
    # If content-type detection fails, try URL extension
    if '.' in url:
        ext = url.split('.')[-1].split('?')[0].lower()
        if ext in ['mp4', 'mov', 'avi', 'mkv', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp3', 'wav', 'm4a', 'aac']:
            return ext
    
    # Default fallback based on context
    if is_audio:
        return 'mp3'  # Default audio format
    else:
        return 'jpg'  # Default image format

def download_file(url: str, is_audio: bool = False) -> tuple[bytes, str]:
    """Download file from URL and detect its format"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '')
        format_ext = detect_format(content_type, url, is_audio)
        
        logger.info(f"Detected format: {format_ext} from content-type: {content_type}")
        return response.content, format_ext
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading file from {url}: {str(e)}"
        )

def clean_temp_files(file_paths: list[str]):
    """Delete temporary files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up {file_path}: {str(e)}")