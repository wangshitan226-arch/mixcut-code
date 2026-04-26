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
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import Render, KaipaiEdit, Material
from extensions import db
from utils.oss import oss_client
from utils.kaipai_asr import create_asr_task, get_asr_task, process_asr_task
from config import USE_ICE_DIRECT_CROP

logger = logging.getLogger(__name__)

kaipai_bp = Blueprint('kaipai', __name__, url_prefix='/api')

# 渲染任务存储（使用线程锁保护）
render_tasks = {}
render_tasks_lock = threading.Lock()

# 任务队列限制（最大并发数）
MAX_CONCURRENT_RENDERS = 3
render_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RENDERS)

# 全局计数器用于唯一文件名
_file_counter = 0
_file_counter_lock = threading.Lock()

def get_unique_filename(prefix='temp'):
    """生成唯一的文件名，包含时间戳、计数器和随机UUID"""
    global _file_counter
    with _file_counter_lock:
        _file_counter += 1
        counter = _file_counter
    timestamp = int(time.time() * 1000)
    random_id = uuid.uuid4().hex[:12]
    return f"{prefix}_{timestamp}_{counter}_{random_id}"


def get_video_duration(video_path):
    """使用ffprobe获取视频实际时长（毫秒）"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            duration_sec = float(result.stdout.strip())
            return int(duration_sec * 1000)
    except Exception as e:
        logger.error(f"获取视频时长失败: {e}")
    return None


def merge_overlapping_ranges(ranges):
    """合并重叠的时间段"""
    if not ranges:
        return []
    
    # 按开始时间排序
    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    merged = [sorted_ranges[0]]
    
    for current in sorted_ranges[1:]:
        last = merged[-1]
        # 如果当前段与上一段重叠或相邻（间隔小于100ms）
        if current[0] <= last[1] + 100:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)
    
    return merged


def calculate_keep_segments(removed_segments, video_duration_ms, buffer_ms=150):
    """
    计算保留的时间段，处理重叠的删除段
    
    Args:
        removed_segments: 要删除的片段列表
        video_duration_ms: 视频总时长（毫秒）
        buffer_ms: 缓冲时间（毫秒），用于处理ASR时间戳不精确的问题
                  默认150ms，会向前和向后各扩展150ms
    """
    if not removed_segments:
        # 没有删除任何片段，保留全部
        return [(0, video_duration_ms)]
    
    # 获取要删除的时间段（添加缓冲时间）
    removed_times = []
    for s in removed_segments:
        # 向前和向后扩展缓冲时间，确保完全删除
        start = max(0, s['beginTime'] - buffer_ms)
        end = min(video_duration_ms, s['endTime'] + buffer_ms)
        removed_times.append((start, end))
    
    # 合并重叠的删除时间段
    removed_times_merged = merge_overlapping_ranges(removed_times)
    
    # 计算保留的时间段
    keep_segments = []
    current_time = 0
    
    for removed_start, removed_end in removed_times_merged:
        # 当前时间到删除开始时间之间的部分保留
        if current_time < removed_start:
            keep_segments.append((current_time, removed_start))
        # 跳到删除结束时间
        current_time = max(current_time, removed_end)
    
    # 保留最后一段（从最后一个删除点到视频结束）
    if current_time < video_duration_ms:
        keep_segments.append((current_time, video_duration_ms))
    
    return keep_segments


@kaipai_bp.route('/renders/<render_id>/kaipai/edit', methods=['POST'])
def create_kaipai_edit(render_id):
    """
    创建新的开拍式剪辑任务（双轨制版本）
    
    双轨制设计：
    - original_video_url: 视频①，服务器高质量视频URL（用于ASR/导出）
    - client_video_url:  视频②，客户端预览视频URL（用于编辑器预览播放）
    """
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
        
        # ========== 双轨制：获取视频URL ==========
        # 视频①：服务器高质量视频URL（优先使用前端传入的，其次是数据库中的）
        server_video_url = data.get('video_url') or render.server_video_url or render.oss_url
        
        # 视频②：客户端预览视频URL（可选，用于编辑器预览）
        client_video_url = data.get('client_video_url')
        
        if not server_video_url:
            return jsonify({
                'error': '视频①（服务器高质量视频）尚未准备好，请稍后再试',
                'code': 'NO_SERVER_VIDEO'
            }), 400
        
        # 双轨制下，视频①已经是服务器高质量视频，不需要云端转码
        # 旧的转码逻辑保留用于兼容非双轨模式
        needs_transcode = data.get('needs_transcode', False)
        final_video_url = server_video_url
        
        if needs_transcode:
            try:
                from utils.cloud_transcoder import submit_transcode_async

                timestamp = int(time.time())
                output_filename = f"transcoded_{render_id}_{timestamp}.mp4"
                output_url = f"https://mixcut.oss-cn-hangzhou.aliyuncs.com/renders/{user_id or 'anonymous'}/{output_filename}"

                logger.info(f"[Kaipai] 提交云端转码任务，输入: {server_video_url}")

                transcode_task_id = submit_transcode_async(
                    input_url=server_video_url,
                    output_url=output_url,
                    quality='high',
                    user_id=user_id or render.user_id or 'anonymous',
                    render_id=render_id
                )
                
                return jsonify({
                    'edit_id': None,
                    'version': version,
                    'status': 'transcoding',
                    'transcode_task_id': transcode_task_id,
                    'message': '视频正在进行云端转码，请稍后再试'
                })
                
            except Exception as e:
                logger.warning(f"[Kaipai] 云端转码提交失败，使用原始视频: {e}")
        
        # 创建草稿
        edit = KaipaiEdit(
            id=str(uuid.uuid4()),
            user_id=user_id or render.user_id,
            render_id=render_id,
            parent_id=parent_id,
            version=version,
            title=data.get('title', f'草稿 {version}'),
            original_video_url=final_video_url,  # 视频①：服务器高质量视频
            status='draft'
        )
        
        db.session.add(edit)
        db.session.commit()
        
        logger.info(f"[Kaipai] 草稿创建成功: edit_id={edit.id}, render_id={render_id}")
        logger.info(f"[Kaipai] 视频①（ASR/导出用）: {final_video_url}")
        logger.info(f"[Kaipai] 视频②（预览用）: {client_video_url or '未提供'}")
        
        return jsonify({
            'edit_id': edit.id,
            'version': version,
            'status': 'draft',
            'video_url': final_video_url,
            'client_video_url': client_video_url  # 返回视频②URL给前端预览用
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'创建剪辑任务失败: {str(e)}'}), 500


@kaipai_bp.route('/kaipai/transcode/<task_id>/status', methods=['GET'])
def get_transcode_status_route(task_id):
    """
    查询云端转码任务状态
    
    前端在创建草稿时如果返回 transcoding 状态，需要轮询此接口
    转码完成后，自动更新数据库中的 output_video_url
    """
    try:
        from utils.cloud_transcoder import get_async_transcode_status, transcode_tasks
        
        logger.info(f"[Transcode] 查询转码状态: task_id={task_id}")
        status = get_async_transcode_status(task_id)
        logger.info(f"[Transcode] 转码状态: {status}")
        
        if status['status'] == 'completed':
            output_url = status.get('output_url')
            logger.info(f"[Transcode] 转码完成: output_url={output_url}")
            
            # 自动更新数据库中的 output_video_url
            task_info = transcode_tasks.get(task_id, {})
            render_id = task_info.get('render_id')
            logger.info(f"[Transcode] 任务信息: render_id={render_id}")
            
            if render_id and output_url:
                try:
                    # 查找关联的 edit 并更新 output_video_url
                    edit = KaipaiEdit.query.filter_by(render_id=render_id).first()
                    if edit:
                        logger.info(f"[Transcode] 找到关联edit: edit_id={edit.id}")
                        logger.info(f"[Transcode] 更新前: output_video_url={edit.output_video_url}")
                        edit.output_video_url = output_url
                        db.session.commit()
                        logger.info(f"[Transcode] ✓ 已更新 edit {edit.id} 的 output_video_url 为: {output_url}")
                    else:
                        logger.warning(f"[Transcode] ✗ 未找到关联edit: render_id={render_id}")
                except Exception as update_err:
                    logger.error(f"[Transcode] 更新数据库失败: {update_err}")
            else:
                logger.warning(f"[Transcode] 无法更新: render_id={render_id}, output_url={output_url}")
            
            return jsonify({
                'status': 'completed',
                'output_url': output_url,
                'progress': 100
            })
        elif status['status'] == 'failed':
            return jsonify({
                'status': 'failed',
                'error': status.get('error', '转码失败'),
                'progress': 0
            })
        else:
            return jsonify({
                'status': 'processing',
                'progress': status.get('progress', 0)
            })
    
    except Exception as e:
        logger.error(f"查询转码状态失败: {e}")
        return jsonify({'error': str(e)}), 500


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
        
        # 添加DeepSeek提取状态
        # 先从数据库的asr_result中读取metadata
        asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
        db_metadata = asr_result.get('metadata', {})
        
        # 再从内存任务中获取状态（如果存在）
        task = get_asr_task(edit_id)
        if task:
            response['extract_status'] = task.get('extract_status', 'unknown')
            # 优先使用内存中的结果（最新）
            if task.get('extract_status') == 'completed':
                metadata = task.get('result', {}).get('metadata', {})
                response['extracted_title'] = metadata.get('title', '')
                response['extracted_keywords'] = metadata.get('keywords', [])
                
                # 如果内存中有结果但数据库没有，保存到数据库
                if metadata.get('title') and not db_metadata.get('title'):
                    try:
                        asr_result['metadata'] = metadata
                        edit.asr_result = json.dumps(asr_result, ensure_ascii=False)
                        db.session.commit()
                        logger.info(f"[DeepSeek] 提取结果已保存到数据库: {edit_id}")
                    except Exception as e:
                        logger.error(f"[DeepSeek] 保存到数据库失败: {e}")
                        
            elif task.get('extract_status') == 'failed':
                response['extract_error'] = task.get('extract_error', '未知错误')
            elif task.get('extract_status') == 'processing':
                # 还在处理中，检查数据库是否有旧结果
                if db_metadata.get('title'):
                    response['extracted_title'] = db_metadata.get('title', '')
                    response['extracted_keywords'] = db_metadata.get('keywords', [])
        else:
            # 内存中没有任务，检查数据库是否有metadata
            if db_metadata.get('title'):
                response['extract_status'] = 'completed'
                response['extracted_title'] = db_metadata.get('title', '')
                response['extracted_keywords'] = db_metadata.get('keywords', [])
            else:
                # 数据库也没有，启动DeepSeek提取
                logger.info(f"[DeepSeek] 缓存加载，启动异步提取: {edit_id}")
                from utils.kaipai_asr import create_asr_task, async_extract_title_and_keywords
                
                create_asr_task(edit_id, '')
                task = get_asr_task(edit_id)
                task['status'] = 'completed'
                task['result'] = asr_result
                # 先标记为处理中，防止前端显示unknown
                task['extract_status'] = 'processing'
                task['extract_start_time'] = time.time()
                
                if task['result'].get('sentences'):
                    async_extract_title_and_keywords(edit_id, task['result']['sentences'])
                    response['extract_status'] = 'processing'
                else:
                    response['extract_status'] = 'unknown'
        
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
    
    # 添加DeepSeek提取状态
    extract_status = task.get('extract_status', 'unknown')
    
    # 检查是否超时（超过60秒）
    if extract_status == 'processing':
        start_time = task.get('extract_start_time', 0)
        if time.time() - start_time > 60:
            extract_status = 'timeout'
            task['extract_status'] = 'failed'
            task['extract_error'] = '提取超时（超过60秒）'
            logger.warning(f"[DeepSeek] 任务 {edit_id} 提取超时")
    
    response['extract_status'] = extract_status
    
    if extract_status == 'completed' and task.get('result', {}).get('metadata'):
        metadata = task['result']['metadata']
        response['extracted_title'] = metadata.get('title', '')
        response['extracted_keywords'] = metadata.get('keywords', [])
    elif extract_status in ['failed', 'timeout']:
        response['extract_error'] = task.get('extract_error', '未知错误')
    
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
    
    # 获取当前已删除的片段列表
    existing_removed = current_params.get('removed_segments', [])
    new_removed = data.get('removed_segments', [])
    
    # 合并删除的片段（去重，基于id）
    existing_ids = {s.get('id') for s in existing_removed}
    merged_removed = existing_removed.copy()
    for seg in new_removed:
        if seg.get('id') not in existing_ids:
            merged_removed.append(seg)
            existing_ids.add(seg.get('id'))
    
    # 记录编辑操作到历史
    action = {
        'timestamp': datetime.now().isoformat(),
        'action': 'update',
        'removed_segments': new_removed,
        'previous_segments': existing_removed
    }
    edit_history.append(action)
    
    # 更新编辑参数
    current_params.update({
        'removed_segments': merged_removed,
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


def _update_render_task(task_id, **kwargs):
    """线程安全地更新渲染任务状态，如果不存在则创建"""
    with render_tasks_lock:
        if task_id not in render_tasks:
            render_tasks[task_id] = {}
        render_tasks[task_id].update(kwargs)


@kaipai_bp.route('/kaipai/<edit_id>/render', methods=['POST'])
def start_render(edit_id):
    """启动视频渲染（裁剪）- 使用线程池限制并发"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 获取编辑参数
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    
    # 获取所有需要在异步线程中使用的数据（避免session问题）
    video_url = edit.original_video_url
    user_id = edit.user_id
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    
    # 生成任务ID并初始化
    task_id = str(uuid.uuid4())
    _update_render_task(task_id, **{
        'status': 'queued',
        'progress': 0,
        'output_url': None,
        'error': None
    })
    
    # 获取当前应用实例（用于创建应用上下文）
    from flask import current_app
    app = current_app._get_current_object()
    
    # 使用线程池提交任务（限制并发数）
    def render_video():
        with app.app_context():
            _update_render_task(task_id, status='processing', progress=5)
            temp_files_to_cleanup = []
            local_video_path = None
            
            try:
                # 下载原始视频到本地（使用唯一文件名）
                local_video_path = os.path.join('uploads', get_unique_filename('video'))
                if video_url.startswith('http'):
                    import requests
                    logger.info(f"[Render {task_id}] 下载视频: {video_url[:80]}...")
                    response = requests.get(video_url, timeout=120)
                    response.raise_for_status()
                    with open(local_video_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"[Render {task_id}] 视频下载完成: {len(response.content)} bytes")
                else:
                    local_video_path = video_url.lstrip('/')
                    logger.info(f"[Render {task_id}] 使用本地视频: {local_video_path}")
                
                _update_render_task(task_id, progress=15)
                
                # 使用ffprobe获取视频实际时长
                video_duration_ms = get_video_duration(local_video_path)
                if video_duration_ms is None:
                    # 降级使用ASR结果中的时长
                    video_duration_ms = asr_result.get('videoInfo', {}).get('duration', 0) * 1000
                    logger.warning(f"[Render {task_id}] 使用ASR时长: {video_duration_ms}ms")
                else:
                    logger.info(f"[Render {task_id}] 视频实际时长: {video_duration_ms}ms")
                
                if video_duration_ms <= 0:
                    raise Exception('无法获取视频时长')
                
                _update_render_task(task_id, progress=25)
                
                # 计算保留的时间段（处理重叠的删除段）
                keep_segments = calculate_keep_segments(removed_segments, video_duration_ms)
                logger.info(f"[Render {task_id}] 保留时间段: {keep_segments}")
                
                if len(keep_segments) == 0:
                    raise Exception('没有可保留的视频片段')
                
                _update_render_task(task_id, progress=30)
                
                # 生成输出文件名
                output_filename = f"kaipai_render_{edit_id}_{int(datetime.now().timestamp())}.mp4"
                output_path = os.path.join('renders', output_filename)
                
                # 构建ffmpeg命令
                if len(keep_segments) == 1:
                    # 只有一段，直接裁剪
                    start_sec = keep_segments[0][0] / 1000
                    duration = (keep_segments[0][1] - keep_segments[0][0]) / 1000
                    logger.info(f"[Render {task_id}] 单段裁剪: {start_sec}s - {start_sec+duration}s")
                    
                    cmd = [
                        'ffmpeg', '-y', '-i', local_video_path,
                        '-ss', str(start_sec), '-t', str(duration),
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                        '-c:a', 'aac', '-b:a', '128k',
                        output_path
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.error(f"[Render {task_id}] FFmpeg错误: {result.stderr}")
                        raise Exception(f'视频裁剪失败: {result.stderr[:200]}')
                else:
                    # 多段，先分割成临时文件，再用concat demuxer拼接
                    logger.info(f"[Render {task_id}] 多段拼接: {len(keep_segments)} 段")
                    
                    try:
                        # 第一步：将每个时间段分割成临时文件（使用唯一文件名）
                        for i, (start, end) in enumerate(keep_segments):
                            start_sec = start / 1000
                            duration = (end - start) / 1000
                            temp_file = os.path.join('renders', get_unique_filename('segment') + '.mp4')
                            temp_files_to_cleanup.append(temp_file)
                            
                            logger.info(f"[Render {task_id}] 分割段 {i+1}/{len(keep_segments)}: {start_sec}s - {start_sec+duration}s")
                            
                            segment_cmd = [
                                'ffmpeg', '-y', '-i', local_video_path,
                                '-ss', str(start_sec), '-t', str(duration),
                                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                                '-c:a', 'aac', '-b:a', '128k',
                                temp_file
                            ]
                            result = subprocess.run(segment_cmd, capture_output=True, text=True)
                            if result.returncode != 0:
                                logger.error(f"[Render {task_id}] 分割段 {i+1} 失败: {result.stderr}")
                                raise Exception(f'分割视频段失败: {result.stderr[:200]}')
                        
                        _update_render_task(task_id, progress=60)
                        
                        # 第二步：创建concat列表文件
                        list_file = os.path.join('renders', get_unique_filename('concat_list') + '.txt')
                        temp_files_to_cleanup.append(list_file)
                        
                        with open(list_file, 'w') as f:
                            for temp_file in temp_files_to_cleanup:
                                if temp_file.endswith('.mp4'):
                                    abs_path = os.path.abspath(temp_file).replace('\\', '/')
                                    f.write(f"file '{abs_path}'\n")
                        
                        logger.info(f"[Render {task_id}] 创建concat列表: {list_file}")
                        
                        # 第三步：使用concat demuxer拼接并添加音频淡入淡出
                        # 先使用 -c copy 快速拼接
                        temp_output = os.path.join('renders', get_unique_filename('temp_concat') + '.mp4')
                        temp_files_to_cleanup.append(temp_output)
                        
                        concat_cmd = [
                            'ffmpeg', '-y',
                            '-f', 'concat',
                            '-safe', '0',
                            '-i', list_file,
                            '-c', 'copy',
                            temp_output
                        ]
                        result = subprocess.run(concat_cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            logger.error(f"[Render {task_id}] 拼接失败: {result.stderr}")
                            raise Exception(f'视频拼接失败: {result.stderr[:200]}')
                        
                        logger.info(f"[Render {task_id}] 快速拼接完成")
                        
                        # 直接复制到输出（暂时移除淡入淡出，避免音频问题）
                        import shutil
                        shutil.copy(temp_output, output_path)
                        
                        logger.info(f"[Render {task_id}] 拼接完成")
                        
                    finally:
                        # 清理临时文件
                        for temp_file in temp_files_to_cleanup:
                            try:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                    logger.info(f"[Render {task_id}] 清理临时文件: {temp_file}")
                            except Exception as e:
                                logger.warning(f"[Render {task_id}] 清理临时文件失败: {temp_file}, {e}")
                
                _update_render_task(task_id, progress=80)
                
                # 验证输出文件
                if not os.path.exists(output_path):
                    raise Exception('输出文件未生成')
                
                output_size = os.path.getsize(output_path)
                logger.info(f"[Render {task_id}] 输出文件大小: {output_size} bytes")
                
                # 上传到OSS
                logger.info(f"[Render {task_id}] 开始上传OSS...")
                oss_url = oss_client.upload_render(output_path, edit_id, user_id)
                logger.info(f"[Render {task_id}] OSS上传完成: {oss_url[:80]}...")
                
                _update_render_task(task_id, progress=100, status='completed', output_url=oss_url)
                
                # 更新数据库（在新session中）
                with db.session.begin():
                    edit_update = KaipaiEdit.query.get(edit_id)
                    if edit_update:
                        edit_update.output_video_url = oss_url
                        edit_update.status = 'completed'
                
                logger.info(f"[Render {task_id}] 任务完成")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Render {task_id}] 任务失败: {error_msg}")
                _update_render_task(task_id, status='failed', error=error_msg)
                
                # 更新数据库状态为失败
                try:
                    with db.session.begin():
                        edit_update = KaipaiEdit.query.get(edit_id)
                        if edit_update:
                            edit_update.status = 'failed'
                except Exception as db_error:
                    logger.error(f"[Render {task_id}] 更新数据库失败状态失败: {db_error}")
            
            finally:
                # 清理下载的原始视频
                if local_video_path and os.path.exists(local_video_path) and 'video_' in local_video_path:
                    try:
                        os.remove(local_video_path)
                        logger.info(f"[Render {task_id}] 清理原始视频: {local_video_path}")
                    except Exception as e:
                        logger.warning(f"[Render {task_id}] 清理原始视频失败: {e}")
    
    # 提交任务到线程池
    render_executor.submit(render_video)
    
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
    if task:
        return jsonify({
            'task_id': task_id,
            'status': task['status'],
            'progress': task['progress'],
            'output_url': task.get('output_url'),
            'error': task.get('error')
        })
    
    # 内存中找不到，尝试从数据库恢复（服务重启后）
    # 从请求参数中获取 edit_id
    edit_id = request.args.get('edit_id')
    if edit_id:
        edit = KaipaiEdit.query.get(edit_id)
        if edit:
            # 根据草稿状态返回相应信息
            if edit.status == 'completed' and edit.output_video_url:
                return jsonify({
                    'task_id': task_id,
                    'status': 'completed',
                    'progress': 100,
                    'output_url': edit.output_video_url,
                    'error': None
                })
            elif edit.status == 'failed':
                return jsonify({
                    'task_id': task_id,
                    'status': 'failed',
                    'progress': 0,
                    'output_url': None,
                    'error': '渲染失败'
                })
            elif edit.status == 'processing':
                return jsonify({
                    'task_id': task_id,
                    'status': 'processing',
                    'progress': 50,
                    'output_url': None,
                    'error': None
                })
    
    return jsonify({'error': 'Task not found'}), 404


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


@kaipai_bp.route('/kaipai/<edit_id>/video', methods=['GET'])
def download_kaipai_video(edit_id):
    """
    代理下载视频文件（解决CORS跨域问题）
    
    前端通过这个接口下载视频，避免直接从OSS下载时的CORS限制
    """
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    video_url = edit.original_video_url
    if not video_url:
        return jsonify({'error': 'Video URL not found'}), 404
    
    try:
        import requests
        from flask import Response
        
        logger.info(f"[Proxy] 开始代理下载视频: {edit_id}")
        
        # 从OSS下载视频
        response = requests.get(video_url, stream=True, timeout=120)
        response.raise_for_status()
        
        # 获取内容类型
        content_type = response.headers.get('Content-Type', 'video/mp4')
        
        # 流式返回给前端
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        logger.info(f"[Proxy] 视频代理下载成功: {edit_id}")
        
        return Response(
            generate(),
            mimetype=content_type,
            headers={
                'Content-Disposition': f'inline; filename="{edit_id}.mp4"',
                'Access-Control-Allow-Origin': '*',
            }
        )
        
    except Exception as e:
        logger.error(f"[Proxy] 代理下载视频失败: {e}")
        return jsonify({'error': f'下载视频失败: {str(e)}'}), 500


@kaipai_bp.route('/kaipai/<edit_id>/preview/rendered', methods=['POST'])
def render_preview_video(edit_id):
    """渲染预览视频（生成实际裁剪后的视频用于预览）"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 复用render逻辑，但生成低质量预览版本
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    
    # 获取所有需要在异步线程中使用的数据
    video_url = edit.original_video_url
    user_id = edit.user_id
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    
    # 启动预览渲染任务（低质量，快速）
    task_id = str(uuid.uuid4())
    _update_render_task(task_id, **{
        'status': 'queued',
        'progress': 0,
        'output_url': None,
        'error': None,
        'is_preview': True
    })
    
    # 获取当前应用实例
    from flask import current_app
    app = current_app._get_current_object()
    
    def render_preview():
        with app.app_context():
            _update_render_task(task_id, status='processing', progress=5)
            temp_files_to_cleanup = []
            local_video_path = None
            
            try:
                # 下载原始视频（使用唯一文件名）
                local_video_path = os.path.join('uploads', get_unique_filename('preview_video'))
                if video_url.startswith('http'):
                    import requests
                    logger.info(f"[Preview {task_id}] 下载视频: {video_url[:80]}...")
                    response = requests.get(video_url, timeout=120)
                    response.raise_for_status()
                    with open(local_video_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"[Preview {task_id}] 视频下载完成: {len(response.content)} bytes")
                else:
                    local_video_path = video_url.lstrip('/')
                    logger.info(f"[Preview {task_id}] 使用本地视频: {local_video_path}")
                
                _update_render_task(task_id, progress=15)
                
                # 使用ffprobe获取视频实际时长
                video_duration_ms = get_video_duration(local_video_path)
                if video_duration_ms is None:
                    video_duration_ms = asr_result.get('videoInfo', {}).get('duration', 0) * 1000
                    logger.warning(f"[Preview {task_id}] 使用ASR时长: {video_duration_ms}ms")
                else:
                    logger.info(f"[Preview {task_id}] 视频实际时长: {video_duration_ms}ms")
                
                if video_duration_ms <= 0:
                    raise Exception('无法获取视频时长')
                
                _update_render_task(task_id, progress=25)
                
                # 计算保留的时间段
                keep_segments = calculate_keep_segments(removed_segments, video_duration_ms)
                logger.info(f"[Preview {task_id}] 保留时间段: {keep_segments}")
                
                if len(keep_segments) == 0:
                    raise Exception('没有可保留的视频片段')
                
                _update_render_task(task_id, progress=35)
                
                # 生成预览视频（低质量，快速）
                output_filename = f"kaipai_preview_{edit_id}_{int(datetime.now().timestamp())}.mp4"
                output_path = os.path.join('renders', output_filename)
                
                # 构建ffmpeg命令 - 预览版使用更低质量
                if len(keep_segments) == 1:
                    # 只有一段，直接裁剪
                    start_sec = keep_segments[0][0] / 1000
                    duration = (keep_segments[0][1] - keep_segments[0][0]) / 1000
                    logger.info(f"[Preview {task_id}] 单段裁剪: {start_sec}s - {start_sec+duration}s")
                    
                    cmd = [
                        'ffmpeg', '-y', '-i', local_video_path,
                        '-ss', str(start_sec), '-t', str(duration),
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                        '-vf', 'scale=480:-2',
                        '-c:a', 'aac', '-b:a', '96k',
                        output_path
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.error(f"[Preview {task_id}] FFmpeg错误: {result.stderr}")
                        raise Exception(f'视频裁剪失败: {result.stderr[:200]}')
                else:
                    # 多段，先分割成临时文件，再用concat demuxer拼接
                    logger.info(f"[Preview {task_id}] 多段拼接: {len(keep_segments)} 段")
                    
                    try:
                        # 第一步：将每个时间段分割成临时文件
                        for i, (start, end) in enumerate(keep_segments):
                            start_sec = start / 1000
                            duration = (end - start) / 1000
                            temp_file = os.path.join('renders', get_unique_filename('preview_segment') + '.mp4')
                            temp_files_to_cleanup.append(temp_file)
                            
                            logger.info(f"[Preview {task_id}] 分割段 {i+1}/{len(keep_segments)}: {start_sec}s - {start_sec+duration}s")
                            
                            segment_cmd = [
                                'ffmpeg', '-y', '-i', local_video_path,
                                '-ss', str(start_sec), '-t', str(duration),
                                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                                '-vf', 'scale=480:-2',
                                '-c:a', 'aac', '-b:a', '96k',
                                temp_file
                            ]
                            result = subprocess.run(segment_cmd, capture_output=True, text=True)
                            if result.returncode != 0:
                                logger.error(f"[Preview {task_id}] 分割段 {i+1} 失败: {result.stderr}")
                                raise Exception(f'分割视频段失败: {result.stderr[:200]}')
                        
                        _update_render_task(task_id, progress=60)
                        
                        # 第二步：创建concat列表文件
                        list_file = os.path.join('renders', get_unique_filename('preview_concat_list') + '.txt')
                        temp_files_to_cleanup.append(list_file)
                        
                        with open(list_file, 'w') as f:
                            for temp_file in temp_files_to_cleanup:
                                if temp_file.endswith('.mp4'):
                                    abs_path = os.path.abspath(temp_file).replace('\\', '/')
                                    f.write(f"file '{abs_path}'\n")
                        
                        logger.info(f"[Preview {task_id}] 创建concat列表: {list_file}")
                        
                        # 第三步：使用concat demuxer拼接并添加音频淡入淡出
                        temp_output = os.path.join('renders', get_unique_filename('preview_temp_concat') + '.mp4')
                        temp_files_to_cleanup.append(temp_output)
                        
                        concat_cmd = [
                            'ffmpeg', '-y',
                            '-f', 'concat',
                            '-safe', '0',
                            '-i', list_file,
                            '-c', 'copy',
                            temp_output
                        ]
                        result = subprocess.run(concat_cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            logger.error(f"[Preview {task_id}] 拼接失败: {result.stderr}")
                            raise Exception(f'视频拼接失败: {result.stderr[:200]}')
                        
                        logger.info(f"[Preview {task_id}] 快速拼接完成")
                        
                        # 直接复制到输出
                        import shutil
                        shutil.copy(temp_output, output_path)
                        
                        logger.info(f"[Preview {task_id}] 拼接完成")
                        
                    finally:
                        # 清理临时文件
                        for temp_file in temp_files_to_cleanup:
                            try:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                    logger.info(f"[Preview {task_id}] 清理临时文件: {temp_file}")
                            except Exception as e:
                                logger.warning(f"[Preview {task_id}] 清理临时文件失败: {temp_file}, {e}")
                
                _update_render_task(task_id, progress=80)
                
                # 验证输出文件
                if not os.path.exists(output_path):
                    raise Exception('输出文件未生成')
                
                output_size = os.path.getsize(output_path)
                logger.info(f"[Preview {task_id}] 输出文件大小: {output_size} bytes")
                
                # 上传到OSS
                logger.info(f"[Preview {task_id}] 开始上传OSS...")
                oss_url = oss_client.upload_render(output_path, edit_id, user_id)
                logger.info(f"[Preview {task_id}] OSS上传完成: {oss_url[:80]}...")
                
                _update_render_task(task_id, progress=100, status='completed', output_url=oss_url)
                logger.info(f"[Preview {task_id}] 任务完成")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Preview {task_id}] 任务失败: {error_msg}")
                _update_render_task(task_id, status='failed', error=error_msg)
            
            finally:
                # 清理下载的原始视频
                if local_video_path and os.path.exists(local_video_path) and 'preview_video_' in local_video_path:
                    try:
                        os.remove(local_video_path)
                        logger.info(f"[Preview {task_id}] 清理原始视频: {local_video_path}")
                    except Exception as e:
                        logger.warning(f"[Preview {task_id}] 清理原始视频失败: {e}")
    
    # 提交任务到线程池
    render_executor.submit(render_preview)
    
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
    try:
        drafts = KaipaiEdit.query.filter_by(user_id=user_id).order_by(KaipaiEdit.updated_at.desc()).all()
        
        return jsonify({
            'user_id': user_id,
            'drafts': [d.to_dict() for d in drafts]
        })
    except Exception as e:
        logger.error(f"获取用户草稿失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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


# ==================== 模板相关API ====================

@kaipai_bp.route('/kaipai/templates', methods=['GET'])
def get_templates():
    """获取系统预设模板列表"""
    from models import Template
    
    category = request.args.get('category')
    
    query = Template.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    
    templates = query.order_by(Template.sort_order).all()
    
    return jsonify({
        'templates': [t.to_dict() for t in templates]
    })


@kaipai_bp.route('/kaipai/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """获取单个模板详情"""
    from models import Template
    
    template = Template.query.get(template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    return jsonify(template.to_dict())


@kaipai_bp.route('/kaipai/<edit_id>/template', methods=['PUT'])
def update_edit_template(edit_id):
    """更新草稿选择的模板"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.get_json(silent=True) or {}
    template_id = data.get('template_id')
    
    # 如果template_id为null，表示取消选择模板
    if template_id:
        from models import Template
        template = Template.query.get(template_id)
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        edit.template_id = template_id
    else:
        edit.template_id = None
    
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'template_id': edit.template_id,
        'template': edit.template.to_dict() if edit.template else None
    })


