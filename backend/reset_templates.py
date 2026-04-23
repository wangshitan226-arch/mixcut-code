"""
重置系统模板 - 删除旧模板，创建新的3个模板
"""
import os
import sys
import uuid
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from extensions import db
from models import Template

# 创建应用
app = Flask(__name__)
# 使用绝对路径，确保能找到数据库文件
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'mixcut_refactored.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 新的3个模板配置
NEW_TEMPLATES = [
    {
        'name': '大字报风格',
        'description': '金色大字标题，适合促销和强调',
        'category': 'promotion',
        'preview_url': '',
        'config': {
            'subtitleStyles': {
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
            },
            'videoEffects': {
                'enableSmartZoom': True,
                'zoomIntensity': 1.2
            }
        }
    },
    {
        'name': '简洁知识风',
        'description': '清晰易读，适合知识分享',
        'category': 'knowledge',
        'preview_url': '',
        'config': {
            'subtitleStyles': {
                'title': {
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
                }
            },
            'videoEffects': {
                'enableSmartZoom': False
            }
        }
    },
    {
        'name': '活力动感风',
        'description': '弹跳动画，适合娱乐内容',
        'category': 'entertainment',
        'preview_url': '',
        'config': {
            'subtitleStyles': {
                'title': {
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
                }
            },
            'videoEffects': {
                'enableSmartZoom': True,
                'zoomIntensity': 1.25
            }
        }
    }
]


def reset_templates():
    with app.app_context():
        print("=" * 60)
        print("重置系统模板")
        print("=" * 60)
        
        # 0. 先创建所有表（如果不存在）
        print("\n0. 检查并创建数据库表...")
        db.create_all()
        print("   数据库表已就绪")
        
        # 1. 删除所有现有模板
        print("\n1. 删除现有模板...")
        try:
            count = Template.query.count()
            Template.query.delete()
            db.session.commit()
            print(f"   已删除 {count} 个旧模板")
        except Exception as e:
            print(f"   无需删除（可能是空表）: {e}")
            db.session.rollback()
        
        # 2. 创建新模板
        print("\n2. 创建新模板...")
        for i, tmpl_data in enumerate(NEW_TEMPLATES):
            template = Template(
                id=str(uuid.uuid4()),
                name=tmpl_data['name'],
                description=tmpl_data['description'],
                category=tmpl_data['category'],
                preview_url=tmpl_data['preview_url'],
                config=json.dumps(tmpl_data['config']),
                is_active=True,
                sort_order=i
            )
            db.session.add(template)
            print(f"   + {tmpl_data['name']}")
        
        db.session.commit()
        
        # 3. 验证
        print("\n3. 验证结果...")
        templates = Template.query.all()
        print(f"   当前共有 {len(templates)} 个模板:")
        for t in templates:
            print(f"     - {t.name}")
        
        print("\n" + "=" * 60)
        print("模板重置完成！")
        print("=" * 60)


if __name__ == '__main__':
    reset_templates()
