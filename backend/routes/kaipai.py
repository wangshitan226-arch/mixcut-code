"""
Kaipai (开拍式) editing routes
网感剪辑API路由 - 文字快剪功能
"""
from flask import Blueprint, request, jsonify
import uuid
import json
import os
import subprocess
import threading
import logging
from datetime import datetime
from models import Render, KaipaiEdit
from extensions import db
from utils.oss import oss_client
from utils.kaipai_asr import create_asr_task, get_asr_task, process_asr_task

logger = logging.getLogger(__name__)

kaipai_bp = Blueprint('kaipai', __name__, url_prefix='/api')

# 渲染任务存储
render_tasks = {}


@kaipai_bp.route('/renders/<render_id>/kaipai/edit', methods=['POST'])
def create_kaipai_edit(render_id):
    """创建新的开拍式剪辑任务"""
    try:
        render = Render.query.get(render_id)
        if not render:
            return jsonify({'error': 'Render not found'}), 404
        
        data = request.get_json(silent=True) or {}
        parent_id = data.get('parent_id')
        user_id = data.get('user_id')
        
        # 计算版本号
        if parent_id:
            parent = KaipaiEdit.query.get(parent_id)
            version = parent.version + 1 if parent else 1
        else:
            existing = KaipaiEdit.query.filter_by(render_id=render_id).count()
            version = existing + 1
        
        # 检查是否有OSS URL
        video_url = render.oss_url
        if not video_url:
            return jsonify({'error': '视频尚未上传到OSS，请稍后再试', 'code': 'NO_OSS_URL'}), 400
    
        edit = KaipaiEdit(
            id=str(uuid.uuid4()),
            user_id=user_id or render.user_id,
            render_id=render_id,
            parent_id=parent_id,
            version=version,
            title=data.get('title', f'草稿 {version}'),
            original_video_url=video_url,
            status='draft'
        )
        
        db.session.add(edit)
        db.session.commit()
        
        return jsonify({
            'edit_id': edit.id,
            'version': version,
            'status': 'draft',
            'video_url': video_url
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'创建剪辑任务失败: {str(e)}'}), 500


@kaipai_bp.route('/kaipai/<edit_id>/transcribe', methods=['POST'])
def start_transcription(edit_id):
    """启动语音识别"""
    logger.info(f"启动语音识别请求: {edit_id}")
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        logger.warning(f"草稿不存在: {edit_id}")
        return jsonify({'error': 'Edit not found'}), 404
    
    # 检查是否已经有ASR结果
    if edit.asr_result:
        logger.info(f"使用缓存的ASR结果: {edit_id}")
        return jsonify({
            'edit_id': edit_id,
            'status': 'completed',
            'result': json.loads(edit.asr_result),
            'from_cache': True
        })
    
    # 获取视频URL
    video_url = edit.original_video_url
    if not video_url:
        logger.error(f"视频URL不存在: {edit_id}")
        return jsonify({'error': '视频URL不存在'}), 400
    
    logger.info(f"启动ASR任务: {edit_id}, video_url: {video_url[:100]}...")
    
    # 创建并启动ASR任务
    create_asr_task(edit_id, video_url)
    process_asr_task(edit_id, video_url, edit_id, edit.user_id)
    
    edit.status = 'transcribing'
    edit.segment_status = 'processing'
    db.session.commit()
    
    logger.info(f"ASR任务已启动: {edit_id}")
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'transcribing'
    })


