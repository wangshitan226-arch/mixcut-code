"""
数据库迁移脚本：添加模板系统支持
运行方式：python migrate_templates.py
"""
import os
import sys

# 添加backend目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from extensions import db
from models import Template, KaipaiEdit
from utils.ice_renderer import init_system_templates, get_default_templates
import json

# 创建临时应用实例
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mixcut_refactored.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def migrate():
    """执行数据库迁移"""
    with app.app_context():
        print("=" * 60)
        print("开始数据库迁移：添加模板系统支持")
        print("=" * 60)
        
        # 1. 创建新表
        print("\n1. 创建Template表...")
        db.create_all()
        print("   [OK] 表创建完成")
        
        # 2. 初始化系统模板
        print("\n2. 初始化系统预设模板...")
        try:
            default_templates = get_default_templates()
            
            for i, tmpl in enumerate(default_templates):
                # 检查是否已存在
                existing = Template.query.filter_by(name=tmpl['name'], is_active=True).first()
                if not existing:
                    import uuid
                    template = Template(
                        id=str(uuid.uuid4()),
                        name=tmpl['name'],
                        description=tmpl['description'],
                        category=tmpl['category'],
                        config=json.dumps(tmpl['config']),
                        is_active=True,
                        sort_order=i
                    )
                    db.session.add(template)
                    print(f"   [+] 创建模板: {tmpl['name']}")
                else:
                    print(f"   [=] 模板已存在: {tmpl['name']}")
            
            db.session.commit()
            print("   [OK] 系统模板初始化完成")
        except Exception as e:
            print(f"   [X] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. 验证模板
        print("\n3. 验证模板数据...")
        templates = Template.query.all()
        print(f"   当前共有 {len(templates)} 个模板")
        for t in templates:
            print(f"   - {t.name} ({t.category})")
        
        # 4. 验证KaipaiEdit表的新字段
        print("\n4. 验证KaipaiEdit表...")
        # 尝试查询一条记录来验证表结构
        try:
            edit = KaipaiEdit.query.first()
            if edit:
                print(f"   [OK] KaipaiEdit表结构正常")
                print(f"   - template_id字段: {edit.template_id}")
            else:
                print("   [OK] KaipaiEdit表结构正常（暂无数据）")
        except Exception as e:
            print(f"   [X] 验证失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("数据库迁移完成！")
        print("=" * 60)
        print("\n新功能说明：")
        print("1. 添加了Template表用于存储系统预设模板")
        print("2. KaipaiEdit表添加了template_id字段用于关联模板")
        print("3. 文字快剪导出时可选择模板进行ICE云端渲染")
        print("\n预设模板列表：")
        for t in templates:
            print(f"  * {t.name} - {t.description}")

if __name__ == '__main__':
    migrate()
