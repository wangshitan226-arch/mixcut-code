"""
添加 Pexels 画中画模板到数据库
修改下面的参数后运行: python add_template_pexels.py
"""
import sqlite3
import json
import uuid
import os
import sys

# 确保在 backend 目录下运行
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ==================== 模板配置 ====================
TEMPLATE_NAME = "粉白蓝"
TEMPLATE_DESC = "阿里云字幕样式 + Pexels全屏画中画，背景模糊处理"
CATEGORY = "pexels_pip"
PREVIEW_IMAGE = "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/img/1.png"

# 字幕样式配置 - 参考阿里云官方文档示例
SUBTITLE_CONFIG = {
    # 字幕样式配置
    "subtitleStyles": {
        # 1. 主标题样式 - 大字号，顶部居中
        "title": {
            "font": "AlibabaPuHuiTi-Heavy",
            "font_size": 80,
            "font_color": "#FFFFFF",
            "outline": 2,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "y": 200,  # 顶部位置
            "alignment": "TopCenter",
            "effect_color_style": "CS0003-000011",  # 花字效果
            "font_face": {
                "Bold": True
            }
        },
        # 2. 副标题样式 - 楷体，斜体下划线
        "subtitle": {
            "font": "KaiTi",
            "font_size": 45,
            "font_color": "#ffffff",
            "outline": 1,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "y": 320,
            "alignment": "TopCenter",
            "font_face": {
                "Italic": True,
                "Underline": True
            }
        },
        # 3. 旋转角度字幕 - 金色，带描边
        "emphasis": {
            "font": "AlibabaPuHuiTi",
            "font_size": 60,
            "font_color": "#FFD700",  # 金色
            "outline": 4,
            "outline_color": "#000000",
            "angle": 350,  # 旋转角度
            "motion_in": "rotateup_in",
            "motion_out": "rotateup_out",
            "y": 740,
            "alignment": "TopLeft",
            "x": 50,
            "font_face": {
                "Bold": True
            }
        },
        # 4. 横幅字幕 - 多行，顶部居中
        "body": {
            "font": "AlibabaPuHuiTi",
            "font_size": 40,
            "font_color": "#ffffff",
            "outline": 1,
            "outline_color": "000000",
            "motion_in": "scroll_right_in",
            "motion_out": "scroll_right_out",
            "y": 900,
            "alignment": "TopCenter",
            "font_face": {
                "Bold": True,
                "Italic": False,
                "Underline": False
            }
        },
        # 5. 带时间控制的字幕
        "section": {
            "font": "KaiTi",
            "font_size": 40,
            "font_color": "#ffffff",
            "outline": 1,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "y": 1000,
            "alignment": "TopCenter",
            "font_face": {
                "Bold": False,
                "Italic": True,
                "Underline": False
            }
        }
    },
    
    # 视频效果配置
    "videoEffects": {
        "enableSmartZoom": False,
        "zoomIntensity": 1.0
    },
    
    # Pexels 画中画配置
    "pexelsConfig": {
        "enabled": True,  # 启用 Pexels 画中画
        "blurRadius": 0.1,  # 背景模糊半径
        "maxKeywords": 3,  # 最大关键词数量
        "searchOrientation": "portrait"  # 搜索竖屏视频
    },
    
    # 背景音乐（可选）
    "backgroundMusic": {
        "url": "",
        "volume": 0.3
    }
}
# =================================================


def add_template():
    """添加模板到数据库"""
    db_path = 'instance/mixcut_refactored.db'
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        print("请确保在 backend 目录下运行此脚本")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 检查模板是否已存在
    c.execute('SELECT id FROM templates WHERE name = ?', (TEMPLATE_NAME,))
    existing = c.fetchone()
    
    if existing:
        print(f"模板 '{TEMPLATE_NAME}' 已存在，ID: {existing[0]}")
        print("如需重新添加，请先删除现有模板")
        conn.close()
        return
    
    # 获取当前最大 sort_order
    c.execute('SELECT MAX(sort_order) FROM templates')
    max_order = c.fetchone()[0] or 0
    
    # 插入新模板
    new_template = (
        str(uuid.uuid4()),
        TEMPLATE_NAME,
        TEMPLATE_DESC,
        CATEGORY,
        PREVIEW_IMAGE,
        json.dumps(SUBTITLE_CONFIG, ensure_ascii=False),
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
    print(f"\n模板添加成功!")
    print(f"  ID: {row[0]}")
    print(f"  名称: {row[1]}")
    print(f"  预览图: {row[2]}")
    
    # 显示所有模板
    print("\n当前所有模板:")
    c.execute('SELECT name, category FROM templates ORDER BY sort_order')
    for i, (name, category) in enumerate(c.fetchall(), 1):
        print(f"  {i}. {name} ({category})")
    
    conn.close()
    
    print(f"\n提示: 使用此模板需要配置 Pexels API Key")
    print(f"  请在环境变量中设置: PEXELS_API_KEY")
    print(f"  或在 utils/pexels_client.py 中修改默认配置")


if __name__ == '__main__':
    add_template()
