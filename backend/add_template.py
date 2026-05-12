"""
添加新模板到数据库
修改下面的参数后运行: python add_template.py
"""
import sqlite3
import json
import uuid

# ==================== 修改这里 ====================
TEMPLATE_NAME = "明快黄"
TEMPLATE_DESC = "亮金黄主题，多层次字幕布局，适合自媒体干货分享"
CATEGORY = "custom"
PREVIEW_IMAGE = "/templates/0.jpg"

# 字幕样式配置 - 根据你的详细描述配置
SUBTITLE_CONFIG = {
    "subtitleStyles": {
        # 1. 标题1：自媒体成功秘籍 - 一级超大号，顶部
        "title": {
            "font": "AlibabaPuHuiTi-Heavy",
            "font_size": 95,
            "font_color": "#FFD300",
            "outline": 6,
            "outline_color": "#996B00",
            "motion_in": "rotateup_in",
            "motion_out": "close_out",
            "y": 0.08,  # 顶部 3%-12% 区间，取中间
            "weight": 1.5
        },
        # 2. 标题2：坚持就是胜利 - 二级大号，紧贴标题1下方
        "subtitle": {
            "font": "AlibabaPuHuiTi-Heavy",
            "font_size": 75,
            "font_color": "#FFFFFF",
            "outline": 5,
            "outline_color": "#5C3A21",
            "motion_in": "slingshot_in",
            "motion_out": "slingshot_out",
            "y": 0.18,  # 13%-22% 区间
            "weight": 1.3
        },
        # 3. 中文短句：我做自媒体的 - 三级中号，左侧
        "section": {
            "font": "AlibabaPuHuiTi-Bold",
            "font_size": 48,
            "font_color": "#FFFFFF",
            "outline": 3,
            "outline_color": "#333333",
            "motion_in": "scroll_right_in",
            "motion_out": "scroll_right_out",
            "y": 0.74,  # 70%-78% 区间
            "weight": 1.0
        },
        # 4. 小英文：I work in self media - 四级小号，中文下方
        "body": {
            "font": "AlibabaPuHuiTi-Regular",
            "font_size": 28,
            "font_color": "#F5F5F5",
            "outline": 0,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "y": 0.80,  # 中文短句正下方
            "weight": 0.8
        },
        # 5. 点睛短句：三字真言 - 三级中号，右下角
        "emphasis": {
            "font": "AlibabaPuHuiTi-Heavy",
            "font_size": 52,
            "font_color": "#FFD300",
            "outline": 4,
            "outline_color": "#8C5F00",
            "motion_in": "wave_in",
            "motion_out": "wave_out",
            "y": 0.88,  # 83%-92% 区间
            "weight": 1.2,
            "loop": 2,
            "loop_effect": "bounce"
        },
        # 6. 数据高亮样式 - 用于关键词"自媒体"高亮
        "data": {
            "font": "AlibabaPuHuiTi-Bold",
            "font_size": 50,
            "font_color": "#FFD300",
            "outline": 3,
            "outline_color": "#996B00",
            "motion_in": "close_in",
            "motion_out": "close_out",
            "y": 0.74,
            "weight": 1.0
        }
    },
    "videoEffects": {
        "enableSmartZoom": True,
        "zoomIntensity": 1.15
    },
    "backgroundMusic": {
        "url": "/templates/bgm/the_mountain-festive-festive-music-508015.mp3",
        "volume": 0.4
    },
    "soundEffects": [
        {
            "name": "wow",
            "url": "/templates/sound_effact/dragon-studio-wow-423653.mp3",
            "trigger": "emphasis"  # 在强调文字出现时触发
        },
        {
            "name": "bell",
            "url": "/templates/sound_effact/u_7xr5ffk4oq-opening-bell-421471.mp3",
            "trigger": "title"  # 在标题出现时触发
        }
    ]
}
# =================================================

def add_template():
    conn = sqlite3.connect('instance/mixcut_refactored.db')
    c = conn.cursor()
    
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
    c.execute('SELECT id, name, preview_url FROM templates WHERE name = ?', (TEMPLATE_NAME,))
    row = c.fetchone()
    print(f"模板添加成功!")
    print(f"  ID: {row[0]}")
    print(f"  名称: {row[1]}")
    print(f"  预览图: {row[2]}")
    
    # 显示所有模板
    print("\n当前所有模板:")
    c.execute('SELECT name FROM templates ORDER BY sort_order')
    for i, (name,) in enumerate(c.fetchall(), 1):
        print(f"  {i}. {name}")
    
    conn.close()

if __name__ == '__main__':
    add_template()
