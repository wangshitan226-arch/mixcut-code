"""
数据库迁移脚本：添加双轨视频支持字段
运行方式：python migrate_dual_track.py

双轨制设计：
- 视频①（server_video_url）：服务器高质量拼接视频，用于ASR/导出
- 视频②（client_video_url）：客户端拼接视频，用于预览播放
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


def get_db_path():
    """获取数据库文件路径"""
    # Flask-SQLAlchemy 的 sqlite:/// 路径是相对于实例目录的
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'mixcut_refactored.db')
    if os.path.exists(db_path):
        return db_path
    
    # 尝试直接在当前目录查找
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mixcut_refactored.db')
    if os.path.exists(db_path):
        return db_path
    
    # 如果都找不到，返回默认路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'mixcut_refactored.db')


def migrate():
    """执行数据库迁移"""
    with app.app_context():
        print("=" * 60)
        print("开始数据库迁移：添加双轨视频支持字段")
        print("=" * 60)

        # 获取数据库连接
        db_path = get_db_path()
        print(f"\n数据库路径: {db_path}")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)

        # 1. 创建新表（如果有新表的话）
        print("\n1. 创建新表...")
        db.create_all()
        print("   [OK] 表创建/更新完成")

        # 2. 为Render表添加双轨视频字段
        print("\n2. 为Render表添加双轨视频字段...")
        render_columns = [
            ('server_video_url', 'VARCHAR(500)'),      # 视频①：服务器高质量拼接视频URL
            ('server_video_status', 'VARCHAR(20) DEFAULT \'pending\''),  # 视频①状态
            ('client_video_url', 'VARCHAR(500)'),       # 视频②：客户端拼接视频URL
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

        # 3. 为Material表添加缺失字段（如果有的话）
        print("\n3. 为Material表添加客户端渲染字段...")
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

        # 4. 为Render表添加OSS字段（如果缺失）
        print("\n4. 为Render表添加OSS字段...")
        if not check_column_exists(conn, 'renders', 'oss_url'):
            try:
                conn.execute("ALTER TABLE renders ADD COLUMN oss_url VARCHAR(500)")
                print("   [+] 添加字段: oss_url")
            except Exception as e:
                print(f"   [X] 添加字段失败 oss_url: {e}")
        else:
            print("   [=] 字段已存在: oss_url")

        conn.commit()
        conn.close()

        # 5. 验证表结构
        print("\n5. 验证表结构...")
        try:
            # 验证Render表
            render = Render.query.first()
            if render:
                print(f"   [OK] Render表结构正常")
                print(f"   - server_video_url: {render.server_video_url}")
                print(f"   - server_video_status: {render.server_video_status}")
                print(f"   - client_video_url: {render.client_video_url}")
                print(f"   - oss_url: {render.oss_url}")
            else:
                print("   [OK] Render表结构正常（暂无数据）")

            # 验证Material表
            mat = Material.query.first()
            if mat:
                print(f"   [OK] Material表结构正常")
                print(f"   - is_local: {mat.is_local}")
                print(f"   - width: {mat.width}")
                print(f"   - height: {mat.height}")
            else:
                print("   [OK] Material表结构正常（暂无数据）")
        except Exception as e:
            print(f"   [X] 验证失败: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 60)
        print("数据库迁移完成！")
        print("=" * 60)
        print("\n新增字段说明：")
        print("1. Render表（双轨视频）：")
        print("   - server_video_url: 视频①，服务器高质量拼接视频URL（用于ASR/导出）")
        print("   - server_video_status: 视频①处理状态（pending/processing/completed/failed）")
        print("   - client_video_url: 视频②，客户端拼接视频URL（用于预览）")
        print("2. Material表（客户端渲染）：")
        print("   - duration_seconds: 视频时长（秒）")
        print("   - is_local: 是否为客户端本地渲染素材")
        print("   - local_material_id: 客户端本地素材ID")
        print("   - width/height: 视频宽高")
        print("   - file_size: 文件大小（字节）")
        print("\n双轨制设计：")
        print("- 视频①：服务器FFmpeg高质量拼接 → OSS → ASR/导出")
        print("- 视频②：客户端秒级拼接 → 本地Blob URL → 预览播放")


if __name__ == '__main__':
    migrate()
