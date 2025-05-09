from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import base64
import uvicorn
import os

app = FastAPI()

class DriveURLRequest(BaseModel):
    drive_url: str

@app.post("/convert-to-base64")
def convert_to_base64(request: DriveURLRequest):
    try:
        response = requests.get(request.drive_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download image from the provided URL.")

        image_bytes = response.content
        base64_str = base64.b64encode(image_bytes).decode('utf-8')

        return {"base64": base64_str}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


if __name__ == "__main__":
    port = int(os.getenv('API_PORT', 8000))
    host = os.getenv('API_HOST', '0.0.0.0')
    uvicorn.run(app, host=host, port=port)