@kaipai_bp.route('/kaipai/<edit_id>/export', methods=['POST'])
def export_video(edit_id):
    """
    导出视频（支持模板渲染）
    
    流程：
    1. 如果选择了模板：文字快剪拼接删除 + ICE模板渲染
    2. 如果没有选择模板：仅文字快剪拼接删除
    """
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 获取编辑参数
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    removed_ids = [s['id'] for s in removed_segments]
    
    # 获取ASR结果
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    sentences = asr_result.get('sentences', [])
    
    if not sentences:
        return jsonify({'error': 'No ASR data available'}), 400
    
    # 检查是否选择了模板
    if edit.template_id:
        # 有模板：提交ICE渲染任务
        return _export_with_template(edit, sentences, removed_ids, asr_result, removed_segments)
    else:
        # 无模板：使用原有FFmpeg拼接逻辑
        return _export_without_template(edit, removed_segments, asr_result)


def _export_with_template(edit, sentences, removed_ids, asr_result, removed_segments):
    """
    使用模板导出（ICE渲染）
    
    支持两种模式：
    1. ICE直接裁剪模式（USE_ICE_DIRECT_CROP=True）：
       - 直接使用原始视频URL，通过ICE的In/Out参数裁剪
       - 省去下载、FFmpeg处理、上传中间视频环节
       - 预计节省 43-70% 时间
    
    2. 本地裁剪模式（USE_ICE_DIRECT_CROP=False）：
       - 先做文字快剪（FFmpeg拼接删除）
       - 上传中间视频到OSS
       - 用中间视频作为输入，提交ICE模板渲染
    """
    from utils.ice_renderer import (
        generate_ice_timeline, 
        generate_ice_timeline_with_crop,
        submit_ice_job, 
        calculate_actual_duration,
        calculate_keep_segments
    )
    from models import Template
    
    template = Template.query.get(edit.template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    template_config = json.loads(template.config) if template.config else {}
    
    # 创建任务
    task_id = str(uuid.uuid4())
    _update_render_task(task_id, **{
        'status': 'processing',
        'progress': 0,
        'output_url': None,
        'error': None,
        'is_template': True,
        'use_ice_crop': USE_ICE_DIRECT_CROP  # 记录使用的模式
    })
    
    edit.status = 'processing'
    db.session.commit()
    
    from flask import current_app
    app = current_app._get_current_object()
    
    if USE_ICE_DIRECT_CROP:
        # 使用ICE直接裁剪模式（优化版）
        def render_with_template_optimized():
            """渲染任务（ICE直接裁剪 + 模板渲染）"""
            with app.app_context():
                _render_with_template_optimized_impl(app, edit, sentences, removed_ids, asr_result, template, template_config, task_id)
        
        render_executor.submit(render_with_template_optimized)
        
        return jsonify({
            'edit_id': edit.id,
            'status': 'processing',
            'task_id': task_id,
            'use_template': True,
            'use_ice_crop': True,
            'template_name': template.name,
            'message': '开始渲染：ICE直接裁剪 + 模板渲染（优化模式）'
        })
    else:
        # 使用本地裁剪模式（原有逻辑）
        def render_with_template():
            """渲染任务（文字快剪 + ICE模板）"""
            with app.app_context():
                _render_with_template_impl(app, edit, sentences, removed_ids, removed_segments, template, template_config, task_id)
        
        render_executor.submit(render_with_template)
        
        return jsonify({
            'edit_id': edit.id,
            'status': 'processing',
            'task_id': task_id,
            'use_template': True,
            'use_ice_crop': False,
            'template_name': template.name,
            'message': '开始渲染：文字快剪 + 模板渲染（兼容模式）'
        })


def _render_with_template_optimized_impl(app, edit, sentences, removed_ids, asr_result, template, template_config, task_id):
    """
    优化的渲染实现（ICE直接裁剪模式）
    
    流程：
    1. 直接使用原始视频URL
    2. 生成带In/Out裁剪参数的Timeline
    3. 提交ICE任务（裁剪+渲染一次完成）
    """
    from utils.ice_renderer import (
        generate_ice_timeline_with_crop,
        submit_ice_job
    )
    
    try:
        _update_render_task(task_id, progress=10)
        
        # 详细记录视频选择逻辑
        logger.info(f"[Task {task_id}] ========== 视频选择开始 ==========")
        logger.info(f"[Task {task_id}] edit.id: {edit.id}")
        logger.info(f"[Task {task_id}] edit.render_id: {edit.render_id}")
        logger.info(f"[Task {task_id}] edit.original_video_url: {edit.original_video_url}")
        logger.info(f"[Task {task_id}] edit.output_video_url: {edit.output_video_url}")
        logger.info(f"[Task {task_id}] output_video_url 是否存在: {bool(edit.output_video_url)}")
        
        # 优先使用转码后的视频（如果存在且可用）
        if edit.output_video_url and edit.output_video_url.strip():
            video_url = edit.output_video_url
            logger.info(f"[Task {task_id}] ✓ 选择转码后的视频（高质量）")
            logger.info(f"[Task {task_id}] ✓ 视频URL: {video_url}")
        else:
            video_url = edit.original_video_url
            logger.info(f"[Task {task_id}] ✗ 转码视频不可用，使用原始视频")
            logger.info(f"[Task {task_id}] ✗ 视频URL: {video_url}")
        
        user_id = edit.user_id
        
        logger.info(f"[Task {task_id}] ========== 视频选择结束 ==========")
        logger.info(f"[Task {task_id}] ICE直接裁剪模式开始...")
        logger.info(f"[Task {task_id}] 最终输入视频: {video_url[:100]}...")
        
        # 获取视频时长
        video_duration_ms = asr_result.get('videoInfo', {}).get('duration', 0) * 1000
        if video_duration_ms <= 0:
            # 尝试从句子计算
            if sentences:
                video_duration_ms = max(s.get('endTime', 0) for s in sentences)
        
        if video_duration_ms <= 0:
            raise Exception('无法获取视频时长')
        
        logger.info(f"[Task {task_id}] 视频时长: {video_duration_ms}ms")
        
        _update_render_task(task_id, progress=30)
        
        # ========== 核心：生成带裁剪参数的Timeline ==========
        logger.info(f"[Task {task_id}] 生成ICE Timeline（带裁剪参数）...")
        
        timeline = generate_ice_timeline_with_crop(
            video_url=video_url,  # 直接使用原始视频URL
            sentences=sentences,
            removed_segment_ids=removed_ids,
            template_config=template_config,
            video_duration_ms=video_duration_ms,
            asr_result=asr_result  # 传入ASR结果，包含DeepSeek提取的标题
        )
        
        _update_render_task(task_id, progress=50)
        
        # 提交ICE任务
        logger.info(f"[Task {task_id}] 提交ICE渲染任务...")
        output_filename = f"kaipai_template_{edit.id}_{int(datetime.now().timestamp())}.mp4"
        job_id, output_url = submit_ice_job(timeline, user_id, output_filename)
        
        logger.info(f"[Task {task_id}] ICE任务提交成功: {job_id}")
        
        _update_render_task(task_id, progress=60, ice_job_id=job_id)
        
        # 轮询ICE任务状态（优化轮询间隔）
        from utils.ice_renderer import get_job_status
        import time
        
        poll_interval = 2  # 初始2秒
        max_interval = 10  # 最大10秒
        
        while True:
            try:
                status = get_job_status(job_id)
                
                if status == 'Success':
                    logger.info(f"[Task {task_id}] ICE渲染完成: {output_url[:80]}...")
                    _update_render_task(task_id, status='completed', progress=100, output_url=output_url)
                    with db.session.begin():
                        edit_update = KaipaiEdit.query.get(edit.id)
                        if edit_update:
                            edit_update.output_video_url = output_url
                            edit_update.status = 'completed'
                    break
                elif status == 'Failed':
                    logger.error(f"[Task {task_id}] ICE渲染失败")
                    _update_render_task(task_id, status='failed', error='ICE render failed')
                    with db.session.begin():
                        edit_update = KaipaiEdit.query.get(edit.id)
                        if edit_update:
                            edit_update.status = 'failed'
                    break
                else:
                    # 更新进度（60-95%）
                    current_progress = render_tasks.get(task_id, {}).get('progress', 60)
                    new_progress = min(95, current_progress + 5)
                    _update_render_task(task_id, progress=new_progress)
                
                # 指数退避
                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, max_interval)
                
            except Exception as e:
                logger.error(f"[Task {task_id}] 轮询ICE状态失败: {e}")
                time.sleep(5)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Task {task_id}] 渲染失败: {error_msg}")
        _update_render_task(task_id, status='failed', error=error_msg)
        
        try:
            with db.session.begin():
                edit_update = KaipaiEdit.query.get(edit.id)
                if edit_update:
                    edit_update.status = 'failed'
        except Exception:
            pass


