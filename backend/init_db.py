"""
数据库初始化脚本
运行此脚本创建数据库表结构
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from models import User, Shot, Material, Render, KaipaiEdit

def init_database():
    """初始化数据库"""
    app = create_app()
    
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("✅ 数据库表创建成功！")
        
        # 显示创建的表
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\n已创建的表 ({len(tables)} 个):")
        for table in tables:
            print(f"  - {table}")

if __name__ == '__main__':
    init_database()