@kaipai_bp.route('/kaipai/<edit_id>/transcribe/status', methods=['GET'])
def get_transcription_status(edit_id):
    """获取语音识别状态"""
    logger.info(f"获取语音识别状态: {edit_id}")
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        logger.warning(f"草稿不存在: {edit_id}")
        return jsonify({'error': 'Edit not found'}), 404
    
    # 检查是否已经有ASR结果（数据库缓存）
    if edit.asr_result:
        logger.info(f"从数据库缓存获取ASR结果: {edit_id}, segment_status: {edit.segment_status}")
        
        # 如果segment还在处理中或已完成但未保存到数据库，检查内存中的任务状态
        task = get_asr_task(edit_id)
        if task:
            logger.info(f"内存任务状态: segment_status={task.get('segment_status')}, has_segment_urls={bool(task.get('segment_urls'))}")
            # 更新数据库中的segment状态和URL
            if task.get('segment_urls') and not edit.segment_urls:
                edit.segment_urls = json.dumps(task['segment_urls'], ensure_ascii=False)
                edit.segment_status = 'completed'
                db.session.commit()
                logger.info(f"更新数据库segment_urls: {len(task['segment_urls'])} 个片段")
            elif task.get('segment_status') and edit.segment_status != task.get('segment_status'):
                edit.segment_status = task.get('segment_status')
                db.session.commit()
        
        response = {
            'edit_id': edit_id,
            'status': 'completed',
            'result': json.loads(edit.asr_result),
            'from_cache': True,
            'segment_status': edit.segment_status
        }
        
        # 如果segment失败，尝试从内存任务获取错误信息
        if edit.segment_status == 'failed':
            task = get_asr_task(edit_id)
            if task and task.get('segment_error'):
                response['segment_error'] = task.get('segment_error')
        
        return jsonify(response)
    
    # 从内存中获取ASR任务状态
    task = get_asr_task(edit_id)
    if not task:
        return jsonify({'error': 'ASR task not found'}), 404
    
    # 如果识别完成，保存到数据库并更新状态
    if task['status'] == 'completed' and edit.status == 'transcribing':
        edit.status = 'draft'
        # 保存ASR结果到数据库
        if task.get('result'):
            edit.asr_result = json.dumps(task['result'], ensure_ascii=False)
        # 保存视频片段URL（如果已完成）
        if task.get('segment_urls'):
            edit.segment_urls = json.dumps(task['segment_urls'], ensure_ascii=False)
            edit.segment_status = 'completed'
        else:
            # 使用任务中的segment_status
            edit.segment_status = task.get('segment_status', 'processing')
        db.session.commit()
    
    response = {
        'edit_id': edit_id,
        'status': task['status'],
        'segment_status': task.get('segment_status', edit.segment_status),
        'result': task.get('result'),
        'error': task.get('error')
    }
    
    # 如果视频分割失败，返回错误信息
    if task.get('segment_status') == 'failed' and task.get('segment_error'):
        response['segment_error'] = task.get('segment_error')
    
    return jsonify(response)


@kaipai_bp.route('/kaipai/<edit_id>', methods=['GET'])
def get_kaipai_edit(edit_id):
    """获取剪辑任务详情"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    return jsonify(edit.to_dict())


@kaipai_bp.route('/kaipai/<edit_id>', methods=['PUT'])
def update_kaipai_edit(edit_id):
    """保存编辑参数"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.get_json(silent=True) or {}
    
    # 获取当前的编辑参数和历史
    current_params = json.loads(edit.edit_params) if edit.edit_params else {}
    edit_history = json.loads(edit.edit_history) if edit.edit_history else []
    
    # 记录编辑操作到历史
    action = {
        'timestamp': datetime.now().isoformat(),
        'action': 'update',
        'removed_segments': data.get('removed_segments', []),
        'previous_segments': current_params.get('removed_segments', [])
    }
    edit_history.append(action)
    
    # 更新编辑参数
    current_params.update({
        'removed_segments': data.get('removed_segments', []),
        'subtitle_style': data.get('subtitle_style', {}),
        'bgm': data.get('bgm', {}),
        'template': data.get('template', {})
    })
    
    edit.edit_params = json.dumps(current_params, ensure_ascii=False)
    edit.edit_history = json.dumps(edit_history, ensure_ascii=False)
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'saved',
        'params': current_params,
        'history_count': len(edit_history)
    })


