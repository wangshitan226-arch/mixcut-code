"""
添加数字人渲染模板到数据库

两种数字人视频类型：
- digital_human_pure: 纯口播，无字幕包装，直接VideoRetalk渲染
- digital_human_mix: 口播混剪，VideoRetalk渲染后作为素材进行智能混剪

模板的 config 不是 ICE Timeline 配置，而是渲染管线配置：
- avatarConfig: VideoRetalk 对口型配置
- mixConfig: 混剪配置（仅 mix 类型）
- pureConfig: 纯口播配置（仅 pure 类型）

运行: python add_digital_human_template.py
"""
import sqlite3
import json
import uuid

DIGITAL_HUMAN_TEMPLATES = [
    {
        "name": "数字人纯口播",
        "description": "无字幕包装，直接生成数字人对口型视频，适合专业剪辑二次创作",
        "category": "digital_human_pure",
        "preview_url": "/templates/dh_pure.jpg",
        "sort_order": 100,
        "config": {
            "renderType": "pure",
            "avatarConfig": {
                "enabled": True,
                "video_extension": False
            },
            "pureConfig": {
                "addSubtitles": False,
                "addBgm": False,
                "addSoundEffects": False
            }
        }
    },
    {
        "name": "数字人口播混剪-网感白橙",
        "description": "数字人+素材智能混剪，网感白橙风格，自动加字幕/标题/特效",
        "category": "digital_human_mix",
        "preview_url": "/templates/dh_mix_white_orange.jpg",
        "sort_order": 101,
        "config": {
            "renderType": "mix",
            "avatarConfig": {
                "enabled": True,
                "video_extension": False
            },
            "mixConfig": {
                "style": "网感白橙",
                "addSubtitles": True,
                "addBgm": True,
                "addSoundEffects": True,
                "subtitleStyles": {
                    "title": {
                        "font": "AlibabaPuHuiTi-Heavy",
                        "font_size": 85,
                        "font_color": "#FF6B35",
                        "outline": 5,
                        "outline_color": "#8B2500",
                        "motion_in": "rotateup_in",
                        "motion_out": "close_out",
                        "y": 0.06,
                        "weight": 1.5
                    },
                    "subtitle": {
                        "font": "AlibabaPuHuiTi-Heavy",
                        "font_size": 62,
                        "font_color": "#FFFFFF",
                        "outline": 4,
                        "outline_color": "#333333",
                        "motion_in": "slingshot_in",
                        "motion_out": "slingshot_out",
                        "y": 0.80,
                        "weight": 1.3
                    },
                    "emphasis": {
                        "font": "AlibabaPuHuiTi-Heavy",
                        "font_size": 56,
                        "font_color": "#FFD300",
                        "outline": 4,
                        "outline_color": "#8C5F00",
                        "motion_in": "wave_in",
                        "motion_out": "wave_out",
                        "y": 0.88,
                        "weight": 1.2,
                        "loop": 2,
                        "loop_effect": "bounce"
                    }
                },
                "backgroundMusic": {
                    "url": "/templates/bgm/the_mountain-festive-festive-music-508015.mp3",
                    "volume": 0.3
                },
                "soundEffects": [
                    {"name": "wow", "url": "/templates/sound_effact/dragon-studio-wow-423653.mp3", "trigger": "emphasis"},
                    {"name": "bell", "url": "/templates/sound_effact/u_7xr5ffk4oq-opening-bell-421471.mp3", "trigger": "title"}
                ]
            }
        }
    },
    {
        "name": "数字人口播混剪-大字报",
        "description": "数字人+素材智能混剪，大字报风格，醒目标题+花字特效",
        "category": "digital_human_mix",
        "preview_url": "/templates/dh_mix_big_text.jpg",
        "sort_order": 102,
        "config": {
            "renderType": "mix",
            "avatarConfig": {
                "enabled": True,
                "video_extension": False
            },
            "mixConfig": {
                "style": "大字报",
                "addSubtitles": True,
                "addBgm": True,
                "addSoundEffects": True,
                "subtitleStyles": {
                    "title": {
                        "font": "AlibabaPuHuiTi-Heavy",
                        "font_size": 95,
                        "font_color": "#FFD300",
                        "outline": 6,
                        "outline_color": "#996B00",
                        "motion_in": "rotateup_in",
                        "motion_out": "close_out",
                        "y": 0.08,
                        "weight": 1.5
                    },
                    "subtitle": {
                        "font": "AlibabaPuHuiTi-Heavy",
                        "font_size": 75,
                        "font_color": "#FFFFFF",
                        "outline": 5,
                        "outline_color": "#5C3A21",
                        "motion_in": "slingshot_in",
                        "motion_out": "slingshot_out",
                        "y": 0.18,
                        "weight": 1.3
                    },
                    "emphasis": {
                        "font": "AlibabaPuHuiTi-Heavy",
                        "font_size": 52,
                        "font_color": "#FFD300",
                        "outline": 4,
                        "outline_color": "#8C5F00",
                        "motion_in": "wave_in",
                        "motion_out": "wave_out",
                        "y": 0.88,
                        "weight": 1.2,
                        "loop": 2,
                        "loop_effect": "bounce"
                    }
                },
                "backgroundMusic": {
                    "url": "/templates/bgm/the_mountain-festive-festive-music-508015.mp3",
                    "volume": 0.4
                },
                "soundEffects": [
                    {"name": "wow", "url": "/templates/sound_effact/dragon-studio-wow-423653.mp3", "trigger": "emphasis"},
                    {"name": "bell", "url": "/templates/sound_effact/u_7xr5ffk4oq-opening-bell-421471.mp3", "trigger": "title"}
                ]
            }
        }
    },
    {
        "name": "数字人口播混剪-专业蓝",
        "description": "数字人+素材智能混剪，专业蓝风格，适合企业宣传和课程讲解",
        "category": "digital_human_mix",
        "preview_url": "/templates/dh_mix_pro_blue.jpg",
        "sort_order": 103,
        "config": {
            "renderType": "mix",
            "avatarConfig": {
                "enabled": True,
                "video_extension": False
            },
            "mixConfig": {
                "style": "专业蓝",
                "addSubtitles": True,
                "addBgm": True,
                "addSoundEffects": False,
                "subtitleStyles": {
                    "title": {
                        "font": "SourceHanSansCN-Bold",
                        "font_size": 68,
                        "font_color": "#2C3E50",
                        "outline": 3,
                        "outline_color": "#FFFFFF",
                        "motion_in": "fade_in",
                        "motion_out": "fade_out",
                        "y": 0.06,
                        "weight": 1.5
                    },
                    "subtitle": {
                        "font": "SourceHanSansCN-Regular",
                        "font_size": 48,
                        "font_color": "#FFFFFF",
                        "outline": 3,
                        "outline_color": "#2C3E50",
                        "motion_in": "fade_in",
                        "motion_out": "fade_out",
                        "y": 0.84,
                        "weight": 1.0
                    },
                    "emphasis": {
                        "font": "SourceHanSansCN-Bold",
                        "font_size": 52,
                        "font_color": "#3498DB",
                        "outline": 3,
                        "outline_color": "#1A5276",
                        "motion_in": "close_in",
                        "motion_out": "close_out",
                        "y": 0.90,
                        "weight": 1.2
                    }
                },
                "backgroundMusic": {
                    "url": "",
                    "volume": 0.15
                },
                "soundEffects": []
            }
        }
    }
]


