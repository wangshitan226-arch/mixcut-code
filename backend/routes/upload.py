"""
File upload routes
"""
from flask import Blueprint, request, jsonify, current_app
import os
import uuid
import threading
import time
from models import User, Shot, Material
from extensions import db, transcode_tasks
from config import UPLOAD_FOLDER, THUMBNAIL_FOLDER, UNIFIED_FOLDER
from utils import allowed_file, generate_image_thumbnail, generate_video_thumbnail, get_video_duration, format_duration, transcode_to_unified
from utils.cleanup import clear_all_user_renders
from websocket import emit_transcode_complete, emit_transcode_progress

upload_bp = Blueprint('upload', __name__, url_prefix='/api')


def async_transcode_task(task_id, material_id, input_path, output_path, quality, app, user_id=None):
    """Background transcoding task"""
    transcode_tasks[task_id] = {
        'id': task_id,
        'material_id': material_id,
        'status': 'processing',
        'progress': 0
    }
    
    try:
        transcode_tasks[task_id]['progress'] = 50
        success = transcode_to_unified(input_path, output_path, quality)
        
        if success:
            # 先更新内存状态，让前端能立即查询到完成状态
            transcode_tasks[task_id]['status'] = 'completed'
            transcode_tasks[task_id]['progress'] = 100
            print(f"[Transcode] Memory status updated to completed: {material_id}")
            
            # 通过WebSocket推送转码完成通知（零延迟）
            if user_id:
                emit_transcode_complete(user_id, material_id, task_id)
            
            # 再更新数据库
            with app.app_context():
                try:
                    material = Material.query.get(material_id)
                    if material:
                        # 从material获取user_id（如果调用时没传）
                        material_user_id = user_id or material.user_id
                        material.unified_path = output_path
                        db.session.commit()
                        print(f"[Transcode] Database updated: {material_id}")
                        
                        # 如果之前没发WebSocket通知，现在发
                        if not user_id and material_user_id:
                            emit_transcode_complete(material_user_id, material_id, task_id)
                    else:
                        print(f"[Transcode] Material not found: {material_id}")
                except Exception as db_error:
                    print(f"[Transcode] Database update error: {db_error}")
                    db.session.rollback()
                    # Retry once
                    time.sleep(0.5)
                    try:
                        material = Material.query.get(material_id)
                        if material:
                            material.unified_path = output_path
                            db.session.commit()
                            print(f"[Transcode] Database updated (retry): {material_id}")
                    except Exception as retry_error:
                        print(f"[Transcode] Database update failed after retry: {retry_error}")
                        db.session.rollback()
        else:
            transcode_tasks[task_id]['status'] = 'failed'
            print(f"[Transcode] Transcode failed: {material_id}")
    except Exception as e:
        transcode_tasks[task_id]['status'] = 'failed'
        transcode_tasks[task_id]['error'] = str(e)
        print(f"[Transcode] Error: {material_id} - {str(e)}")


@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    """Upload file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        user_id = request.form.get('user_id')
        shot_id = request.form.get('shotId')
        quality = request.form.get('quality', 'medium')
        
        if not user_id:
            return jsonify({'error': '没有指定用户ID'}), 400
        if not shot_id:
            return jsonify({'error': '没有指定镜头ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        try:
            shot_id = int(shot_id)
        except ValueError:
            return jsonify({'error': '无效的镜头ID'}), 400
        
        shot = Shot.query.get(shot_id)
        if not shot or shot.user_id != user_id:
            return jsonify({'error': '镜头不存在或无权限'}), 404
        
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # Clear all renders for this user when adding new material
        # This ensures old renders don't show outdated content
        clear_all_user_renders(user_id)
        
        material_id = str(uuid.uuid4())
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{material_id}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        thumbnail_filename = f"{material_id}_thumb.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_filename)
        
        is_video = ext in {'mp4', 'mov', 'avi', 'webm'}
        
        if is_video:
            generate_video_thumbnail(filepath, thumbnail_path)
            duration_seconds = get_video_duration(filepath)
            duration = format_duration(duration_seconds)
        else:
            generate_image_thumbnail(filepath, thumbnail_path)
            duration_seconds = 3.0  # 图片默认3秒
            duration = '0:03'
        
        unified_filename = f"{material_id}_unified.mp4"
        unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
        
        material = Material(
            id=material_id,
            user_id=user_id,
            shot_id=shot_id,
            type='video' if is_video else 'image',
            original_name=file.filename,
            file_path=filepath,
            unified_path=None,
            thumbnail_path=thumbnail_path,
            duration=duration,
            duration_seconds=duration_seconds  # 保存数值类型，用于快速计算
        )
        db.session.add(material)
        db.session.commit()
        
        # Start processing task
        task_id = f"transcode_{material_id}"
        app = current_app._get_current_object()  # Get the actual app object
        thread = threading.Thread(
            target=async_transcode_task,
            args=(task_id, material_id, filepath, unified_path, quality, app, user_id)  # 传递user_id用于WebSocket通知
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'id': material_id,
            'type': 'video' if is_video else 'image',
            'url': f'/uploads/{filename}',
            'thumbnail': f'/uploads/thumbnails/{thumbnail_filename}',
            'duration': duration,
            'originalName': file.filename,
            'transcode_task_id': task_id,
            'transcode_status': 'processing'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/transcode/<task_id>/status', methods=['GET'])
def get_transcode_status(task_id):
    """Get transcoding status - 优化：优先返回内存状态，减少数据库查询"""
    # 优先检查内存中的任务状态（最快）
    if task_id in transcode_tasks:
        task = transcode_tasks[task_id]
        # 如果内存状态是completed，直接返回，不查询数据库
        if task['status'] == 'completed':
            return jsonify({
                'task_id': task_id,
                'status': 'completed',
                'progress': 100
            })
        # 其他状态直接返回
        return jsonify({
            'task_id': task_id,
            'status': task['status'],
            'progress': task.get('progress', 0)
        })
    
    # 内存中没有，检查数据库（任务可能已完成并被清理）
    material_id = task_id.replace('transcode_', '')
    material = Material.query.get(material_id)
    if material and material.unified_path and os.path.exists(material.unified_path):
        return jsonify({
            'task_id': task_id,
            'status': 'completed',
            'progress': 100
        })
    
    return jsonify({'error': '任务不存在'}), 404
