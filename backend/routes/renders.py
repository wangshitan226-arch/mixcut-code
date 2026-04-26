"""
Render result routes - 优化版本：本地预览 + OSS下载
优化点：
1. 视频合成后保存本地文件，用于流畅预览
2. 后台异步上传OSS，用于下载和文字快剪
3. 预览优先使用本地文件，下载使用OSS URL
4. 本地文件按原逻辑清理（素材变化时）
"""
from flask import Blueprint, request, jsonify, send_from_directory, current_app
import os
import uuid
import threading
import json
import time
import logging
import subprocess
from models import User, Render, Material
from extensions import db, render_tasks
from config import RENDERS_FOLDER
from utils import fast_concat_videos
from utils.oss import oss_client

logger = logging.getLogger(__name__)

renders_bp = Blueprint('renders', __name__, url_prefix='/api')


def update_render_oss_url(combo_id, oss_url, app):
    """
    OSS上传完成后，更新数据库的oss_url字段
    
    Args:
        combo_id: 渲染组合ID
        oss_url: OSS URL
        app: Flask应用实例
    """
    with app.app_context():
        try:
            render = Render.query.get(combo_id)
            if render:
                render.oss_url = oss_url
                db.session.commit()
                print(f"[OSS] 数据库已更新: {combo_id} -> OSS URL={oss_url}")
            else:
                print(f"[OSS] 未找到渲染记录: {combo_id}")
        except Exception as e:
            print(f"[OSS] 更新数据库失败: {e}")
            db.session.rollback()


def fast_concat_task(task_id, combo_id, unified_files, output_path, user_id=None, app=None, quality='medium'):
    """
    Fast concat using -c copy
    优化：合成后保存本地文件，后台异步上传OSS
    """
    if app is None:
        from app_new import create_app
        app = create_app()
    
    with app.app_context():
        db.app = app
        
        render_tasks[task_id] = {
            'id': task_id,
            'combo_id': combo_id,
            'status': 'processing',
            'progress': 0,
            'output_path': output_path
        }
        
        try:
            render_tasks[task_id]['progress'] = 50
            # 传入质量参数以控制输出码率
            success = fast_concat_videos(unified_files, output_path, quality=quality)
            
            if success and os.path.exists(output_path):
                # 立即返回本地URL（用户流畅预览）
                render_tasks[task_id]['progress'] = 100
                render_tasks[task_id]['status'] = 'completed'
                render_tasks[task_id]['video_url'] = f'/renders/{os.path.basename(output_path)}'
                
                # 更新数据库：保存本地文件路径
                try:
                    render = Render.query.get(combo_id)
                    if render:
                        render.file_path = output_path
                        render.status = 'completed'
                        db.session.commit()
                        print(f"[RENDER] 数据库已更新（本地）: {combo_id} -> {output_path}")
                except Exception as db_error:
                    print(f"[RENDER] 数据库更新失败: {db_error}")
                    db.session.rollback()
                
                print(f"[RENDER] 任务 {task_id} 完成（本地）: {output_path}")
                
                # 后台异步上传OSS（不删除本地文件）
                def oss_callback(oss_url, success):
                    """OSS上传完成后的回调"""
                    if success and oss_url:
                        render_tasks[task_id]['oss_url'] = oss_url
                        render_tasks[task_id]['oss_uploaded'] = True
                        # 只更新oss_url字段，保留本地文件
                        update_render_oss_url(combo_id, oss_url, app)
                    else:
                        render_tasks[task_id]['oss_uploaded'] = False
                        print(f"[OSS] 上传失败: {combo_id}")
                
                # 获取用户信息（用于判断匿名用户）
                try:
                    user = User.query.get(user_id) if user_id else None
                except:
                    user = None
                
                print(f"[OSS] 启动异步上传: {combo_id}")
                oss_client.upload_render_async(
                    local_path=output_path,
                    render_id=combo_id,
                    user_id=user_id,
                    user_obj=user,
                    callback=oss_callback
                )
                
            else:
                render_tasks[task_id]['status'] = 'failed'
                render_tasks[task_id]['error'] = 'Concat failed'
                
        except Exception as e:
            print(f"[RENDER] 任务 {task_id} 失败: {e}")
            import traceback
            traceback.print_exc()
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
            # 优先使用本地文件预览（速度快）
            file_exists = False
            video_url = None
            oss_uploading = False
            oss_uploaded = False
            
            if render.file_path and os.path.exists(render.file_path):
                # 本地文件存在，用于预览
                file_exists = True
                video_url = f'/renders/{os.path.basename(render.file_path)}'
            elif render.oss_url:
                # 本地不存在但有OSS URL
                file_exists = True
                video_url = render.oss_url
                oss_uploaded = True
            
            # 检查是否正在上传OSS
            if not render.oss_url and not oss_uploaded:
                for task_id, task in render_tasks.items():
                    if task.get('combo_id') == render.id and task.get('status') == 'completed' and not task.get('oss_uploaded'):
                        oss_uploading = True
                        break
            
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
                'preview_url': video_url,  # 优先本地文件，流畅预览
                'oss_url': render.oss_url,  # OSS URL（用于下载）
                'oss_uploading': oss_uploading,
                'oss_uploaded': bool(render.oss_url)
            }
            combinations.append(combo_data)
        
        return jsonify({'combinations': combinations})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@renders_bp.route('/video/<combo_id>/preview', methods=['GET'])