def add_digital_human_templates():
    conn = sqlite3.connect('instance/mixcut_refactored.db')
    c = conn.cursor()

    c.execute("DELETE FROM templates WHERE category IN ('digital_human', 'digital_human_pure', 'digital_human_mix')")
    deleted = c.rowcount
    if deleted:
        print(f"  清理旧数字人模板: {deleted} 个")

    added = 0
    for tpl in DIGITAL_HUMAN_TEMPLATES:
        new_id = str(uuid.uuid4())
        c.execute('''
            INSERT INTO templates
            (id, name, description, category, preview_url, config, is_active, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, datetime('now'), datetime('now'))
        ''', (
            new_id,
            tpl['name'],
            tpl['description'],
            tpl['category'],
            tpl['preview_url'],
            json.dumps(tpl['config'], ensure_ascii=False),
            tpl['sort_order']
        ))
        added += 1
        print(f"  添加: {tpl['name']} [{tpl['category']}]")

    conn.commit()

    print(f"\n数字人模板初始化完成: 添加 {added} 个")

    c.execute('SELECT name, category FROM templates ORDER BY sort_order')
    print("\n当前所有模板:")
    for i, (name, cat) in enumerate(c.fetchall(), 1):
        marker = "★" if 'digital_human' in cat else " "
        print(f"  {i}. [{marker}] {name} ({cat})")

    conn.close()


if __name__ == '__main__':
    add_digital_human_templates()
