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
    # 从环境变量读取敏感信息
    'access_key_id': os.environ.get('OSS_ACCESS_KEY_ID', ''),
    'access_key_secret': os.environ.get('OSS_ACCESS_KEY_SECRET', ''),
    'endpoint': 'oss-cn-beijing.aliyuncs.com',  # 华北2(北京)
    'bucket_name': 'fengma-materials',
    'cdn_domain': '',  # 可选，如配置了CDN加速域名
}

# 是否启用OSS
OSS_ENABLED = bool(OSS_CONFIG['access_key_id'] and OSS_CONFIG['access_key_secret'])

# ==================== 阿里云ICE配置 ====================
ICE_CONFIG = {
    # 阿里云ICE（智能媒体服务）配置
    # 用于模板渲染
    'access_key_id': os.environ.get('ICE_ACCESS_KEY_ID', OSS_CONFIG['access_key_id']),
    'access_key_secret': os.environ.get('ICE_ACCESS_KEY_SECRET', OSS_CONFIG['access_key_secret']),
    'region': 'cn-beijing',  # 服务所在地域
}

# 是否启用ICE模板渲染
ICE_ENABLED = bool(ICE_CONFIG['access_key_id'] and ICE_CONFIG['access_key_secret'])

# ==================== ICE直接裁剪优化配置 ====================
# 是否使用ICE直接裁剪模式（跳过本地FFmpeg处理）
# True:  使用ICE的In/Out参数直接裁剪，省去下载、FFmpeg处理、上传环节（推荐）
# False: 使用本地FFmpeg裁剪后上传中间视频到ICE（兼容模式）
USE_ICE_DIRECT_CROP = True


def ensure_directories():
    """Ensure all required directories exist"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
    os.makedirs(UNIFIED_FOLDER, exist_ok=True)
    os.makedirs(RENDERS_FOLDER, exist_ok=True)
