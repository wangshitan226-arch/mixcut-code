"""
Configuration settings for MixCut Backend
"""
import os

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Upload folders
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
UNIFIED_FOLDER = os.path.join(BASE_DIR, 'unified')
RENDERS_FOLDER = os.path.join(BASE_DIR, 'renders')

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}

# Database
SQLALCHEMY_DATABASE_URI = 'sqlite:///mixcut_refactored.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Video quality settings
QUALITY_SETTINGS = {
    'low': {'scale': '720:1280', 'crf': '23', 'preset': 'ultrafast'},
    'medium': {'scale': '1080:1920', 'crf': '23', 'preset': 'superfast'},
    'high': {'scale': '1440:2560', 'crf': '22', 'preset': 'veryfast'},
    'ultra': {'scale': '2160:3840', 'crf': '20', 'preset': 'faster'}
}

# Cleanup settings
RENDER_MAX_AGE_HOURS = 24

# ==================== OSS配置 ====================
OSS_CONFIG = {
    # 阿里云OSS配置
    # 建议使用环境变量，但这里直接配置以便快速启动
    'access_key_id': os.environ.get('OSS_ACCESS_KEY_ID', ''),
    'access_key_secret': os.environ.get('OSS_ACCESS_KEY_SECRET', ''),
    'endpoint': 'oss-cn-beijing.aliyuncs.com',  # 华北2(北京)
    'bucket_name': 'fengma-materials',
    'cdn_domain': '',  # 可选，如配置了CDN加速域名
}

# 是否启用OSS
OSS_ENABLED = bool(OSS_CONFIG['access_key_id'] and OSS_CONFIG['access_key_secret'])


def ensure_directories():
    """Ensure all required directories exist"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
    os.makedirs(UNIFIED_FOLDER, exist_ok=True)
    os.makedirs(RENDERS_FOLDER, exist_ok=True)