@kaipai_bp.route('/kaipai/<edit_id>/undo', methods=['POST'])
def undo_kaipai_edit(edit_id):
    """撤回上一次编辑"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    edit_history = json.loads(edit.edit_history) if edit.edit_history else []
    current_params = json.loads(edit.edit_params) if edit.edit_params else {}
    
    if not edit_history:
        return jsonify({'error': '没有可撤回的操作'}), 400
    
    # 移除最后一次操作
    last_action = edit_history.pop()
    
    # 恢复之前的segments状态
    if last_action.get('previous_segments') is not None:
        current_params['removed_segments'] = last_action['previous_segments']
    
    edit.edit_params = json.dumps(current_params, ensure_ascii=False)
    edit.edit_history = json.dumps(edit_history, ensure_ascii=False)
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'undone',
        'params': current_params,
        'history_count': len(edit_history)
    })


@kaipai_bp.route('/kaipai/<edit_id>/subtitle', methods=['PUT'])
def update_subtitle(edit_id):
    """更新片段字幕文本"""
    logger.info(f"更新字幕请求: {edit_id}")
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        logger.warning(f"草稿不存在: {edit_id}")
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.get_json(silent=True) or {}
    segment_id = data.get('segment_id')
    new_text = data.get('text')
    
    if not segment_id or new_text is None:
        return jsonify({'error': '缺少segment_id或text参数'}), 400
    
    # 获取当前ASR结果
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    sentences = asr_result.get('sentences', [])
    
    # 查找并更新对应片段
    updated = False
    for sentence in sentences:
        if sentence.get('id') == segment_id:
            old_text = sentence.get('text', '')
            sentence['text'] = new_text
            updated = True
            logger.info(f"更新字幕: {segment_id}, '{old_text}' -> '{new_text}'")
            break
    
    if not updated:
        return jsonify({'error': '片段未找到'}), 404
    
    # 保存更新后的ASR结果
    edit.asr_result = json.dumps(asr_result, ensure_ascii=False)
    
    # 记录编辑历史
    edit_history = json.loads(edit.edit_history) if edit.edit_history else []
    edit_history.append({
        'timestamp': datetime.now().isoformat(),
        'action': 'edit_subtitle',
        'segment_id': segment_id,
        'new_text': new_text
    })
    edit.edit_history = json.dumps(edit_history, ensure_ascii=False)
    
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'segment_id': segment_id,
        'text': new_text,
        'status': 'updated'
    })


@kaipai_bp.route('/kaipai/<edit_id>/render', methods=['POST'])
def start_render(edit_id):
    """启动视频渲染（裁剪）"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 获取编辑参数
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    
    if not removed_segments:
        return jsonify({'error': '没有要删除的片段'}), 400
    
    # 获取所有需要在异步线程中使用的数据（避免session问题）
    video_url = edit.original_video_url
    user_id = edit.user_id
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    
    # 启动异步渲染任务
    task_id = str(uuid.uuid4())
    render_tasks[task_id] = {
        'status': 'processing',
        'progress': 0,
        'output_url': None,
        'error': None
    }
    
    # 获取当前应用实例（用于创建应用上下文）
    from flask import current_app
    app = current_app._get_current_object()
    
    # 异步执行视频裁剪
    def render_video():
        with app.app_context():
            try:
                render_tasks[task_id]['progress'] = 10
                
                # 计算保留的时间段（反向思考：删除selected的segments）
                all_segments = asr_result.get('sentences', [])
                
                # 获取要删除的时间段
                removed_times = [(s['beginTime'], s['endTime']) for s in removed_segments]
                
                # 计算保留的时间段
                keep_segments = []
                video_duration = asr_result.get('videoInfo', {}).get('duration', 0) * 1000
                
                current_time = 0
                for seg in all_segments:
                    seg_start = seg['beginTime']
                    seg_end = seg['endTime']
                    
                    # 检查这个片段是否被选中删除
                    is_removed = any(r[0] <= seg_start and r[1] >= seg_end for r in removed_times)
                    
                    if not is_removed:
                        keep_segments.append((seg_start, seg_end))
                
                render_tasks[task_id]['progress'] = 30
                
                # 使用ffmpeg裁剪视频
                output_filename = f"kaipai_render_{edit_id}_{int(datetime.now().timestamp())}.mp4"
                output_path = os.path.join('renders', output_filename)
                
                # 构建ffmpeg命令 - 使用复杂滤镜拼接多个时间段
                if len(keep_segments) == 0:
                    raise Exception('没有可保留的视频片段')
                
                # 下载原始视频到本地
                local_video_path = os.path.join('uploads', f'temp_{edit_id}.mp4')
                if video_url.startswith('http'):
                    import requests
                    response = requests.get(video_url)
                    with open(local_video_path, 'wb') as f:
                        f.write(response.content)
                else:
                    local_video_path = video_url.lstrip('/')
                
                render_tasks[task_id]['progress'] = 50
                
                # 构建ffmpeg filter_complex
                filter_parts = []
                concat_parts = []
                
                for i, (start, end) in enumerate(keep_segments):
                    start_sec = start / 1000
                    duration = (end - start) / 1000
                    filter_parts.append(f"[0:v]trim=start={start_sec}:duration={duration},setpts=PTS-STARTPTS[v{i}];")
                    filter_parts.append(f"[0:a]atrim=start={start_sec}:duration={duration},asetpts=PTS-STARTPTS[a{i}];")
                    concat_parts.append(f"[v{i}][a{i}]")
                
                filter_complex = ''.join(filter_parts) + ''.join(concat_parts) + f"concat=n={len(keep_segments)}:v=1:a=1[outv][outa]"
                
                cmd = [
                    'ffmpeg', '-y', '-i', local_video_path,
                    '-filter_complex', filter_complex,
                    '-map', '[outv]', '-map', '[outa]',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k',
                    output_path
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                render_tasks[task_id]['progress'] = 80
                
                # 上传到OSS
                oss_url = oss_client.upload_render(output_path, edit_id, user_id)
                
                render_tasks[task_id]['progress'] = 100
                render_tasks[task_id]['status'] = 'completed'
                render_tasks[task_id]['output_url'] = oss_url
                
                # 更新数据库（在新session中）
                from extensions import db
                from models import KaipaiEdit
                with db.session.begin():
                    edit_update = KaipaiEdit.query.get(edit_id)
                    if edit_update:
                        edit_update.output_video_url = oss_url
                        edit_update.status = 'completed'
                
                # 清理临时文件
                if os.path.exists(local_video_path) and 'temp_' in local_video_path:
                    os.remove(local_video_path)
                
            except Exception as e:
                render_tasks[task_id]['status'] = 'failed'
                render_tasks[task_id]['error'] = str(e)
                # 更新数据库状态为失败
                from extensions import db
                from models import KaipaiEdit
                with db.session.begin():
                    edit_update = KaipaiEdit.query.get(edit_id)
                    if edit_update:
                        edit_update.status = 'failed'
    
    thread = threading.Thread(target=render_video)
    thread.daemon = True
    thread.start()
    
    edit.status = 'processing'
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'processing',
        'task_id': task_id
    })


