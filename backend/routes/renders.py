"""
Render result routes
"""
from flask import Blueprint, request, jsonify, send_from_directory
import os
import uuid
import threading
import json
from models import User, Render, Material
from extensions import db, render_tasks
from config import RENDERS_FOLDER
from utils import fast_concat_videos

renders_bp = Blueprint('renders', __name__, url_prefix='/api')


def fast_concat_task(task_id, combo_id, unified_files, output_path):
    """Fast concat using -c copy"""
    render_tasks[task_id] = {
        'id': task_id,
        'combo_id': combo_id,
        'status': 'processing',
        'progress': 0,
        'output_path': output_path
    }
    
    try:
        render_tasks[task_id]['progress'] = 50
        success = fast_concat_videos(unified_files, output_path)
        
        if success and os.path.exists(output_path):
            render_tasks[task_id]['progress'] = 100
            render_tasks[task_id]['status'] = 'completed'
            render_tasks[task_id]['video_url'] = f'/renders/{os.path.basename(output_path)}'
        else:
            render_tasks[task_id]['status'] = 'failed'
            render_tasks[task_id]['error'] = 'Concat failed'
            
    except Exception as e:
        render_tasks[task_id]['status'] = 'failed'
        render_tasks[task_id]['error'] = str(e)


@renders_bp.route('/renders', methods=['GET'])
def get_renders():
    """Get all renders for a user"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': '缺少user_id参数'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        renders = Render.query.filter_by(user_id=user_id).order_by(Render.combo_index).all()
        
        if not renders:
            return jsonify({'combinations': []})
        
        combinations = []
        for render in renders:
            file_exists = render.file_path and os.path.exists(render.file_path)
            
            try:
                material_ids = json.loads(render.material_ids)
            except:
                material_ids = []
            
            materials_data = []
            for mat_id in material_ids:
                material = Material.query.get(mat_id)
                if material and material.user_id == user_id:
                    materials_data.append({
                        'id': material.id,
                        'type': material.type,
                        'url': f'/uploads/{os.path.basename(material.file_path)}',
                        'thumbnail': f'/uploads/thumbnails/{os.path.basename(material.thumbnail_path)}',
                        'duration': material.duration,
                        'name': material.original_name
                    })
            
            combo_data = {
                'id': render.id,
                'index': render.combo_index,
                'materials': materials_data,
                'thumbnail': render.thumbnail,
                'duration': render.duration,
                'duration_seconds': render.duration_seconds,
                'tag': render.tag,
                'preview_status': 'completed' if file_exists else 'pending',
                'preview_url': f'/renders/{os.path.basename(render.file_path)}' if file_exists else None
            }
            combinations.append(combo_data)
        
        return jsonify({'combinations': combinations})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@renders_bp.route('/combinations/<combo_id>/render', methods=['POST'])
def render_combination_video(combo_id):
    """On-demand render preview video for a combination"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        user_id = parts[1]
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        render = Render.query.get(combo_id)
        if not render or render.user_id != user_id:
            return jsonify({'error': '组合不存在'}), 404
        
        # Check if there's already a completed render for this combo
        if render.file_path and os.path.exists(render.file_path):
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{os.path.basename(render.file_path)}'
            })
        
        # Check if there's an ongoing task
        for task_id, task in render_tasks.items():
            if task.get('combo_id') == combo_id and task['status'] == 'processing':
                return jsonify({
                    'status': 'processing',
                    'task_id': task_id,
                    'progress': task.get('progress', 0)
                })
        
        # Generate unique filename with timestamp to avoid conflicts
        import time
        timestamp = int(time.time())
        output_filename = f"render_{combo_id}_{timestamp}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        material_ids = json.loads(render.material_ids)
        material_files = []
        
        for mat_id in material_ids:
            material = Material.query.get(mat_id)
            if material and material.user_id == user_id and material.unified_path and os.path.exists(material.unified_path):
                material_files.append(material.unified_path)
        
        if not material_files:
            return jsonify({'error': '素材文件不存在'}), 404
        
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        thread = threading.Thread(
            target=fast_concat_task,
            args=(task_id, combo_id, material_files, output_path)
        )
        thread.daemon = True
        thread.start()
        
        # Update render record with new file path
        render.file_path = output_path
        render.status = 'processing'
        db.session.commit()
        
        return jsonify({
            'status': 'processing',
            'task_id': task_id,
            'progress': 0
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@renders_bp.route('/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Get render task status"""
    if task_id not in render_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = render_tasks[task_id]
    response = {
        'task_id': task_id,
        'status': task['status'],
        'progress': task.get('progress', 0)
    }
    
    if task['status'] == 'completed':
        response['video_url'] = task.get('video_url')
    elif task['status'] == 'failed':
        response['error'] = task.get('error')
    
    return jsonify(response)


@renders_bp.route('/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """Download video"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        render = Render.query.get(combo_id)
        if not render or not render.file_path:
            return jsonify({
                'status': 'failed',
                'error': '视频文件不存在，请重新生成'
            }), 404
        
        output_path = render.file_path
        output_filename = os.path.basename(output_path)
        
        if not os.path.exists(output_path):
            return jsonify({
                'status': 'failed',
                'error': '视频文件不存在，请重新生成'
            }), 404
        
        data = request.json or {}
        download_mode = data.get('mode', 'proxy')
        
        if download_mode == 'redirect':
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}',
                'download_url': f'/api/download/file?path={output_filename}&name=mixcut_{combo_id}.mp4',
                'mode': 'redirect'
            })
        else:
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}',
                'mode': 'proxy'
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@renders_bp.route('/download/file', methods=['GET'])
def download_file():
    """Direct file download"""
    try:
        file_path = request.args.get('path')
        download_name = request.args.get('name', 'video.mp4')
        
        if not file_path:
            return jsonify({'error': '没有指定文件路径'}), 400
        
        full_path = os.path.join(RENDERS_FOLDER, os.path.basename(file_path))
        
        if not os.path.exists(full_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_from_directory(
            RENDERS_FOLDER,
            os.path.basename(file_path),
            as_attachment=True,
            download_name=download_name
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
