"""
系统模板配置

定义所有系统预设模板
要添加新模板，在此文件的 TEMPLATES 列表中添加即可
"""

from typing import List, Dict, Optional
from .styles import SUBTITLE_STYLES

# ============================================
# 系统模板配置
# ============================================

TEMPLATES: List[Dict] = [
    {
        'id': 'template_001',
        'name': '大字报风格',
        'description': '金色大字标题，适合促销和强调',
        'category': 'promotion',
        'preview_image': '/templates/preview_001.jpg',  # 预览图路径
        'config': {
            'subtitleStyles': {
                'title': SUBTITLE_STYLES['title'],
                'body': SUBTITLE_STYLES['body'],
                'emphasis': SUBTITLE_STYLES['emphasis'],
                'data': SUBTITLE_STYLES['data']
            },
            'videoEffects': {
                'enableSmartZoom': True,
                'zoomIntensity': 1.2
            }
        }
    },
    {
        'id': 'template_002',
        'name': '简洁知识风',
        'description': '清晰易读，适合知识分享',
        'category': 'knowledge',
        'preview_image': '/templates/preview_002.jpg',
        'config': {
            'subtitleStyles': {
                'title': SUBTITLE_STYLES['subtitle'],
                'body': SUBTITLE_STYLES['body']
            },
            'videoEffects': {
                'enableSmartZoom': False
            }
        }
    },
    {
        'id': 'template_003',
        'name': '活力动感风',
        'description': '弹跳动画，适合娱乐内容',
        'category': 'entertainment',
        'preview_image': '/templates/preview_003.jpg',
        'config': {
            'subtitleStyles': {
                'title': SUBTITLE_STYLES['emphasis'],
                'body': SUBTITLE_STYLES['body']
            },
            'videoEffects': {
                'enableSmartZoom': True,
                'zoomIntensity': 1.25
            }
        }
    }
]


def get_template_by_id(template_id: str) -> Optional[Dict]:
    """
    根据ID获取模板配置
    
    Args:
        template_id: 模板ID
    
    Returns:
        模板配置字典，未找到返回None
    """
    for template in TEMPLATES:
        if template['id'] == template_id:
            return template
    return None


def get_templates_by_category(category: str) -> List[Dict]:
    """
    根据分类获取模板列表
    
    Args:
        category: 分类名称
    
    Returns:
        模板列表
    """
    return [t for t in TEMPLATES if t['category'] == category]


def get_all_template_ids() -> List[str]:
    """获取所有模板ID列表"""
    return [t['id'] for t in TEMPLATES]


# ============================================
# 模板初始化相关
# ============================================

def get_default_templates() -> List[Dict]:
    """
    获取默认模板列表（用于数据库初始化）
    返回不包含id的模板配置，让数据库自动生成id
    """
    return [
        {
            'name': t['name'],
            'description': t['description'],
            'category': t['category'],
            'preview_image': t.get('preview_image', ''),
            'config': t['config']
        }
        for t in TEMPLATES
    ]
