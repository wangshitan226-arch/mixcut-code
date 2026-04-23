"""
字幕样式配置

定义所有可用的字幕样式参数
"""

# 基础样式定义 - 支持模板扩展
# 默认字体大小150，可通过模板配置覆盖

SUBTITLE_STYLES = {
    'title': {
        'font': 'SimSun',
        'font_size': 150,  # 默认150，可通过模板覆盖
        'font_color': '#FFFFFF',
        'outline': 40,
        'outline_color': '#000000',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'x': 0,
        'y': 500,
        'alignment': 'TopLeft',
        'adapt_mode': 'AutoWrap',
        'size_request_type': 'RealDim'
    },
    'subtitle': {
        'font': 'SimSun',
        'font_size': 150,
        'font_color': '#FFFFFF',
        'outline': 40,
        'outline_color': '#000000',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'x': 0,
        'y': 500,
        'alignment': 'TopLeft',
        'adapt_mode': 'AutoWrap',
        'size_request_type': 'RealDim'
    },
    'body': {
        'font': 'SimSun',
        'font_size': 150,
        'font_color': '#FFFFFF',
        'outline': 40,
        'outline_color': '#000000',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'x': 0,
        'y': 500,
        'alignment': 'TopLeft',
        'adapt_mode': 'AutoWrap',
        'size_request_type': 'RealDim'
    },
    'emphasis': {
        'font': 'SimSun',
        'font_size': 150,
        'font_color': '#FFFFFF',
        'outline': 40,
        'outline_color': '#000000',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'x': 0,
        'y': 500,
        'alignment': 'TopLeft',
        'adapt_mode': 'AutoWrap',
        'size_request_type': 'RealDim',
        'effect_color_style': 'red_grad'  # 强调样式使用花字
    },
    'data': {
        'font': 'SimSun',
        'font_size': 150,
        'font_color': '#FFFFFF',
        'outline': 40,
        'outline_color': '#000000',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'x': 0,
        'y': 500,
        'alignment': 'TopLeft',
        'adapt_mode': 'AutoWrap',
        'size_request_type': 'RealDim',
        'effect_color_style': 'golden'  # 数据样式使用金色花字
    },
    'question': {
        'font': 'SimSun',
        'font_size': 150,
        'font_color': '#FFFFFF',
        'outline': 40,
        'outline_color': '#000000',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'x': 0,
        'y': 500,
        'alignment': 'TopLeft',
        'adapt_mode': 'AutoWrap',
        'size_request_type': 'RealDim'
    },
    'quote': {
        'font': 'SimSun',
        'font_size': 150,
        'font_color': '#FFFFFF',
        'outline': 40,
        'outline_color': '#000000',
        'motion_in': 'fade_in',
        'motion_out': 'fade_out',
        'x': 0,
        'y': 500,
        'alignment': 'TopLeft',
        'adapt_mode': 'AutoWrap',
        'size_request_type': 'RealDim'
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