def _render_with_template_impl(app, edit, sentences, removed_ids, removed_segments, template, template_config, task_id):
    """
    原有的渲染实现（本地裁剪模式，作为fallback保留）
    
    流程：
    1. 先做文字快剪（FFmpeg拼接删除）
    2. 上传中间视频到OSS
    3. 用中间视频作为输入，提交ICE模板渲染
    """
    temp_files_to_cleanup = []
    intermediate_video_url = None
    
    try:
        _update_render_task(task_id, progress=5)
        
        # ========== 第1步：文字快剪（FFmpeg拼接删除）==========
        logger.info(f"[Task {task_id}] 开始文字快剪（本地模式）...")
        
        video_url = edit.original_video_url
        user_id = edit.user_id
        
        # 下载原始视频
        local_video_path = os.path.join('uploads', get_unique_filename('video'))
        if video_url.startswith('http'):
            import requests
            logger.info(f"[Task {task_id}] 下载视频...")
            response = requests.get(video_url, timeout=120)
            response.raise_for_status()
            with open(local_video_path, 'wb') as f:
                f.write(response.content)
        else:
            local_video_path = video_url.lstrip('/')
        
        _update_render_task(task_id, progress=15)
        
        # 获取视频时长
        video_duration_ms = get_video_duration(local_video_path)
        if video_duration_ms is None:
            video_duration_ms = asr_result.get('videoInfo', {}).get('duration', 0) * 1000
        
        if video_duration_ms <= 0:
            raise Exception('无法获取视频时长')
        
        _update_render_task(task_id, progress=25)
        
        # 计算保留时间段
        keep_segments = calculate_keep_segments(removed_segments, video_duration_ms)
        
        if len(keep_segments) == 0:
            raise Exception('没有可保留的视频片段')
        
        _update_render_task(task_id, progress=30)
        
        # 生成中间视频文件（文字快剪结果）
        intermediate_filename = f"kaipai_intermediate_{edit.id}_{int(datetime.now().timestamp())}.mp4"
        intermediate_path = os.path.join('renders', intermediate_filename)
        temp_files_to_cleanup.append(intermediate_path)
        
        # 使用FFmpeg处理
        if len(keep_segments) == 1:
            # 单段裁剪
            start_sec = keep_segments[0][0] / 1000
            duration = (keep_segments[0][1] - keep_segments[0][0]) / 1000
            
            cmd = [
                'ffmpeg', '-y', '-i', local_video_path,
                '-ss', str(start_sec), '-t', str(duration),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k',
                intermediate_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f'视频裁剪失败: {result.stderr[:200]}')
        else:
            # 多段拼接
            segment_files = []
            for i, (start, end) in enumerate(keep_segments):
                start_sec = start / 1000
                duration = (end - start) / 1000
                temp_file = os.path.join('renders', get_unique_filename('segment') + '.mp4')
                temp_files_to_cleanup.append(temp_file)
                segment_files.append(temp_file)
                
                segment_cmd = [
                    'ffmpeg', '-y', '-i', local_video_path,
                    '-ss', str(start_sec), '-t', str(duration),
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k',
                    temp_file
                ]
                result = subprocess.run(segment_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f'分割视频段失败: {result.stderr[:200]}')
            
            _update_render_task(task_id, progress=50)
            
            # 创建concat列表
            list_file = os.path.join('renders', get_unique_filename('concat_list') + '.txt')
            temp_files_to_cleanup.append(list_file)
            
            with open(list_file, 'w') as f:
                for temp_file in segment_files:
                    abs_path = os.path.abspath(temp_file).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            
            # 拼接
            temp_output = os.path.join('renders', get_unique_filename('temp_concat') + '.mp4')
            temp_files_to_cleanup.append(temp_output)
            
            concat_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                temp_output
            ]
            result = subprocess.run(concat_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f'视频拼接失败: {result.stderr[:200]}')
            
            import shutil
            shutil.copy(temp_output, intermediate_path)
        
        _update_render_task(task_id, progress=60)
        
        # 上传中间视频到OSS
        logger.info(f"[Task {task_id}] 上传中间视频到OSS...")
        intermediate_video_url = oss_client.upload_render(intermediate_path, f"intermediate_{edit.id}", user_id)
        
        _update_render_task(task_id, progress=70)
        
        # ========== 第2步：ICE模板渲染 ==========
        logger.info(f"[Task {task_id}] 开始ICE模板渲染...")
        
        # 生成ICE Timeline（使用中间视频作为输入）
        timeline = generate_ice_timeline(
            video_url=intermediate_video_url,
            sentences=sentences,
            removed_segment_ids=removed_ids,
            template_config=template_config,
            video_duration_ms=calculate_actual_duration([s for s in sentences if s['id'] not in removed_ids])
        )
        
        # 提交ICE任务
        output_filename = f"kaipai_template_{edit.id}_{int(datetime.now().timestamp())}.mp4"
        job_id, output_url = submit_ice_job(timeline, user_id, output_filename)
        
        _update_render_task(task_id, progress=80, ice_job_id=job_id)
        
        # 轮询ICE任务状态
        from utils.ice_renderer import get_job_status
        import time
        
        poll_interval = 5
        
        while True:
            try:
                status = get_job_status(job_id)
                
                if status == 'Success':
                    _update_render_task(task_id, status='completed', progress=100, output_url=output_url)
                    with db.session.begin():
                        edit_update = KaipaiEdit.query.get(edit.id)
                        if edit_update:
                            edit_update.output_video_url = output_url
                            edit_update.status = 'completed'
                    break
                elif status == 'Failed':
                    _update_render_task(task_id, status='failed', error='ICE render failed')
                    with db.session.begin():
                        edit_update = KaipaiEdit.query.get(edit.id)
                        if edit_update:
                            edit_update.status = 'failed'
                    break
                else:
                    current_progress = render_tasks.get(task_id, {}).get('progress', 80)
                    new_progress = min(95, current_progress + 3)
                    _update_render_task(task_id, progress=new_progress)
                
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.error(f"[Task {task_id}] 轮询ICE状态失败: {e}")
                time.sleep(10)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Task {task_id}] 渲染失败: {error_msg}")
        _update_render_task(task_id, status='failed', error=error_msg)
        
        try:
            with db.session.begin():
                edit_update = KaipaiEdit.query.get(edit.id)
                if edit_update:
                    edit_update.status = 'failed'
        except Exception:
            pass
    
    finally:
        # 清理临时文件
        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
        
        if local_video_path and os.path.exists(local_video_path) and 'video_' in local_video_path:
            try:
                os.remove(local_video_path)
            except Exception:
                pass


