"""
Material management routes
"""
from flask import Blueprint, request, jsonify, current_app
import os
import time
import threading
import uuid
from models import Material, User
from extensions import db, transcode_tasks
from utils import cleanup_renders_with_material, transcode_to_unified
from utils.cleanup import clear_all_user_renders
from config import UPLOAD_FOLDER, THUMBNAIL_FOLDER, UNIFIED_FOLDER

materials_bp = Blueprint('materials', __name__, url_prefix='/api')


@materials_bp.route('/materials/upload', methods=['POST'])
def upload_material():
    """
    上传原始视频文件到本地，并进行FFmpeg转码
    双轨制：浏览器WebCodecs + 本地FFmpeg同时转码
    """
    try:
        if 'video_file' not in request.files:
            return jsonify({'error': '没有视频文件'}), 400
        
        file = request.files['video_file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        user_id = request.form.get('user_id')
        material_id = request.form.get('material_id')
        duration = request.form.get('duration', '0')
        width = request.form.get('width', '0')
        height = request.form.get('height', '0')
        file_size = request.form.get('file_size', '0')
        
        if not user_id or not material_id:
            return jsonify({'error': '缺少用户ID或素材ID'}), 400
        
        # 保存原始视频文件
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'mp4'
        filename = f"{material_id}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # 保存缩略图（如果有）
        thumbnail_path = None
        if 'thumbnail' in request.files:
            thumb_file = request.files['thumbnail']
            thumb_filename = f"{material_id}_thumb.jpg"
            thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumb_filename)
            thumb_file.save(thumbnail_path)
        
        # 设置unified_path（本地FFmpeg转码输出路径）
        unified_filename = f"{material_id}_unified.mp4"
        unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
        
        # 检查素材是否已存在
        material = Material.query.get(material_id)
        if material:
            # 更新现有素材
            material.file_path = filepath
            material.unified_path = None  # 等待转码完成
            if thumbnail_path:
                material.thumbnail_path = thumbnail_path
            db.session.commit()
        else:
            # 创建新素材记录
            material = Material(
                id=material_id,
                user_id=user_id,
                type='video',
                original_name=file.filename,
                file_path=filepath,
                unified_path=None,
                thumbnail_path=thumbnail_path,
                duration=duration,
                duration_seconds=float(duration) if duration else 0,
                is_local=True,
                width=int(width) if width else 0,
                height=int(height) if height else 0,
                file_size=int(file_size) if file_size else 0
            )
            db.session.add(material)
            db.session.commit()
        
        # 启动本地FFmpeg转码（异步）
        task_id = f"transcode_{material_id}"
        app = current_app._get_current_object()
        
        def transcode_task():
            """后台转码任务"""
            with app.app_context():
                try:
                    print(f"[本地FFmpeg转码] 开始: {material_id}")
                    success = transcode_to_unified(filepath, unified_path, 'medium')
                    
                    if success:
                        material = Material.query.get(material_id)
                        if material:
                            material.unified_path = unified_path
                            db.session.commit()
                            print(f"[本地FFmpeg转码] 完成: {material_id} -> {unified_path}")
                    else:
                        print(f"[本地FFmpeg转码] 失败: {material_id}")
                except Exception as e:
                    print(f"[本地FFmpeg转码] 异常: {material_id} - {e}")
        
        thread = threading.Thread(target=transcode_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'id': material_id,
            'file_path': filepath,
            'unified_path': unified_path,
            'transcode_task_id': task_id,
            'transcode_status': 'processing',
            'message': '原始视频已上传到本地，FFmpeg转码中'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


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
