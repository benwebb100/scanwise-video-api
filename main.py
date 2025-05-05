from fastapi import FastAPI, HTTPException, Form
import uvicorn
from moviepy import ImageClip, AudioFileClip
import os
import logging
import time
import requests
import mimetypes
from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from dotenv import load_dotenv
import gc

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video Generation API")

# Constants
TEMP_DIR = "video_temp"
MAX_FILE_SIZE_MB = 100
SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp']
SUPPORTED_AUDIO_FORMATS = ['mp3', 'wav', 'aac', 'm4a', 'ogg']

# Create temp directories
os.makedirs(TEMP_DIR, exist_ok=True)

# Google Drive setup from environment variables
SCOPES = ['https://www.googleapis.com/auth/drive.file']

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

def check_file_size(file_path: str, max_size_mb: int = MAX_FILE_SIZE_MB):
    """Check if file size is within limits"""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.2f}MB (max {max_size_mb}MB)"
        )

def get_credentials_dict():
    """Create credentials dictionary from environment variables"""
    required_creds = [
        "TYPE",  # Changed from GOOGLE_TYPE
        "PROJECT_ID",  # Changed from GOOGLE_PROJECT_ID
        "PRIVATE_KEY_ID",  # Changed from GOOGLE_PRIVATE_KEY_ID
        "PRIVATE_KEY",  # Changed from GOOGLE_PRIVATE_KEY
        "CLIENT_EMAIL",  # Changed from GOOGLE_CLIENT_EMAIL
        "CLIENT_ID",  # Changed from GOOGLE_CLIENT_ID
        "AUTH_URI",  # Changed from GOOGLE_AUTH_URI
        "TOKEN_URI",  # Changed from GOOGLE_TOKEN_URI
        "AUTH_PROVIDER_X509_CERT_URL",  # Changed from GOOGLE_AUTH_PROVIDER_X509_CERT_URL
        "CLIENT_X509_CERT_URL"  # Changed from GOOGLE_CLIENT_X509_CERT_URL
    ]
    
    missing = [cred for cred in required_creds if not os.getenv(cred)]
    if missing:
        raise ValueError(f"Missing required credentials: {', '.join(missing)}")

    return {
        "type": os.getenv("TYPE"),
        "project_id": os.getenv("PROJECT_ID"),
        "private_key_id": os.getenv("PRIVATE_KEY_ID"),
        "private_key": os.getenv("PRIVATE_KEY"),
        "client_email": os.getenv("CLIENT_EMAIL"),
        "client_id": os.getenv("CLIENT_ID"),
        "auth_uri": os.getenv("AUTH_URI"),
        "token_uri": os.getenv("TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL")
    }

def get_google_drive_service():
    """Get Google Drive service using credentials from environment variables"""
    try:
        credentials_dict = get_credentials_dict()
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES
        )
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Error setting up Google Drive service: {str(e)}")
        raise

def upload_to_drive(file_path: str, mime_type: str = 'video/mp4') -> dict:
    """Upload file to Google Drive and return both shareable and download links"""
    try:
        service = get_google_drive_service()
        
        file_metadata = {
            'name': os.path.basename(file_path),
            'mimeType': mime_type
        }
        
        media = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True
        )
        
        logger.info("Uploading file to Google Drive...")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(
            fileId=file.get('id'),
            body=permission
        ).execute()
        
        file_id = file.get('id')
        return {
            "shareable_link": f"https://drive.google.com/file/d/{file_id}/view",
            "download_link": f"https://drive.google.com/uc?id={file_id}&export=download"
        }
    
    except Exception as e:
        logger.error(f"Error uploading to Google Drive: {str(e)}")
        raise

def detect_format(content_type: str, url: str, is_audio: bool = False) -> str:
    """Detect format from content type or URL"""
    format_ext = MIME_TO_FORMAT.get(content_type.lower())
    
    if not format_ext:
        ext = url.split('.')[-1].lower()
        if ext in SUPPORTED_IMAGE_FORMATS or ext in SUPPORTED_AUDIO_FORMATS:
            format_ext = ext
        else:
            format_ext = 'mp3' if is_audio else 'jpg'
    
    return format_ext

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

@app.post("/generate-video")
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
        image_path = os.path.join(TEMP_DIR, f"temp_image_{timestamp}.{image_format}")
        audio_path = os.path.join(TEMP_DIR, f"temp_audio_{timestamp}.{audio_format}")
        video_path = os.path.join(TEMP_DIR, f"output_video_{timestamp}.mp4")
        
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

        # Create video using moviepy
        image_clip = None
        audio_clip = None
        drive_links = None
        
        try:
            logger.info("Creating video...")
            image_clip = ImageClip(image_path, duration=duration)
            audio_clip = AudioFileClip(audio_path)
            
            final_duration = min(duration, audio_clip.duration)
            image_clip = image_clip.with_duration(final_duration)
            
            final_clip = image_clip.with_audio(audio_clip)
            
            # Write video with improved parameters
            try:
                logger.info("Writing video file...")
                final_clip.write_videofile(
                    video_path,
                    fps=24,
                    codec='libx264',
                    audio_codec='aac',
                    threads=4,
                    preset='ultrafast',
                    ffmpeg_params=['-strict', '-2', '-bufsize', '2000k'],
                    logger=None
                )
            except Exception as video_error:
                logger.error(f"Error writing video: {str(video_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error writing video: {str(video_error)}"
                )
            
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
            
        finally:
            if image_clip: 
                try:
                    image_clip.close()
                except:
                    pass
            if audio_clip: 
                try:
                    audio_clip.close()
                except:
                    pass
            
            # Clean up temporary files
            for file_path in temp_files:
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
    port = int(os.getenv('API_PORT', 8000))
    host = os.getenv('API_HOST', '0.0.0.0')
    uvicorn.run(app, host=host, port=port)