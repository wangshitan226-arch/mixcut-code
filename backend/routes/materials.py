"""
Material management routes
"""
from flask import Blueprint, jsonify
import os
import time
from models import Material
from extensions import db
from utils import cleanup_renders_with_material
from utils.cleanup import clear_all_user_renders

materials_bp = Blueprint('materials', __name__, url_prefix='/api')


@materials_bp.route('/materials/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete a material"""
    try:
        material = Material.query.get_or_404(material_id)
        user_id = material.user_id
        
        print(f"\n[DELETE MATERIAL] material_id: {material_id}")
        print(f"[DELETE MATERIAL] user_id from material: {user_id}")
        print(f"[DELETE MATERIAL] material.file_path: {material.file_path}")
        
        # First, delete material files to free up disk space
        deleted_files = []
        for path in [material.file_path, material.unified_path, material.thumbnail_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    deleted_files.append(path)
                    print(f"[DELETE MATERIAL] Deleted file: {path}")
                except Exception as e:
                    print(f"[DELETE MATERIAL] Failed to delete {path}: {e}")
        
        # Delete material from database
        db.session.delete(material)
        db.session.commit()
        
        print(f"[DELETE MATERIAL] Material deleted from DB. deleted_files count: {len(deleted_files)}")
        
        # Then clear all renders for this user (after material is deleted)
        # This ensures old renders don't show outdated content
        print(f"[DELETE MATERIAL] About to call clear_all_user_renders with user_id: {user_id}")
        clear_all_user_renders(user_id)
        
        return jsonify({
            'message': '素材已删除',
            'deleted_files': len(deleted_files)
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting material: {e}")
        return jsonify({'error': str(e)}), 500
