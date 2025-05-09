from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
from utils.logging_setup import logger
import requests
import base64

# Initialize FastAPI router
router = APIRouter()


class DriveURLRequest(BaseModel):
    drive_url: str

@router.post("/convert-to-base64")
def convert_to_base64(request: DriveURLRequest):
    logger.info(f"Received request to convert URL to base64: {request.drive_url[:50]}...")
    
    try:
        logger.debug("Attempting to download image from URL")
        response = requests.get(request.drive_url)
        
        if response.status_code != 200:
            logger.error(f"Failed to download image - Status code: {response.status_code}")
            raise HTTPException(status_code=400, detail="Failed to download image from the provided URL.")

        image_bytes = response.content
        logger.debug(f"Successfully downloaded image - Size: {len(image_bytes)} bytes")
        
        base64_str = base64.b64encode(image_bytes).decode('utf-8')
        logger.info(f"Successfully converted image to base64 - Size: {len(base64_str)} characters")

        return {"base64": base64_str}

    except HTTPException:
        # Let FastAPI handle HTTPExceptions directly
        raise
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading image: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during base64 conversion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")