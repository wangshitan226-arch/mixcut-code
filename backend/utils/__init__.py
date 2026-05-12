"""
Utility functions for MixCut backend
"""
from .validators import validate_username, validate_password, validate_email, validate_phone
from .video import (
    allowed_file, get_quality_settings, transcode_to_unified,
    generate_image_thumbnail, generate_video_thumbnail,
    get_video_duration, format_duration, fast_concat_videos
)
from .helpers import cleanup_renders_with_material, clear_user_renders, calculate_uniqueness_tag
from .cleanup import clear_all_user_renders, clear_user_render_files, clear_user_renders_db
from .oss import oss_client
from .kaipai_asr import create_asr_task, get_asr_task, process_asr_task

__all__ = [
    'validate_username', 'validate_password', 'validate_email', 'validate_phone',
    'allowed_file', 'get_quality_settings', 'transcode_to_unified',
    'generate_image_thumbnail', 'generate_video_thumbnail',
    'get_video_duration', 'format_duration', 'fast_concat_videos',
    'cleanup_renders_with_material', 'clear_user_renders', 'calculate_uniqueness_tag',
    'clear_all_user_renders', 'clear_user_render_files', 'clear_user_renders_db',
    'oss_client',
    'create_asr_task', 'get_asr_task', 'process_asr_task'
]