def get_preview_video(combo_id):
    """
    获取优化后的预览视频（低码率版本）
    用于服务器部署后的流畅播放
    """
    try:
        render = Render.query.get(combo_id)
        if not render:
            return jsonify({'error': '视频不存在'}), 404
        
        # 检查是否已有低码率预览版本
        preview_filename = f"preview_{combo_id}.mp4"
        preview_path = os.path.join(RENDERS_FOLDER, preview_filename)
        
        # 如果预览版已存在，直接返回
        if os.path.exists(preview_path):
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{preview_filename}',
                'type': 'preview'
            })
        
        # 检查原视频是否存在
        if not render.file_path or not os.path.exists(render.file_path):
            return jsonify({'error': '原视频不存在'}), 404
        
        # 异步生成低码率预览版
        task_id = f"preview_{uuid.uuid4().hex[:8]}"
        app = current_app._get_current_object()
        
        def generate_preview():
            with app.app_context():
                try:
                    from utils.video import transcode_to_unified
                    
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', render.file_path,
                        '-c:v', 'libx264',
                        '-preset', 'superfast',
                        '-crf', '28',  # 更高压缩率
                        '-maxrate', '1M',  # 限制码率1Mbps
                        '-bufsize', '1M',
                        '-vf', 'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2',
                        '-c:a', 'aac',
                        '-b:a', '96k',
                        '-movflags', '+faststart',
                        preview_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"[Preview] 生成成功: {preview_path}")
                    else:
                        print(f"[Preview] 生成失败: {result.stderr}")
                except Exception as e:
                    print(f"[Preview] 异常: {e}")
        
        thread = threading.Thread(target=generate_preview)
        thread.daemon = True
        thread.start()
        
        # 返回原视频URL，预览版生成后下次请求会返回
        return jsonify({
            'status': 'processing',
            'video_url': f'/renders/{os.path.basename(render.file_path)}',
            'message': '预览版生成中，请稍后刷新'
        })
        
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
        
        # 检查本地文件是否存在（优先本地，速度快）
        if render.file_path and os.path.exists(render.file_path):
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{os.path.basename(render.file_path)}',
                'source': 'local'
            })
        
        # 检查OSS URL是否存在（兜底）
        if render.oss_url:
            return jsonify({
                'status': 'completed',
                'video_url': render.oss_url,
                'source': 'oss'
            })
        
        # 检查是否有正在进行的任务
        for task_id, task in render_tasks.items():
            if task.get('combo_id') == combo_id and task['status'] == 'processing':
                return jsonify({
                    'status': 'processing',
                    'task_id': task_id,
                    'progress': task.get('progress', 0)
                })
        
        # 生成新视频
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
        app = current_app._get_current_object()
        
        thread = threading.Thread(
            target=fast_concat_task,
            args=(task_id, combo_id, material_files, output_path, user_id, app)
        )
        thread.daemon = True
        thread.start()
        
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
        response['oss_uploaded'] = task.get('oss_uploaded', False)
    elif task['status'] == 'failed':
        response['error'] = task.get('error')
    
    return jsonify(response)


