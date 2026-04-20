"""
Video generation routes - 优化版本
"""
from flask import Blueprint, request, jsonify
from itertools import product
import json
import os
import glob
import threading
import time
from models import User, Render, Material
from extensions import db
from config import RENDERS_FOLDER
from utils import format_duration, calculate_uniqueness_tag, clear_user_renders

generate_bp = Blueprint('generate', __name__, url_prefix='/api')


def clear_user_render_files(user_id):
    """Clear all render files for a user - 异步执行，不阻塞主线程"""
    try:
        pattern = os.path.join(RENDERS_FOLDER, f'render_combo_{user_id}_*.mp4')
        files = glob.glob(pattern)
        for filepath in files:
            try:
                os.remove(filepath)
            except:
                pass
        print(f"[Cleanup] Cleared {len(files)} render files for user {user_id}")
    except Exception as e:
        print(f"[Cleanup] Error: {e}")


def is_material_ready(mat):
    """Check if a material is ready for video generation"""
    if mat.unified_path and os.path.exists(mat.unified_path):
        return True, 'completed'
    
    from extensions import transcode_tasks
    task_id = f"transcode_{mat.id}"
    if task_id in transcode_tasks:
        task = transcode_tasks[task_id]
        if task['status'] == 'processing':
            return False, 'processing'
        elif task['status'] == 'completed':
            fresh_mat = Material.query.get(mat.id)
            if fresh_mat and fresh_mat.unified_path and os.path.exists(fresh_mat.unified_path):
                return True, 'completed'
            return False, 'processing'
        else:
            return False, 'failed'
    
    return False, 'pending'


def generate_combinations_async(user_id, material_lists, shots_data, total_possible):
    """异步生成组合详情 - 后台计算时长并更新数据库"""
    def async_task():
        try:
            print(f"[Async Generate] Starting for user {user_id}, total combos: {total_possible}")
            start_time = time.time()
            
            all_combos = list(product(*material_lists))
            limit = min(total_possible, 1000)
            
            # 批量获取或计算时长
            duration_cache = {}
            
            for combo_index, combo in enumerate(all_combos[:limit]):
                combo_id = f"combo_{user_id}_{combo_index}"
                
                # 计算总时长（使用缓存）
                total_duration = 0
                for m in combo:
                    mat_id = m['id']
                    if mat_id not in duration_cache:
                        # 优先使用数据库中的duration_seconds
                        if m.get('duration_seconds'):
                            duration_cache[mat_id] = m['duration_seconds']
                        elif m['type'] == 'image':
                            duration_cache[mat_id] = 3.0
                        else:
                            #  fallback：从文件读取（应该很少发生）
                            from utils import get_video_duration
                            duration_cache[mat_id] = get_video_duration(m['unified_path'])
                    total_duration += duration_cache[mat_id]
                
                # 更新数据库中的Render记录
                render = Render.query.get(combo_id)
                if render:
                    render.duration = format_duration(total_duration)
                    render.duration_seconds = total_duration
                    render.tag = calculate_uniqueness_tag(combo)
                
                # 每10个提交一次，减少数据库压力
                if combo_index % 10 == 0:
                    db.session.commit()
            
            # 最后提交剩余
            db.session.commit()
            
            elapsed = time.time() - start_time
            print(f"[Async Generate] Completed in {elapsed:.2f}s for user {user_id}")
            
        except Exception as e:
            print(f"[Async Generate] Error: {e}")
            db.session.rollback()
    
    # 启动后台线程
    thread = threading.Thread(target=async_task)
    thread.daemon = True
    thread.start()


@generate_bp.route('/generate', methods=['POST'])
def generate_combinations():
    """Generate combinations metadata - 优化版本，快速返回"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': '缺少user_id'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 检查转码状态
        transcoding_materials = []
        for shot in user.shots:
            for mat in shot.materials:
                is_ready, status = is_material_ready(mat)
                if not is_ready and status == 'processing':
                    transcoding_materials.append({
                        'id': mat.id,
                        'name': mat.original_name,
                        'shot_name': shot.name
                    })
        
        if transcoding_materials:
            return jsonify({
                'error': '部分素材正在转码中，请等待转码完成后再生成',
                'transcoding_materials': transcoding_materials,
                'code': 'TRANSCODING_IN_PROGRESS'
            }), 400
        
        # 异步清理旧文件（不阻塞）
        cleanup_thread = threading.Thread(target=clear_user_render_files, args=(user_id,))
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        # 清理数据库记录（批量删除）
        Render.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        
        shots = sorted([s for s in user.shots if s.materials], key=lambda x: x.sequence)
        
        if not shots:
            return jsonify({'error': '没有镜头包含素材'}), 400
        
        # 准备素材数据（使用duration_seconds避免文件IO）
        material_lists = []
        shots_data = []
        for shot in shots:
            mat_dicts = [{
                'id': mat.id,
                'type': mat.type,
                'unified_path': mat.unified_path,
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'duration_seconds': mat.duration_seconds or (3.0 if mat.type == 'image' else 0),
                'name': mat.original_name
            } for mat in shot.materials if mat.unified_path and os.path.exists(mat.unified_path)]
            if mat_dicts:
                material_lists.append(mat_dicts)
                shots_data.append({'name': shot.name, 'materials': len(mat_dicts)})
        
        if not material_lists:
            return jsonify({'error': '没有可用的素材'}), 400
        
        # 计算组合数
        total_possible = 1
        for mat_list in material_lists:
            total_possible *= len(mat_list)
        
        limit = min(total_possible, 1000)
        
        # 快速生成组合（不计算时长，使用默认值）
        all_combos = list(product(*material_lists))
        combinations = []
        
        # 批量准备Render对象
        renders_to_add = []
        
        for combo_index, combo in enumerate(all_combos[:limit]):
            combo_id = f"combo_{user_id}_{combo_index}"
            
            # 使用默认时长（异步任务会更新准确值）
            default_duration = sum(m.get('duration_seconds', 3.0) for m in combo)
            
            material_ids = json.dumps([m['id'] for m in combo])
            render = Render(
                id=combo_id,
                user_id=user_id,
                combo_index=combo_index,
                material_ids=material_ids,
                tag='计算中...',  # 异步更新
                duration=format_duration(default_duration),
                duration_seconds=default_duration,
                thumbnail=combo[0]['thumbnail'] if combo else '',
                file_path=None,
                status='pending'
            )
            renders_to_add.append(render)
            
            combo_data = {
                'id': combo_id,
                'index': combo_index,
                'materials': list(combo),
                'thumbnail': combo[0]['thumbnail'] if combo else '',
                'duration': format_duration(default_duration),
                'duration_seconds': default_duration,
                'tag': '计算中...',
                'preview_status': 'pending',
                'preview_url': None
            }
            combinations.append(combo_data)
        
        # 批量插入数据库（一次性）
        db.session.bulk_save_objects(renders_to_add)
        db.session.commit()
        
        # 启动异步任务计算准确时长和标签
        generate_combinations_async(user_id, material_lists, shots_data, total_possible)
        
        print(f"[Generate] Quick response: {len(combinations)} combos in {(time.time() - request.start_time):.3f}s")
        
        return jsonify({
            'total': len(combinations),
            'total_possible': total_possible,
            'combinations': combinations,
            'async_processing': True
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"[Generate] Error: {e}")
        return jsonify({'error': str(e)}), 500


# 添加请求计时中间件
@generate_bp.before_request
def before_request():
    request.start_time = time.time()
