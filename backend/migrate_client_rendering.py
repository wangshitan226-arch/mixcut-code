"""
数据库迁移脚本：添加客户端渲染支持字段
运行方式：python migrate_client_rendering.py
"""
import os
import sys

# 添加backend目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from extensions import db
from models import Material, Render
import sqlite3

# 创建临时应用实例
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mixcut_refactored.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


def check_column_exists(conn, table_name, column_name):
    """检查表中是否存在指定字段"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate():
    """执行数据库迁移"""
    with app.app_context():
        print("=" * 60)
        print("开始数据库迁移：添加客户端渲染支持字段")
        print("=" * 60)

        # 获取数据库连接（注意：Flask-SQLAlchemy 的 sqlite:/// 路径是相对于实例目录的）
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'mixcut_refactored.db')
        if not os.path.exists(db_path):
            # 尝试直接在当前目录查找
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mixcut_refactored.db')
        conn = sqlite3.connect(db_path)

        # 1. 创建新表（如果有新表的话）
        print("\n1. 创建新表...")
        db.create_all()
        print("   [OK] 表创建/更新完成")

        # 2. 为Material表添加新字段
        print("\n2. 为Material表添加客户端渲染字段...")
        material_columns = [
            ('duration_seconds', 'FLOAT DEFAULT 0'),
            ('is_local', 'BOOLEAN DEFAULT 0'),
            ('local_material_id', 'VARCHAR(36)'),
            ('width', 'INTEGER'),
            ('height', 'INTEGER'),
            ('file_size', 'BIGINT'),
        ]

        for column_name, column_type in material_columns:
            if not check_column_exists(conn, 'materials', column_name):
                try:
                    conn.execute(f"ALTER TABLE materials ADD COLUMN {column_name} {column_type}")
                    print(f"   [+] 添加字段: {column_name}")
                except Exception as e:
                    print(f"   [X] 添加字段失败 {column_name}: {e}")
            else:
                print(f"   [=] 字段已存在: {column_name}")

        # 3. 为Render表添加新字段
        print("\n3. 为Render表添加OSS字段...")
        render_columns = [
            ('oss_url', 'VARCHAR(500)'),
        ]

        for column_name, column_type in render_columns:
            if not check_column_exists(conn, 'renders', column_name):
                try:
                    conn.execute(f"ALTER TABLE renders ADD COLUMN {column_name} {column_type}")
                    print(f"   [+] 添加字段: {column_name}")
                except Exception as e:
                    print(f"   [X] 添加字段失败 {column_name}: {e}")
            else:
                print(f"   [=] 字段已存在: {column_name}")

        conn.commit()
        conn.close()

        # 4. 验证表结构
        print("\n4. 验证表结构...")
        try:
            # 验证Material表
            mat = Material.query.first()
            if mat:
                print(f"   [OK] Material表结构正常")
                print(f"   - is_local字段: {mat.is_local}")
                print(f"   - width字段: {mat.width}")
                print(f"   - height字段: {mat.height}")
            else:
                print("   [OK] Material表结构正常（暂无数据）")

            # 验证Render表
            render = Render.query.first()
            if render:
                print(f"   [OK] Render表结构正常")
                print(f"   - oss_url字段: {render.oss_url}")
            else:
                print("   [OK] Render表结构正常（暂无数据）")
        except Exception as e:
            print(f"   [X] 验证失败: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 60)
        print("数据库迁移完成！")
        print("=" * 60)
        print("\n新增字段说明：")
        print("1. Material表：")
        print("   - duration_seconds: 视频时长（秒，数值类型）")
        print("   - is_local: 是否为客户端本地渲染素材")
        print("   - local_material_id: 客户端本地素材ID")
        print("   - width/height: 视频宽高")
        print("   - file_size: 文件大小（字节）")
        print("2. Render表：")
        print("   - oss_url: OSS文件URL")
        print("\n新功能说明：")
        print("- 支持客户端渲染模式（浏览器本地转码）")
        print("- 支持前端直传OSS")
        print("- 支持ICE模板渲染使用客户端渲染结果")


if __name__ == '__main__':
    migrate()
