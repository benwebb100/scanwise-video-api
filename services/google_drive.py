import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from utils.logging_setup import logger
from config import GOOGLE_DRIVE_SCOPES

def get_credentials_dict():
    """Create credentials dictionary from environment variables"""
    required_creds = [
        "TYPE", "PROJECT_ID", "PRIVATE_KEY_ID", "PRIVATE_KEY",
        "CLIENT_EMAIL", "CLIENT_ID", "AUTH_URI", "TOKEN_URI",
        "AUTH_PROVIDER_X509_CERT_URL", "CLIENT_X509_CERT_URL"
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

def get_drive_service():
    """Get Google Drive service using credentials from environment variables"""
    try:
        credentials_dict = get_credentials_dict()
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=GOOGLE_DRIVE_SCOPES
        )
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Error setting up Google Drive service: {str(e)}")
        raise

def upload_to_drive(file_path: str, mime_type: str = 'video/mp4') -> dict:
    """Upload file to Google Drive and return both shareable and download links"""
    try:
        service = get_drive_service()
        
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