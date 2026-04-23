"""
添加"无模板"选项到数据库
运行: python add_no_template.py
"""
import sqlite3
import json
import uuid

TEMPLATE_NAME = "无模板"
TEMPLATE_DESC = "不使用任何模板效果，仅保留基础字幕"
CATEGORY = "none"
PREVIEW_IMAGE = "/templates/none.jpg"

# 无模板配置 - 只保留最基础的字幕样式
NO_TEMPLATE_CONFIG = {
    "subtitleStyles": {
        "body": {
            "font": "SimSun",
            "font_size": 18,
            "font_color": "#FFFFFF",
            "outline": 5,
            "outline_color": "#000000",
            "y": 0.85,
            "alignment": "Center"
        }
    },
    "videoEffects": {
        "enableSmartZoom": False,
        "zoomIntensity": 1.0
    },
    "backgroundMusic": None,
    "soundEffects": [],
    "openingTitle": {
        "enabled": False
    },
    "keywordFlower": {
        "enabled": False
    },
    "keywordSound": {
        "enabled": False
    }
}

def add_template():
    conn = sqlite3.connect('instance/mixcut_refactored.db')
    c = conn.cursor()
    
    # 检查是否已存在
    c.execute('SELECT id FROM templates WHERE name = ?', (TEMPLATE_NAME,))
    existing = c.fetchone()
    
    if existing:
        print(f"模板 '{TEMPLATE_NAME}' 已存在，ID: {existing[0]}")
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
        json.dumps(NO_TEMPLATE_CONFIG),
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
    c.execute('SELECT name FROM templates WHERE is_active = 1 ORDER BY sort_order')
    for i, (name,) in enumerate(c.fetchall(), 1):
        print(f"  {i}. {name}")
    
    conn.close()

if __name__ == '__main__':
    add_template()
