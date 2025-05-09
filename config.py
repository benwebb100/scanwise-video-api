import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Application configuration
TEMP_DIR = "video_temp"
MAX_FILE_SIZE_MB = 100
SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp']
SUPPORTED_AUDIO_FORMATS = ['mp3', 'wav', 'aac', 'm4a', 'ogg']
GOOGLE_DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
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

# Create temp directories
os.makedirs(TEMP_DIR, exist_ok=True)