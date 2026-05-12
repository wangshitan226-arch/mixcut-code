"""
模板管理系统

使用方式:
    from templates import get_templates, get_template_config
    
    # 获取所有模板
    templates = get_templates()
    
    # 获取单个模板配置
    config = get_template_config('template_id')
"""

from .config import TEMPLATES, get_template_by_id
from .styles import SUBTITLE_STYLES

__all__ = ['TEMPLATES', 'get_template_by_id', 'SUBTITLE_STYLES']
