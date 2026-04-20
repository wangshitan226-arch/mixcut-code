"""
Shot management routes
"""
from flask import Blueprint, request, jsonify
import os
from models import User, Shot
from extensions import db, transcode_tasks

shots_bp = Blueprint('shots', __name__, url_prefix='/api')


@shots_bp.route('/shots', methods=['GET'])
def get_shots():
    """Get all shots for a user"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': '缺少user_id参数'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        shots_data = []
        for shot in sorted(user.shots, key=lambda x: x.sequence):
            materials_data = []
            for mat in shot.materials:
                # Determine transcode status
                task_id = f"transcode_{mat.id}"
                
                # 优先检查内存中的任务状态（最快）
                if task_id in transcode_tasks:
                    task = transcode_tasks[task_id]
                    if task['status'] == 'completed':
                        transcode_status = 'completed'
                        transcode_task_id = task_id
                    elif task['status'] == 'processing':
                        transcode_status = 'processing'
                        transcode_task_id = task_id
                    else:  # failed
                        transcode_status = 'failed'
                        transcode_task_id = task_id
                # 其次检查数据库和文件系统
                elif mat.unified_path and os.path.exists(mat.unified_path):
                    transcode_status = 'completed'
                    transcode_task_id = None
                else:
                    transcode_status = 'pending'
                    transcode_task_id = None
                
                materials_data.append({
                    'id': mat.id,
                    'type': mat.type,
                    'url': f'/uploads/{os.path.basename(mat.file_path)}',
                    'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                    'duration': mat.duration,
                    'name': mat.original_name,
                    'transcode_status': transcode_status,
                    'transcode_task_id': transcode_task_id
                })
            
            shots_data.append({
                'id': shot.id,
                'name': shot.name,
                'sequence': shot.sequence,
                'materials': materials_data
            })
        
        return jsonify({'shots': shots_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@shots_bp.route('/shots', methods=['POST'])
def create_shot():
    """Create a new shot"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': '缺少user_id'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        shot_count = len(user.shots)
        shot = Shot(
            user_id=user_id,
            name=data.get('name', f'镜头{shot_count + 1}'),
            sequence=shot_count
        )
        db.session.add(shot)
        db.session.commit()
        
        return jsonify({
            'id': shot.id,
            'name': shot.name,
            'sequence': shot.sequence,
            'materials': []
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@shots_bp.route('/shots/<int:shot_id>', methods=['DELETE'])
def delete_shot(shot_id):
    """Delete a shot"""
    try:
        shot = Shot.query.get_or_404(shot_id)
        
        for material in shot.materials:
            for path in [material.file_path, material.unified_path, material.thumbnail_path]:
                if path and os.path.exists(path):
                    os.remove(path)
        
        db.session.delete(shot)
        db.session.commit()
        
        return jsonify({'message': '镜头已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