def _export_without_template(edit, removed_segments, asr_result):
    """不使用模板导出（原有FFmpeg逻辑）"""
    # 复用原有的render逻辑
    video_url = edit.original_video_url
    user_id = edit.user_id
    edit_id = edit.id
    
    # 创建任务
    task_id = str(uuid.uuid4())
    _update_render_task(task_id, **{
        'status': 'queued',
        'progress': 0,
        'output_url': None,
        'error': None,
        'is_template': False
    })
    
    from flask import current_app
    app = current_app._get_current_object()
    
    def render_video():
        """视频渲染任务"""
        with app.app_context():
            temp_files_to_cleanup = []
            local_video_path = None
            
            try:
                _update_render_task(task_id, status='processing', progress=5)
                
                # 下载原始视频
                local_video_path = os.path.join('uploads', get_unique_filename('video'))
                if video_url.startswith('http'):
                    import requests
                    logger.info(f"[Render {task_id}] 下载视频...")
                    response = requests.get(video_url, timeout=120)
                    response.raise_for_status()
                    with open(local_video_path, 'wb') as f:
                        f.write(response.content)
                else:
                    local_video_path = video_url.lstrip('/')
                
                _update_render_task(task_id, progress=15)
                
                # 获取视频时长
                video_duration_ms = get_video_duration(local_video_path)
                if video_duration_ms is None:
                    video_duration_ms = asr_result.get('videoInfo', {}).get('duration', 0) * 1000
                
                if video_duration_ms <= 0:
                    raise Exception('无法获取视频时长')
                
                _update_render_task(task_id, progress=25)
                
                # 计算保留时间段
                keep_segments = calculate_keep_segments(removed_segments, video_duration_ms)
                
                if len(keep_segments) == 0:
                    raise Exception('没有可保留的视频片段')
                
                _update_render_task(task_id, progress=30)
                
                # 生成输出文件
                output_filename = f"kaipai_render_{edit_id}_{int(datetime.now().timestamp())}.mp4"
                output_path = os.path.join('renders', output_filename)
                
                # 使用FFmpeg处理
                if len(keep_segments) == 1:
                    # 单段裁剪
                    start_sec = keep_segments[0][0] / 1000
                    duration = (keep_segments[0][1] - keep_segments[0][0]) / 1000
                    
                    cmd = [
                        'ffmpeg', '-y', '-i', local_video_path,
                        '-ss', str(start_sec), '-t', str(duration),
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                        '-c:a', 'aac', '-b:a', '128k',
                        output_path
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise Exception(f'视频裁剪失败: {result.stderr[:200]}')
                else:
                    # 多段拼接
                    for i, (start, end) in enumerate(keep_segments):
                        start_sec = start / 1000
                        duration = (end - start) / 1000
                        temp_file = os.path.join('renders', get_unique_filename('segment') + '.mp4')
                        temp_files_to_cleanup.append(temp_file)
                        
                        segment_cmd = [
                            'ffmpeg', '-y', '-i', local_video_path,
                            '-ss', str(start_sec), '-t', str(duration),
                            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                            '-c:a', 'aac', '-b:a', '128k',
                            temp_file
                        ]
                        result = subprocess.run(segment_cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            raise Exception(f'分割视频段失败: {result.stderr[:200]}')
                    
                    _update_render_task(task_id, progress=60)
                    
                    # 创建concat列表
                    list_file = os.path.join('renders', get_unique_filename('concat_list') + '.txt')
                    temp_files_to_cleanup.append(list_file)
                    
                    with open(list_file, 'w') as f:
                        for temp_file in temp_files_to_cleanup:
                            if temp_file.endswith('.mp4'):
                                abs_path = os.path.abspath(temp_file).replace('\\', '/')
                                f.write(f"file '{abs_path}'\n")
                    
                    # 拼接
                    temp_output = os.path.join('renders', get_unique_filename('temp_concat') + '.mp4')
                    temp_files_to_cleanup.append(temp_output)
                    
                    concat_cmd = [
                        'ffmpeg', '-y',
                        '-f', 'concat',
                        '-safe', '0',
                        '-i', list_file,
                        '-c', 'copy',
                        temp_output
                    ]
                    result = subprocess.run(concat_cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise Exception(f'视频拼接失败: {result.stderr[:200]}')
                    
                    import shutil
                    shutil.copy(temp_output, output_path)
                
                _update_render_task(task_id, progress=80)
                
                # 上传OSS
                oss_url = oss_client.upload_render(output_path, edit_id, user_id)
                
                _update_render_task(task_id, progress=100, status='completed', output_url=oss_url)
                
                # 更新数据库
                with db.session.begin():
                    edit_update = KaipaiEdit.query.get(edit_id)
                    if edit_update:
                        edit_update.output_video_url = oss_url
                        edit_update.status = 'completed'
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Render {task_id}] 任务失败: {error_msg}")
                _update_render_task(task_id, status='failed', error=error_msg)
                
                try:
                    with db.session.begin():
                        edit_update = KaipaiEdit.query.get(edit_id)
                        if edit_update:
                            edit_update.status = 'failed'
                except Exception:
                    pass
            
            finally:
                # 清理临时文件
                for temp_file in temp_files_to_cleanup:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception:
                        pass
                
                if local_video_path and os.path.exists(local_video_path) and 'video_' in local_video_path:
                    try:
                        os.remove(local_video_path)
                    except Exception:
                        pass
    
    # 提交任务
    render_executor.submit(render_video)
    
    edit.status = 'processing'
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'processing',
        'task_id': task_id,
        'use_template': False
    })


@kaipai_bp.route('/test-deepseek', methods=['POST'])
def test_deepseek():
    """测试DeepSeek API是否正常工作"""
    try:
        from utils.kaipai_asr import extract_title_and_keywords_with_deepseek
        
        test_sentences = [
            {'text': '这是一个测试视频'},
            {'text': '展示了如何提取标题和关键词'},
            {'text': '增长率达到50%，非常惊人'}
        ]
        
        logger.info('[Test] 开始测试DeepSeek API')
        result = extract_title_and_keywords_with_deepseek(test_sentences)
        logger.info(f'[Test] DeepSeek返回: {result}')
        
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        logger.error(f'[Test] DeepSeek测试失败: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