@kaipai_bp.route('/kaipai/render/<task_id>/status', methods=['GET'])
def get_render_status(task_id):
    """获取渲染任务状态"""
    task = render_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({
        'task_id': task_id,
        'status': task['status'],
        'progress': task['progress'],
        'output_url': task.get('output_url'),
        'error': task.get('error')
    })


@kaipai_bp.route('/kaipai/<edit_id>/preview', methods=['GET'])
def get_preview_video(edit_id):
    """获取预览视频（使用原始视频，前端根据时间戳控制播放）"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 返回原始视频URL，前端根据removed_segments来跳过被删除的部分
    return jsonify({
        'edit_id': edit_id,
        'video_url': edit.original_video_url,
        'preview_mode': True
    })


@kaipai_bp.route('/kaipai/<edit_id>/preview/rendered', methods=['POST'])
def render_preview_video(edit_id):
    """渲染预览视频（生成实际裁剪后的视频用于预览）"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 复用render逻辑，但生成低质量预览版本
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    
    if not removed_segments:
        # 没有删除任何片段，直接返回原视频
        return jsonify({
            'edit_id': edit_id,
            'video_url': edit.original_video_url,
            'preview_rendered': False
        })
    
    # 获取所有需要在异步线程中使用的数据
    video_url = edit.original_video_url
    user_id = edit.user_id
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    
    # 启动预览渲染任务（低质量，快速）
    task_id = str(uuid.uuid4())
    render_tasks[task_id] = {
        'status': 'processing',
        'progress': 0,
        'output_url': None,
        'error': None,
        'is_preview': True
    }
    
    # 获取当前应用实例
    from flask import current_app
    app = current_app._get_current_object()
    
    def render_preview():
        with app.app_context():
            try:
                render_tasks[task_id]['progress'] = 10
                
                all_segments = asr_result.get('sentences', [])
                
                removed_times = [(s['beginTime'], s['endTime']) for s in removed_segments]
                
                keep_segments = []
                for seg in all_segments:
                    seg_start = seg['beginTime']
                    seg_end = seg['endTime']
                    is_removed = any(r[0] <= seg_start and r[1] >= seg_end for r in removed_times)
                    if not is_removed:
                        keep_segments.append((seg_start, seg_end))
                
                render_tasks[task_id]['progress'] = 30
                
                # 下载原始视频
                local_video_path = os.path.join('uploads', f'temp_preview_{edit_id}.mp4')
                if video_url.startswith('http'):
                    import requests
                    response = requests.get(video_url)
                    with open(local_video_path, 'wb') as f:
                        f.write(response.content)
                else:
                    local_video_path = video_url.lstrip('/')
                
                render_tasks[task_id]['progress'] = 40
                
                # 生成预览视频（低质量，快速）
                output_filename = f"kaipai_preview_{edit_id}_{int(datetime.now().timestamp())}.mp4"
                output_path = os.path.join('renders', output_filename)
                
                # 构建ffmpeg命令 - 预览版使用更低质量
                filter_parts = []
                concat_parts = []
                
                for i, (start, end) in enumerate(keep_segments):
                    start_sec = start / 1000
                    duration = (end - start) / 1000
                    filter_parts.append(f"[0:v]trim=start={start_sec}:duration={duration},setpts=PTS-STARTPTS[v{i}];")
                    filter_parts.append(f"[0:a]atrim=start={start_sec}:duration={duration},asetpts=PTS-STARTPTS[a{i}];")
                    concat_parts.append(f"[v{i}][a{i}]")
                
                filter_complex = ''.join(filter_parts) + ''.join(concat_parts) + f"concat=n={len(keep_segments)}:v=1:a=1[outv][outa]"
                
                # 预览版使用更低分辨率和码率
                cmd = [
                    'ffmpeg', '-y', '-i', local_video_path,
                    '-filter_complex', filter_complex,
                    '-map', '[outv]', '-map', '[outa]',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                    '-vf', 'scale=480:-2',  # 降低分辨率
                    '-c:a', 'aac', '-b:a', '96k',
                    output_path
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                render_tasks[task_id]['progress'] = 80
                
                # 上传到OSS
                oss_url = oss_client.upload_render(output_path, edit_id, user_id)
                
                render_tasks[task_id]['progress'] = 100
                render_tasks[task_id]['status'] = 'completed'
                render_tasks[task_id]['output_url'] = oss_url
                
                # 清理临时文件
                if os.path.exists(local_video_path) and 'temp_' in local_video_path:
                    os.remove(local_video_path)
                
            except Exception as e:
                render_tasks[task_id]['status'] = 'failed'
                render_tasks[task_id]['error'] = str(e)
    
    thread = threading.Thread(target=render_preview)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'processing',
        'task_id': task_id
    })


