from fastapi import FastAPI
import uvicorn
import os

from routes.generate_video import router as generate_video_router
from routes.base64 import router as hex_to_base64_router
from routes.generate_avatar_video import router as generate_avatar_video_router

# Initialize FastAPI app
app = FastAPI(
    title="Video Generation API",
    description="API for generating videos from images and audio files",
    version="1.0.0"
)

# Import routes
app.include_router(generate_video_router)
app.include_router(hex_to_base64_router)
app.include_router(generate_avatar_video_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Video Generation API!"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/version")
def get_version():
    return {"version": "1.0.0"}

# Main entry point
# to run the FastAPI app
if __name__ == "__main__":
    port = int(os.getenv('API_PORT', 8000))
    host = os.getenv('API_HOST', '0.0.0.0')
    uvicorn.run(app, host=host, port=port)