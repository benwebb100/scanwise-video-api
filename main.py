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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video Generation API")

# Ensure temp directory exists
os.makedirs("temp", exist_ok=True)

SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp']
SUPPORTED_AUDIO_FORMATS = ['mp3', 'wav', 'aac', 'm4a', 'ogg']

# Google Drive setup
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'service_account.json'

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

def get_credentials_dict():
    """Create credentials dictionary from environment variables"""
    return {
        "type": os.getenv("GOOGLE_TYPE"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY"),
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL")
    }

def get_google_drive_service():
    """Get Google Drive service using service account"""
    try:

        credentials_dict = get_credentials_dict()
        
        # Validate required credentials
        required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email"]
        missing_fields = [field for field in required_fields if not credentials_dict.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing required credentials: {', '.join(missing_fields)}")
        
        # credentials = service_account.Credentials.from_service_account_file(
        #     SERVICE_ACCOUNT_FILE, scopes=SCOPES)

        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES
        )
        
        service = build('drive', 'v3', credentials=credentials)
        return service
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
        drive_links = None
        
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
            
            # Upload to Google Drive
            logger.info("Uploading video to Google Drive...")
            drive_links = upload_to_drive(video_path)
            
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
            if image_clip: image_clip.close()
            if audio_clip: audio_clip.close()
            
            # Clean up all temporary files
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
    uvicorn.run(app, host="0.0.0.0", port=8000)