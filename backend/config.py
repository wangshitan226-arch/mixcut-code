"""Application configuration"""
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Upload folders
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
UNIFIED_FOLDER = os.path.join(UPLOAD_FOLDER, 'unified')
RENDERS_FOLDER = os.path.join(BASE_DIR, 'renders')

# Database
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "mixcut.db")}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# File limits
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB

# Allowed file extensions
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'webm', 'mkv'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
ALLOWED_EXTENSIONS = ALLOWED_VIDEO_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS

# Quality settings for transcoding
QUALITY_SETTINGS = {
    'low': {'scale': '720:1280', 'crf': '23', 'preset': 'ultrafast', 'label': '流畅', 'desc': '720P'},
    'medium': {'scale': '1080:1920', 'crf': '23', 'preset': 'superfast', 'label': '高清', 'desc': '1080P'},
    'high': {'scale': '1440:2560', 'crf': '22', 'preset': 'veryfast', 'label': '超清', 'desc': '2K'},
    'ultra': {'scale': '2160:3840', 'crf': '20', 'preset': 'faster', 'label': '原画', 'desc': '4K'}
}

# CORS settings
CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# Cleanup settings
RENDER_CLEANUP_MAX_AGE_HOURS = 24
