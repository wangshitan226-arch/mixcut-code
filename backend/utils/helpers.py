"""
Helper utilities
"""
import json
import os
from extensions import db
from models import Render


def cleanup_renders_with_material(user_id, material_id):
    """Delete all renders that contain a specific material"""
    try:
        renders = Render.query.filter_by(user_id=user_id).all()
        for render in renders:
            try:
                material_ids = json.loads(render.material_ids)
                if material_id in material_ids:
                    if render.file_path and os.path.exists(render.file_path):
                        try:
                            os.remove(render.file_path)
                        except:
                            pass
                    db.session.delete(render)
            except:
                continue
        db.session.commit()
    except Exception as e:
        print(f"Error cleaning up renders: {e}")


def clear_user_renders(user_id):
    """Clear all renders for a user"""
    try:
        renders = Render.query.filter_by(user_id=user_id).all()
        for render in renders:
            if render.file_path and os.path.exists(render.file_path):
                try:
                    os.remove(render.file_path)
                except:
                    pass
        
        Render.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        print(f"Cleared all renders for user {user_id}")
    except Exception as e:
        print(f"Error clearing renders: {e}")


def calculate_uniqueness_tag(materials):
    """Calculate uniqueness tag"""
    video_count = sum(1 for m in materials if m['type'] == 'video')
    if video_count == len(materials):
        return '完全不重复'
    elif video_count >= len(materials) // 2:
        return '极低重复率'
    else:
        return '普通'
