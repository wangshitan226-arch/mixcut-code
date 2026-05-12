"""
更新 SimSun 模板配置
运行: python update_simsun_template.py
"""
import sqlite3
import json

conn = sqlite3.connect('instance/mixcut_refactored.db')
c = conn.cursor()

# 获取宋体大字模板的当前配置
c.execute("SELECT id, config FROM templates WHERE name = '宋体大字模板'")
row = c.fetchone()

if row:
    template_id, config_json = row
    config = json.loads(config_json)
    
    # 更新字幕样式配置
    config['subtitleStyles'] = {
        "body": {
            "font": "SimSun",
            "font_size": 80,
            "font_color": "#FFFFFF",
            "outline": 5,
            "outline_color": "#000000",
            "motion_in": "fade_in",
            "motion_out": "fade_out",
            "x": 0.5,
            "y": 0.80,
            "alignment": "Center",
            "adapt_mode": "AutoWrap",
            "size_request_type": "RealDim"
        },
        "emphasis": {
            "font": "SimSun",
            "font_size": 80,
            "font_color": "#FFFFFF",
            "outline": 5,
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
            "font_size": 80,
            "font_color": "#FFFFFF",
            "outline": 5,
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
    }
    
    # 更新视频效果
    config['videoEffects'] = {
        "enableSmartZoom": False,
        "zoomIntensity": 1.0
    }
    
    # 更新背景音乐
    config['backgroundMusic'] = {
        "url": "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/bgm/the_mountain-festive-festive-music-508015.mp3",
        "volume": 0.4
    }
    
    # 更新音效 - 只保留wow音效，删除bell音效
    config['soundEffects'] = [
        {
            "name": "wow",
            "url": "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/dragon-studio-wow-423653.mp3",
            "trigger": "emphasis"
        }
    ]
    
    # 开场标题配置
    config['openingTitle'] = {
        "enabled": True,
        "font": "SourceHanSansCN-Bold",
        "font_size": 120,
        "font_color": "#000000",
        "font_weight": "Bold",
        "x": 0.5,
        "y": 0.1,
        "alignment": "Center",
        "duration": 5,
        "motion_in": "bounce_in",
        "motion_out": "fade_out",
        # 使用系统花字样式 CS0001-000004（黄色背景效果）
        "effect_color_style": "CS0001-000004"
    }
    
    # 关键词花字配置
    config['keywordFlower'] = {
        "enabled": True,
        "font": "SourceHanSansCN-Bold",
        "font_size": 80,
        "font_color": "#FFFFFF",
        "effect_color_style": "CS0001-000008",
        "x": 0.7,
        "y": 0.3,
        "x_offset": 100,
        "y_offset": 80,
        "alignment": "TopLeft",
        "duration": 2,
        "motion_effects": ["pop_in", "slide_up", "slide_left", "bounce_in"],
        "motion_out": "fade_out"
    }
    
    # 关键词音效配置
    config['keywordSound'] = {
        "enabled": True,
        "sound_urls": [
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/dragon-studio-wow-423653.mp3",
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/u_7xr5ffk4oq-opening-bell-421471.mp3",
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/dragon-studio-pop-402324.mp3",
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/kauasilbershlachparodes-camera-flash-494027.mp3"
        ],
        "duration": 1.5,
        "volume": 0.7
    }
    
    # 更新预览图
    preview_url = "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/img/001.jpg"
    
    # 更新数据库
    c.execute('UPDATE templates SET preview_url = ?, config = ? WHERE id = ?',
              (preview_url, json.dumps(config), template_id))
    conn.commit()
    
    print('模板更新成功!')
    print(f'  ID: {template_id}')
    print(f'  字体: SimSun')
    print(f'  字号: 80')
    print(f'  描边: 5')
    print(f'  位置: Y=0.85, 居中')
    print(f'  预览图: {preview_url}')
    print(f'  BGM: {config["backgroundMusic"]["url"]}')
    print(f'  开场标题: 已启用')
    print(f'  关键词花字: 已启用')
    print(f'  关键词音效: 已启用')
    
else:
    print('未找到宋体大字模板')

conn.close()
