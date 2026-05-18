"""
Configuration settings for MixCut Backend
"""
import os
from dotenv import load_dotenv

load_dotenv()

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
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///mixcut_refactored.db')
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
    'access_key_id': os.environ.get('OSS_ACCESS_KEY_ID', ''),
    'access_key_secret': os.environ.get('OSS_ACCESS_KEY_SECRET', ''),
    'endpoint': os.environ.get('OSS_ENDPOINT', 'oss-cn-hangzhou.aliyuncs.com'),
    'bucket_name': os.environ.get('OSS_BUCKET_NAME', 'mixcut'),
    'cdn_domain': os.environ.get('OSS_CDN_DOMAIN', ''),
}

# 是否启用OSS
OSS_ENABLED = bool(OSS_CONFIG['access_key_id'] and OSS_CONFIG['access_key_secret'])

# ==================== 阿里云ICE配置 ====================
ICE_CONFIG = {
    'access_key_id': os.environ.get('ICE_ACCESS_KEY_ID', OSS_CONFIG['access_key_id']),
    'access_key_secret': os.environ.get('ICE_ACCESS_KEY_SECRET', OSS_CONFIG['access_key_secret']),
    'region': os.environ.get('ICE_REGION', 'cn-hangzhou'),
}

# 是否启用ICE模板渲染
ICE_ENABLED = bool(ICE_CONFIG['access_key_id'] and ICE_CONFIG['access_key_secret'])

# ==================== DashScope配置 ====================
DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
DASHSCOPE_BASE_URL = os.environ.get('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/api/v1')

# ==================== VideoRetalk配置 ====================
VIDEORETALK_BASE_URL = os.environ.get('VIDEORETALK_BASE_URL', DASHSCOPE_BASE_URL)
VIDEORETALK_ENABLED = bool(DASHSCOPE_API_KEY)

# ==================== DeepSeek配置 ====================
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/chat/completions')

# ==================== ICE直接裁剪优化配置 ====================
USE_ICE_DIRECT_CROP = os.environ.get('USE_ICE_DIRECT_CROP', 'true').lower() == 'true'

def ensure_directories():
    """Ensure all required directories exist"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
    os.makedirs(UNIFIED_FOLDER, exist_ok=True)
    os.makedirs(RENDERS_FOLDER, exist_ok=True)
