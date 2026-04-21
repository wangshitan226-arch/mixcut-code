"""
Cleanup utilities for user data - OSS版本
支持本地文件和OSS文件的清理
"""
import os
import glob
from config import RENDERS_FOLDER
from extensions import db
from models import Render
# 新增导入
from utils.oss import oss_client


def clear_user_render_files(user_id):
    """
    清理用户的渲染文件
    支持本地文件和OSS文件
    """
    deleted_count = 0
    try:
        print(f"[CLEANUP] ====== START clear_user_render_files ======")
        print(f"[CLEANUP] User ID: '{user_id}' (type: {type(user_id)})")
        
        # 1. 查询该用户的所有渲染记录
        renders = Render.query.filter_by(user_id=user_id).all()
        print(f"[CLEANUP] 找到 {len(renders)} 个渲染记录")
        
        for render in renders:
            file_path = render.file_path
            if not file_path:
                continue
            
            if file_path.startswith('http'):
                # OSS文件，调用OSS删除
                print(f"[CLEANUP] 删除OSS文件: {file_path}")
                success = oss_client.delete_render(file_path)
                if success:
                    deleted_count += 1
            else:
                # 本地文件，直接删除
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        print(f"[CLEANUP] 删除本地文件: {file_path}")
                    except Exception as e:
                        print(f"[CLEANUP] 删除本地文件失败: {file_path}, {e}")
        
        # 2. 清理可能遗漏的本地文件（兼容旧数据）
        if os.path.exists(RENDERS_FOLDER):
            pattern = os.path.join(RENDERS_FOLDER, f'render_combo_{user_id}_*.mp4')
            files = glob.glob(pattern)
            for filepath in files:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"[CLEANUP] 删除遗留文件: {filepath}")
                except Exception as e:
                    print(f"[CLEANUP] 删除遗留文件失败: {filepath}, {e}")
        
        print(f"[CLEANUP] 总计删除: {deleted_count} 个文件")
        print(f"[CLEANUP] ====== END clear_user_render_files ======")
        
    except Exception as e:
        print(f"[CLEANUP] ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    return deleted_count


def clear_user_renders_db(user_id):
    """Clear all render records from database for a user"""
    try:
        print(f"[CLEANUP] 清理用户 {user_id} 的数据库记录")
        
        count_before = Render.query.filter_by(user_id=user_id).count()
        result = Render.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        
        print(f"[CLEANUP] 删除 {result} 条数据库记录")
    except Exception as e:
        print(f"[CLEANUP] ERROR: {e}")
        db.session.rollback()


def clear_all_user_renders(user_id):
    """
    清理用户的所有渲染（文件 + 数据库）
    支持本地和OSS存储
    """
    print(f"\n{'='*60}")
    print(f"[CLEANUP] 开始清理用户 {user_id} 的所有渲染")
    print(f"{'='*60}")
    
    # 先删除文件（OSS + 本地）
    file_count = clear_user_render_files(user_id)
    
    # 再删除数据库记录
    clear_user_renders_db(user_id)
    
    print(f"[CLEANUP] 完成: 删除 {file_count} 个文件")
    print(f"{'='*60}\n")
