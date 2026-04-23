"""
添加 SimSun 150字号模板到数据库
运行: python add_simsun_template.py
"""
import sqlite3
import json
import uuid

# ==================== 模板配置 ====================
TEMPLATE_NAME = "宋体大字模板"
TEMPLATE_DESC = "SimSun字体，150字号，纯白描边，自动换行"
CATEGORY = "custom"
PREVIEW_IMAGE = "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/img/001.jpg"

# 字幕样式配置
SUBTITLE_CONFIG = {
    "subtitleStyles": {
        "body": {
            "font": "SimSun",
            "font_size": 100,
            "font_color": "#FFFFFF",
            "outline": 15,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "x": 0.5,
            "y": -200,
            "alignment": "Center",
            "adapt_mode": "AutoWrap",
            "size_request_type": "RealDim"
        },
        "emphasis": {
            "font": "SimSun",
            "font_size": 100,
            "font_color": "#FFFFFF",
            "outline": 15,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "x": 0.5,
            "y": -200,
            "alignment": "Center",
            "adapt_mode": "AutoWrap",
            "size_request_type": "RealDim",
            "effect_color_style": "red_grad"
        },
        "data": {
            "font": "SimSun",
            "font_size": 100,
            "font_color": "#FFFFFF",
            "outline": 15,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "x": 0.5,
            "y": -200,
            "alignment": "Center",
            "adapt_mode": "AutoWrap",
            "size_request_type": "RealDim",
            "effect_color_style": "golden"
        }
    },
    "videoEffects": {
        "enableSmartZoom": False,
        "zoomIntensity": 1.0
    },
    "backgroundMusic": {
        "url": "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/bgm/the_mountain-festive-festive-music-508015.mp3",
        "volume": 0.4
    },
    "soundEffects": [
        {
            "name": "wow",
            "url": "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/dragon-studio-wow-423653.mp3",
            "trigger": "emphasis"
        },
        {
            "name": "bell",
            "url": "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/u_7xr5ffk4oq-opening-bell-421471.mp3",
            "trigger": "title"
        }
    ]
}
# =================================================

def add_template():
    conn = sqlite3.connect('instance/mixcut_refactored.db')
    c = conn.cursor()
    
    # 检查是否已存在同名模板
    c.execute('SELECT id FROM templates WHERE name = ?', (TEMPLATE_NAME,))
    existing = c.fetchone()
    if existing:
        print(f"模板 '{TEMPLATE_NAME}' 已存在，ID: {existing[0]}")
        print("如需更新，请使用 update_template.py")
        conn.close()
        return
    
    # 获取当前最大sort_order
    c.execute('SELECT MAX(sort_order) FROM templates')
    max_order = c.fetchone()[0] or 0
    
    # 插入新模板
    new_template = (
        str(uuid.uuid4()),
        TEMPLATE_NAME,
        TEMPLATE_DESC,
        CATEGORY,
        PREVIEW_IMAGE,
        json.dumps(SUBTITLE_CONFIG),
        1,  # is_active
        max_order + 1  # sort_order
    )
    
    c.execute('''
        INSERT INTO templates 
        (id, name, description, category, preview_url, config, is_active, sort_order, created_at, updated_at) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    ''', new_template)
    
    conn.commit()
    
    # 验证
    c.execute('SELECT id, name, config FROM templates WHERE name = ?', (TEMPLATE_NAME,))
    row = c.fetchone()
    print(f"模板添加成功!")
    print(f"  ID: {row[0]}")
    print(f"  名称: {row[1]}")
    
    # 解析配置显示关键信息
    config = json.loads(row[2])
    subtitle_styles = config.get('subtitleStyles', {})
    body_style = subtitle_styles.get('body', {})
    print(f"  字体: {body_style.get('font', 'N/A')}")
    print(f"  字号: {body_style.get('font_size', 'N/A')}")
    print(f"  颜色: {body_style.get('font_color', 'N/A')}")
    
    # 显示所有模板
    print("\n当前所有模板:")
    c.execute('SELECT name, sort_order FROM templates ORDER BY sort_order')
    for i, (name, order) in enumerate(c.fetchall(), 1):
        print(f"  {i}. {name} (排序: {order})")
    
    conn.close()

if __name__ == '__main__':
    add_template()
