"""
字幕样式配置

定义所有可用的字幕样式参数
"""

# 基础样式定义
SUBTITLE_STYLES = {
    'title': {
        'font': 'AlibabaPuHuiTi-Heavy',
        'font_size': 90,
        'font_color': '#FFD700',
        'outline': 5,
        'outline_color': '#8B4513',
        'motion_in': 'rotateup_in',
        'motion_out': 'close_out',
        'y': 0.35,
        'weight': 1.5
    },
    'subtitle': {
        'font': 'AlibabaPuHuiTi-Regular',
        'font_size': 50,
        'font_color': '#FFFFFF',
        'outline': 3,
        'outline_color': '#333333',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'y': 0.52,
        'weight': 1.2
    },
    'body': {
        'font': 'AlibabaPuHuiTi-Regular',
        'font_size': 42,
        'font_color': '#FFFFFF',
        'outline': 2,
        'outline_color': '#000000',
        'motion_in': 'scroll_right_in',
        'motion_out': 'scroll_right_out',
        'y': 0.72,
        'weight': 1.0
    },
    'emphasis': {
        'font': 'AlibabaPuHuiTi-Bold',
        'font_size': 60,
        'font_color': '#FFDD00',
        'outline': 4,
        'outline_color': '#FF6600',
        'motion_in': 'slingshot_in',
        'motion_out': 'slingshot_out',
        'y': 0.5,
        'weight': 1.0,
        'loop': 2,
        'loop_effect': 'bounce'
    },
    'data': {
        'font': 'AlibabaPuHuiTi-Bold',
        'font_size': 80,
        'font_color': '#00FF88',
        'outline': 4,
        'outline_color': '#00CC66',
        'motion_in': 'close_in',
        'motion_out': 'close_out',
        'y': 0.45,
        'weight': 1.2
    }
}


def get_style(style_name: str) -> dict:
    """获取指定样式配置"""
    return SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES['body'])


def create_custom_style(
    base_style: str = 'body',
    font: str = None,
    font_size: int = None,
    font_color: str = None,
    outline: int = None,
    y: float = None
) -> dict:
    """
    基于基础样式创建自定义样式
    
    Args:
        base_style: 基础样式名称
        font: 字体
        font_size: 字号
        font_color: 字体颜色
        outline: 描边宽度
        y: 垂直位置
    
    Returns:
        自定义样式配置
    """
    style = SUBTITLE_STYLES.get(base_style, SUBTITLE_STYLES['body']).copy()
    
    if font:
        style['font'] = font
    if font_size:
        style['font_size'] = font_size
    if font_color:
        style['font_color'] = font_color
    if outline is not None:
        style['outline'] = outline
    if y is not None:
        style['y'] = y
    
    return style
