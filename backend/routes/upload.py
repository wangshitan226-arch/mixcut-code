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
        # 接受前端传入的 material_id（双轨制需要前后端ID一致）
        material_id = request.form.get('material_id')
        
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
        
        # 如果前端没有传入 material_id，则生成新的
        if not material_id:
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
        
        # 构建返回数据
        # 本地URL用于前端缓存到浏览器本地存储（WebCodecs预览用）
        local_url = f'/uploads/{filename}'
        
        return jsonify({
            'id': material_id,
            'type': 'video' if is_video else 'image',
            'url': local_url,                    # 本地URL（给前端缓存用）
            'thumbnail': f'/uploads/thumbnails/{thumbnail_filename}',
            'duration': duration,
            'originalName': file.filename,
            'transcode_task_id': task_id,
            'transcode_status': 'processing',
            # 新增字段：用于前端识别和缓存
            'local_url': local_url,              # 本地文件URL
            'can_cache': True,                   # 是否可以缓存到浏览器
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


@upload_bp.route('/materials/<material_id>/download', methods=['GET'])
def download_material(material_id):
    """
    下载素材文件（用于前端缓存到浏览器本地存储）
    
    这个接口允许前端下载完整的视频文件，然后缓存到 IndexedDB/OPFS 中，
    实现零延迟的本地播放。
    """
    try:
        material = Material.query.get(material_id)
        if not material:
            return jsonify({'error': '素材不存在'}), 404
        
        # 检查文件是否存在
        if not os.path.exists(material.file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 返回文件
        from flask import send_file
        return send_file(
            material.file_path,
            as_attachment=False,  # 不作为附件下载，直接播放
            mimetype='video/mp4'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/materials/metadata', methods=['POST'])
def upload_material_metadata():
    """
    上传素材元数据（客户端渲染模式 + 双轨制本地FFmpeg转码）
    
    双轨制设计：
    1. 浏览器WebCodecs转码 → 存浏览器本地（视频②预览用）
    2. 本地FFmpeg转码 → 存服务器磁盘 unified/ 文件夹（视频①ASR/导出用）
    
    请求参数：
    - user_id: 用户ID
    - shot_id: 镜头ID
    - material_id: 客户端生成的素材ID
    - duration: 视频时长（秒）
    - width: 视频宽度
    - height: 视频高度
    - file_size: 文件大小（字节）
    - video_file: 原始视频文件（用于本地FFmpeg转码）
    - thumbnail: 缩略图文件（可选）
    """
    try:
        user_id = request.form.get('user_id')
        shot_id = request.form.get('shot_id')
        material_id = request.form.get('material_id')
        duration = request.form.get('duration', '0')
        width = request.form.get('width')
        height = request.form.get('height')
        file_size = request.form.get('file_size', '0')
        
        if not user_id:
            return jsonify({'error': '没有指定用户ID'}), 400
        if not shot_id:
            return jsonify({'error': '没有指定镜头ID'}), 400
        if not material_id:
            return jsonify({'error': '没有指定素材ID'}), 400
        
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
        
        # 处理缩略图上传
        thumbnail_path = None
        if 'thumbnail' in request.files:
            thumbnail_file = request.files['thumbnail']
            if thumbnail_file and thumbnail_file.filename:
                thumbnail_filename = f"{material_id}_thumb.jpg"
                thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_filename)
                thumbnail_file.save(thumbnail_path)
        
        # 转换时长为字符串格式
        duration_seconds = float(duration)
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        duration_str = f"{minutes}:{seconds:02d}"
        
        # ========== 双轨制：本地FFmpeg转码 ==========
        # 检查是否有原始视频文件上传（用于本地FFmpeg转码）
        file_path = 'local'  # 默认标记为本地素材
        unified_path = None  # 等待本地FFmpeg转码完成
        
        if 'video_file' in request.files:
            video_file = request.files['video_file']
            if video_file and video_file.filename:
                # 保存原始视频文件到 uploads/ 文件夹
                ext = video_file.filename.rsplit('.', 1)[1].lower() if '.' in video_file.filename else 'mp4'
                filename = f"{material_id}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                video_file.save(filepath)
                file_path = filepath
                print(f"[双轨制] 原始视频已保存: {filepath}")
                
                # 设置 unified_path（本地FFmpeg转码输出路径）
                unified_filename = f"{material_id}_unified.mp4"
                unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
                
                # 启动本地FFmpeg转码（异步）
                task_id = f"transcode_{material_id}"
                app = current_app._get_current_object()
                thread = threading.Thread(
                    target=async_transcode_task,
                    args=(task_id, material_id, filepath, unified_path, 'medium', app, user_id)
                )
                thread.daemon = True
                thread.start()
                print(f"[双轨制] 本地FFmpeg转码已启动: {material_id}")
        else:
            print(f"[双轨制] 没有上传原始视频文件，跳过本地FFmpeg转码")
        
        # 创建素材记录
        material = Material(
            id=material_id,
            user_id=user_id,
            shot_id=shot_id,
            type='video',
            original_name='local_video.mp4',
            file_path=file_path,
            unified_path=unified_path,
            thumbnail_path=thumbnail_path,
            duration=duration_str,
            duration_seconds=duration_seconds,
            is_local=True,
            local_material_id=material_id,
            width=int(width) if width else None,
            height=int(height) if height else None,
            file_size=int(file_size) if file_size else None
        )
        db.session.add(material)
        db.session.commit()
        
        # 清除用户的旧渲染结果
        from utils.cleanup import clear_all_user_renders
        clear_all_user_renders(user_id)
        
        return jsonify({
            'id': material_id,
            'type': 'video',
            'url': 'local',  # 本地素材没有服务器URL
            'thumbnail': f'/uploads/thumbnails/{thumbnail_filename}' if thumbnail_path else None,
            'duration': duration_str,
            'originalName': 'local_video.mp4',
            'is_local': True,
            'transcode_status': 'processing' if unified_path else 'completed',
            'transcode_task_id': f"transcode_{material_id}" if unified_path else None,
            'message': '素材元数据已保存，本地FFmpeg转码中' if unified_path else '素材元数据已保存（客户端本地渲染）'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
