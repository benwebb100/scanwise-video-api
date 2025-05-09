from moviepy import ImageClip, AudioFileClip
from fastapi import HTTPException
from utils.logging_setup import logger

def create_video(image_path: str, audio_path: str, video_path: str, duration: float) -> float:
    """Create video from image and audio files"""
    image_clip = None
    audio_clip = None
    
    try:
        logger.info("Creating video...")
        image_clip = ImageClip(image_path, duration=duration)
        audio_clip = AudioFileClip(audio_path)
        
        final_duration = min(duration, audio_clip.duration)
        image_clip = image_clip.with_duration(final_duration)
        
        final_clip = image_clip.with_audio(audio_clip)
        
        # Write video with improved parameters
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
        
        return final_duration
        
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating video: {str(e)}"
        )
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