@renders_bp.route('/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """Download video - 优先使用OSS URL"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        render = Render.query.get(combo_id)
        if not render:
            return jsonify({
                'status': 'failed',
                'error': '视频不存在'
            }), 404
        
        # 优先使用OSS URL（用于下载和文字快剪）
        if render.oss_url:
            return jsonify({
                'status': 'completed',
                'video_url': render.oss_url,
                'mode': 'redirect',
                'source': 'oss'
            })
        
        # 如果没有OSS URL，使用本地文件
        if render.file_path and os.path.exists(render.file_path):
            output_filename = os.path.basename(render.file_path)
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}',
                'download_url': f'/api/download/file?path={output_filename}&name=mixcut_{combo_id}.mp4',
                'mode': 'redirect',
                'source': 'local'
            })
        
        return jsonify({
            'status': 'failed',
            'error': '视频文件不存在，请重新生成'
        }), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@renders_bp.route('/proxy/video', methods=['GET'])
def proxy_video():
    """
    代理下载视频文件（解决CORS跨域问题）
    支持Range请求（206 Partial Content）实现边下边播
    
    参数: url - 要代理下载的视频URL
    用于前端缓存视频到浏览器本地存储
    """
    try:
        video_url = request.args.get('url')
        if not video_url:
            return jsonify({'error': '缺少url参数'}), 400
        
        from flask import Response
        
        logger.info(f"[Proxy] 开始代理下载视频: {video_url}")
        
        # 获取Range请求头（用于边下边播）
        range_header = request.headers.get('Range')
        
        # 判断是本地文件还是远程URL
        if video_url.startswith('http://localhost:3002') or video_url.startswith('/renders/'):
            # 本地文件，直接读取
            if video_url.startswith('http://localhost:3002'):
                file_path = video_url.replace('http://localhost:3002', '')
            else:
                file_path = video_url
            
            file_name = os.path.basename(file_path)
            full_path = os.path.join(RENDERS_FOLDER, file_name)
            
            if not os.path.exists(full_path):
                # 尝试查找匹配的文件（忽略大小写）
                if os.path.exists(RENDERS_FOLDER):
                    for f in os.listdir(RENDERS_FOLDER):
                        if f.lower() == file_name.lower():
                            full_path = os.path.join(RENDERS_FOLDER, f)
                            file_name = f
                            break
                    else:
                        return jsonify({'error': f'文件不存在: {file_name}'}), 404
            
            file_size = os.path.getsize(full_path)
            
            # 处理Range请求（支持边下边播）
            if range_header:
                byte_range = range_header.replace('bytes=', '').split('-')
                start = int(byte_range[0]) if byte_range[0] else 0
                end = int(byte_range[1]) if byte_range[1] else file_size - 1
                length = end - start + 1
                
                def generate_range():
                    with open(full_path, 'rb') as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk_size = min(8192, remaining)
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            yield chunk
                            remaining -= len(chunk)
                
                logger.info(f"[Proxy] Range请求: {start}-{end}/{file_size}")
                
                return Response(
                    generate_range(),
                    status=206,  # Partial Content
                    mimetype='video/mp4',
                    headers={
                        'Content-Disposition': f'inline; filename="{file_name}"',
                        'Access-Control-Allow-Origin': '*',
                        'Content-Range': f'bytes {start}-{end}/{file_size}',
                        'Content-Length': str(length),
                        'Accept-Ranges': 'bytes',
                    }
                )
            
            # 完整文件请求
            def generate_local():
                with open(full_path, 'rb') as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        yield chunk
            
            logger.info(f"[Proxy] 本地文件代理成功: {file_name}, 大小: {file_size}")
            
            return Response(
                generate_local(),
                mimetype='video/mp4',
                headers={
                    'Content-Disposition': f'inline; filename="{file_name}"',
                    'Access-Control-Allow-Origin': '*',
                    'Content-Length': str(file_size),
                    'Accept-Ranges': 'bytes',
                }
            )
        else:
            # 远程URL（如OSS），通过requests代理
            import requests
            
            # 转发Range头到远程服务器
            headers = {}
            if range_header:
                headers['Range'] = range_header
            
            response = requests.get(video_url, stream=True, timeout=120, headers=headers)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', 'video/mp4')
            content_length = response.headers.get('Content-Length')
            content_range = response.headers.get('Content-Range')
            
            resp_headers = {
                'Content-Disposition': 'inline',
                'Access-Control-Allow-Origin': '*',
                'Accept-Ranges': 'bytes',
            }
            if content_length:
                resp_headers['Content-Length'] = content_length
            if content_range:
                resp_headers['Content-Range'] = content_range
            
            def generate_remote():
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            logger.info(f"[Proxy] 远程视频代理成功")
            
            return Response(
                generate_remote(),
                status=response.status_code,
                mimetype=content_type,
                headers=resp_headers
            )
        
    except Exception as e:
        import traceback
        logger.error(f"[Proxy] 代理下载视频失败: {e}")
        logger.error(f"[Proxy] 详细错误: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


def server_concat_task(task_id, combo_id, unified_files, output_path, user_id=None, app=None):
    """
    服务器高质量拼接任务（视频①）
    拼接完成后上传到OSS，供ASR和导出使用
    """
    if app is None:
        from app_new import create_app
        app = create_app()
    
    with app.app_context():
        db.app = app
        
        render_tasks[task_id] = {
            'id': task_id,
            'combo_id': combo_id,
            'status': 'processing',
            'progress': 0,
            'output_path': output_path,
            'type': 'server_concat'
        }
        
        try:
            render_tasks[task_id]['progress'] = 30
            # 使用高质量参数拼接
            success = fast_concat_videos(unified_files, output_path, quality='high')
            
            if success and os.path.exists(output_path):
                render_tasks[task_id]['progress'] = 70
                
                # 更新数据库：标记服务器视频处理中
                try:
                    render = Render.query.get(combo_id)
                    if render:
                        render.server_video_status = 'processing'
                        db.session.commit()
                except Exception as db_error:
                    print(f"[SERVER_RENDER] 数据库更新失败: {db_error}")
                    db.session.rollback()
                
                # 上传到OSS
                def oss_callback(oss_url, success):
                    if success and oss_url:
                        render_tasks[task_id]['oss_url'] = oss_url
                        render_tasks[task_id]['status'] = 'completed'
                        render_tasks[task_id]['progress'] = 100
                        
                        # 更新数据库
                        with app.app_context():
                            try:
                                render = Render.query.get(combo_id)
                                if render:
                                    render.server_video_url = oss_url
                                    render.server_video_status = 'completed'
                                    db.session.commit()
                                    print(f"[SERVER_RENDER] 视频①已生成并上传: {combo_id} -> {oss_url}")
                            except Exception as e:
                                print(f"[SERVER_RENDER] 更新数据库失败: {e}")
                                db.session.rollback()
                    else:
                        render_tasks[task_id]['status'] = 'failed'
                        render_tasks[task_id]['error'] = 'OSS上传失败'
                        
                        with app.app_context():
                            try:
                                render = Render.query.get(combo_id)
                                if render:
                                    render.server_video_status = 'failed'
                                    db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                
                try:
                    user = User.query.get(user_id) if user_id else None
                except:
                    user = None
                
                print(f"[SERVER_RENDER] 开始上传视频①到OSS: {combo_id}")
                oss_client.upload_render_async(
                    local_path=output_path,
                    render_id=combo_id,
                    user_id=user_id,
                    user_obj=user,
                    callback=oss_callback
                )
                
            else:
                render_tasks[task_id]['status'] = 'failed'
                render_tasks[task_id]['error'] = 'Concat failed'
                
                with app.app_context():
                    try:
                        render = Render.query.get(combo_id)
                        if render:
                            render.server_video_status = 'failed'
                            db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                
        except Exception as e:
            print(f"[SERVER_RENDER] 任务失败: {e}")
            import traceback
            traceback.print_exc()
            render_tasks[task_id]['status'] = 'failed'
            render_tasks[task_id]['error'] = str(e)
            
            with app.app_context():
                try:
                    render = Render.query.get(combo_id)
                    if render:
                        render.server_video_status = 'failed'
                        db.session.commit()
                except Exception as e:
                    db.session.rollback()


def fast_concat_copy(unified_files, output_path):
    """
    秒级拼接视频（-c copy 不重新编码）
    用于生成本地FFmpeg高质量视频（视频①）
    """
    import uuid
    if not unified_files:
        return False
    
    list_file = os.path.join(RENDERS_FOLDER, f"list_{uuid.uuid4().hex[:8]}.txt")
    with open(list_file, 'w') as f:
        for filepath in unified_files:
            abs_path = os.path.abspath(filepath)
            f.write(f"file '{abs_path}'\n")
    
    try:
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',           # 不重新编码，秒级完成
            '-movflags', '+faststart',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[fast_concat_copy] FFmpeg error: {result.stderr}")
        return result.returncode == 0
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


@renders_bp.route('/combinations/<combo_id>/server-render', methods=['POST'])
def start_server_render(combo_id):
    """
    启动本地FFmpeg秒级拼接（视频①）
    
    流程：
    1. 同步秒级拼接（-c copy，立即完成）
    2. 同步上传OSS（等待上传完成）
    3. 返回OSS URL（用于ASR/导出）
    """
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
        
        # 检查是否已有OSS视频
        if render.server_video_url:
            return jsonify({
                'status': 'completed',
                'video_url': render.server_video_url,
                'message': '视频①已存在'
            })
        
        # 获取素材文件（优先使用unified_path，已经是统一格式）
        material_ids = json.loads(render.material_ids)
        material_files = []
        
        for mat_id in material_ids:
            material = Material.query.get(mat_id)
            if material and material.user_id == user_id:
                if material.unified_path and os.path.exists(material.unified_path):
                    material_files.append(material.unified_path)
                elif material.file_path and os.path.exists(material.file_path):
                    material_files.append(material.file_path)
        
        if not material_files:
            return jsonify({'error': '素材文件不存在'}), 404
        
        # ========== 同步秒级拼接（-c copy） ==========
        timestamp = int(time.time())
        output_filename = f"combo_{combo_id}_{timestamp}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        print(f"[server-render] 开始秒级拼接: {combo_id}")
        success = fast_concat_copy(material_files, output_path)
        
        if not success or not os.path.exists(output_path):
            return jsonify({'error': '本地FFmpeg秒级拼接失败'}), 500
        
        print(f"[server-render] 秒级拼接完成: {output_path}")
        
        # 更新数据库：保存本地文件路径
        render.file_path = output_path
        render.server_video_status = 'uploading'
        db.session.commit()
        
        # ========== 同步上传OSS（等待完成） ==========
        print(f"[server-render] 开始同步上传OSS: {combo_id}")
        
        oss_url = None
        try:
            user_obj = User.query.get(user_id)
            # 使用同步上传（阻塞等待）
            oss_url = oss_client.upload_render(
                local_path=output_path,
                render_id=combo_id,
                user_id=user_id,
                user_obj=user_obj
            )
            print(f"[server-render] OSS上传完成: {combo_id} -> {oss_url}")
        except Exception as e:
            print(f"[server-render] OSS上传失败: {combo_id} - {e}")
            return jsonify({
                'status': 'local_ready',
                'video_url': f"http://localhost:3002/renders/{output_filename}",
                'error': f'OSS上传失败: {str(e)}'
            }), 500
        
        if oss_url:
            # 更新数据库：保存OSS URL
            render.server_video_url = oss_url
            render.server_video_status = 'completed'
            db.session.commit()
            
            return jsonify({
                'status': 'completed',
                'video_url': oss_url,  # OSS URL，可直接用于ASR
                'message': '本地FFmpeg秒级拼接完成，OSS上传完成'
            })
        else:
            return jsonify({
                'status': 'failed',
                'error': 'OSS上传返回空URL'
            }), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@renders_bp.route('/combinations/<combo_id>/server-render/status', methods=['GET'])
def get_server_render_status(combo_id):
    """获取视频①（本地FFmpeg高质量视频）的状态"""
    try:
        render = Render.query.get(combo_id)
        if not render:
            return jsonify({'error': '组合不存在'}), 404
        
        # 检查OSS是否已完成
        if render.server_video_url:
            return jsonify({
                'status': 'completed',
                'video_url': render.server_video_url,
                'progress': 100
            })
        
        # 检查本地文件是否已生成
        if render.file_path and os.path.exists(render.file_path):
            local_url = f"http://localhost:3002/renders/{os.path.basename(render.file_path)}"
            return jsonify({
                'status': 'local_ready',
                'video_url': local_url,
                'progress': 50,
                'message': '本地FFmpeg拼接完成，OSS上传中'
            })
        
        return jsonify({
            'status': render.server_video_status or 'pending',
            'progress': 0
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