@kaipai_bp.route('/renders/<render_id>/kaipai/versions', methods=['GET'])
def get_kaipai_versions(render_id):
    """获取某个render的所有剪辑版本"""
    render = Render.query.get(render_id)
    if not render:
        return jsonify({'error': 'Render not found'}), 404
    
    versions = KaipaiEdit.query.filter_by(render_id=render_id).order_by(KaipaiEdit.version).all()
    
    return jsonify({
        'render_id': render_id,
        'versions': [v.to_dict() for v in versions]
    })


@kaipai_bp.route('/users/<user_id>/kaipai/drafts', methods=['GET'])
def get_user_drafts(user_id):
    """获取用户的所有草稿（用于首页显示）"""
    drafts = KaipaiEdit.query.filter_by(user_id=user_id).order_by(KaipaiEdit.updated_at.desc()).all()
    
    return jsonify({
        'user_id': user_id,
        'drafts': [d.to_dict() for d in drafts]
    })


@kaipai_bp.route('/kaipai/<edit_id>/title', methods=['PUT'])
def update_draft_title(edit_id):
    """更新草稿标题"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.get_json(silent=True) or {}
    title = data.get('title')
    
    if title:
        edit.title = title
        db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'title': edit.title
    })


@kaipai_bp.route('/kaipai/<edit_id>', methods=['DELETE'])
def delete_kaipai_edit(edit_id):
    """删除草稿"""
    try:
        logger.info(f"删除草稿请求: {edit_id}")
        edit = KaipaiEdit.query.get(edit_id)
        if not edit:
            logger.warning(f"草稿不存在: {edit_id}")
            return jsonify({'error': 'Edit not found'}), 404
        
        # 删除OSS上的视频片段
        if edit.segment_urls:
            try:
                segment_urls = json.loads(edit.segment_urls)
                logger.info(f"删除 {len(segment_urls)} 个OSS片段")
                for segment in segment_urls:
                    url = segment.get('url', '')
                    if url and 'aliyuncs.com' in url:
                        # 从URL中提取OSS key
                        # URL格式: https://bucket.endpoint/key
                        key = url.split('.aliyuncs.com/')[-1]
                        if key:
                            try:
                                oss_client.bucket.delete_object(key)
                                logger.info(f"删除OSS片段: {key}")
                            except Exception as e:
                                logger.error(f"删除OSS片段失败 {key}: {e}")
            except Exception as e:
                logger.error(f"解析segment_urls失败: {e}")
        
        # 删除OSS上的导出视频
        if edit.output_video_url and 'aliyuncs.com' in edit.output_video_url:
            try:
                key = edit.output_video_url.split('.aliyuncs.com/')[-1]
                if key:
                    oss_client.bucket.delete_object(key)
                    logger.info(f"删除OSS导出视频: {key}")
            except Exception as e:
                logger.error(f"删除OSS导出视频失败: {e}")
        
        db.session.delete(edit)
        db.session.commit()
        logger.info(f"草稿删除成功: {edit_id}")
        
        return jsonify({
            'edit_id': edit_id,
            'status': 'deleted'
        })
    except Exception as e:
        logger.error(f"删除草稿失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'删除失败: {str(e)}'}), 500
