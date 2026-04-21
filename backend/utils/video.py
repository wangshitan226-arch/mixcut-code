"""
Video processing utilities
"""
import os
import subprocess
import uuid
from config import RENDERS_FOLDER, ALLOWED_EXTENSIONS


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_quality_settings(quality='medium'):
    """Get video quality settings"""
    settings = {
        'low': {'scale': '720:1280', 'crf': '23', 'preset': 'ultrafast'},
        'medium': {'scale': '1080:1920', 'crf': '23', 'preset': 'superfast'},
        'high': {'scale': '1440:2560', 'crf': '22', 'preset': 'veryfast'},
        'ultra': {'scale': '2160:3840', 'crf': '20', 'preset': 'faster'}
    }
    return settings.get(quality, settings['medium'])


def transcode_to_unified(input_path, output_path, quality='medium'):
    """Transcode video/image to unified format"""
    settings = get_quality_settings(quality)
    ext = input_path.rsplit('.', 1)[1].lower()
    
    if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', input_path,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,fps=30',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p10le',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-t', '3',
            '-movflags', '+faststart',
            output_path
        ]
    else:
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,fps=30',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p10le',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-ac', '2',
            '-movflags', '+faststart',
            output_path
        ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_video_thumbnail(video_path, output_path, time_point='00:00:01'):
    """Generate thumbnail from video"""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-ss', time_point,
        '-vframes', '1',
        '-q:v', '2',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_image_thumbnail(image_path, thumbnail_path):
    """Generate thumbnail for image"""
    from PIL import Image
    with Image.open(image_path) as img:
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.thumbnail((300, 400), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (300, 400), (200, 200, 200))
        x = (300 - img.width) // 2
        y = (400 - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(thumbnail_path, 'JPEG', quality=80)


def get_video_duration(video_path):
    """Get video duration in seconds"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            return float(result.stdout.strip())
        except:
            return 0
    return 0


def format_duration(seconds):
    """Format duration in seconds to MM:SS"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def fast_concat_videos(unified_files, output_path):
    """Fast concat videos using ffmpeg concat demuxer"""
    if not unified_files:
        return False
    
    files_with_audio = []
    for filepath in unified_files:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a',
               '-show_entries', 'stream=codec_type', '-of',
               'default=noprint_wrappers=1:nokey=1', filepath]
        result = subprocess.run(cmd, capture_output=True, text=True)
        has_audio = 'audio' in result.stdout
        files_with_audio.append((filepath, has_audio))
    
    all_have_audio = all(has_audio for _, has_audio in files_with_audio)
    
    list_file = os.path.join(RENDERS_FOLDER, f"list_{uuid.uuid4().hex[:8]}.txt")
    with open(list_file, 'w') as f:
        for filepath, _ in files_with_audio:
            abs_path = os.path.abspath(filepath)
            f.write(f"file '{abs_path}'\n")
    
    try:
        if all_have_audio:
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                '-movflags', '+faststart',
                output_path
            ]
        else:
            processed_files = []
            temp_files = []
            
            try:
                for i, (filepath, has_audio) in enumerate(files_with_audio):
                    if has_audio:
                        processed_files.append(filepath)
                    else:
                        temp_output = os.path.join(RENDERS_FOLDER, f"temp_{uuid.uuid4().hex[:8]}_{i}.mp4")
                        temp_files.append(temp_output)
                        
                        cmd = [
                            'ffmpeg', '-y',
                            '-i', filepath,
                            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                            '-c:v', 'copy',
                            '-c:a', 'aac',
                            '-b:a', '128k',
                            '-ar', '44100',
                            '-ac', '2',
                            '-shortest',
                            '-movflags', '+faststart',
                            temp_output
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            processed_files.append(temp_output)
                        else:
                            processed_files.append(filepath)
                
                with open(list_file, 'w') as f:
                    for filepath in processed_files:
                        abs_path = os.path.abspath(filepath)
                        f.write(f"file '{abs_path}'\n")
                
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', list_file,
                    '-c', 'copy',
                    '-movflags', '+faststart',
                    output_path
                ]
            finally:
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg concat error: {result.stderr}")
        return result.returncode == 0
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)
