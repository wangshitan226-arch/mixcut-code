"""Video processing utilities"""
import os
import subprocess
import cv2
from PIL import Image
from config import QUALITY_SETTINGS

def get_quality_settings(quality):
    """Get quality settings for transcoding"""
    return QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS['medium'])

def transcode_to_unified(input_path, output_path, quality='medium'):
    """Transcode video/image to unified format"""
    settings = get_quality_settings(quality)
    ext = input_path.rsplit('.', 1)[1].lower()
    
    if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
        # For images: create 3-second video
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', input_path,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30',
            '-c:v', 'libx264',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-t', '3',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_path
        ]
    else:
        # For videos: transcode to unified format
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30',
            '-c:v', 'libx264',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-ac', '2',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_path
        ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def generate_image_thumbnail(image_path, thumbnail_path):
    """Generate thumbnail for image"""
    with Image.open(image_path) as img:
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.thumbnail((300, 400), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (300, 400), (200, 200, 200))
        x = (300 - img.width) // 2
        y = (400 - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(thumbnail_path, 'JPEG', quality=80)

def generate_video_thumbnail(video_path, thumbnail_path):
    """Generate thumbnail for video (first frame)"""
    cap = cv2.VideoCapture(video_path)
    success, frame = cap.read()
    if success:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        img.thumbnail((300, 400), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (300, 400), (200, 200, 200))
        x = (300 - img.width) // 2
        y = (400 - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(thumbnail_path, 'JPEG', quality=80)
    cap.release()
    return success

def get_video_duration(video_path):
    """Get video duration in seconds"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps > 0:
        return frame_count / fps
    return 0

def format_duration(seconds):
    """Format duration as MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"
