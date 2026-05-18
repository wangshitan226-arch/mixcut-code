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
        
        from models import DigitalHuman
        combinations = []
        for render in renders:
            file_exists = False
            video_url = None
            oss_uploading = False
            oss_uploaded = False
            
            if render.file_path and os.path.exists(render.file_path):
                file_exists = True
                video_url = f'/renders/{os.path.basename(render.file_path)}'
            elif render.oss_url:
                file_exists = True
                video_url = render.oss_url
                oss_uploaded = True
            elif render.server_video_url:
                file_exists = True
                video_url = render.server_video_url
                oss_uploaded = True
            
            if not render.oss_url and not oss_uploaded:
                for task_id, task in render_tasks.items():
                    if task.get('combo_id') == render.id and task.get('status') == 'completed' and not task.get('oss_uploaded'):
                        oss_uploading = True
                        break
            
            tag = render.tag or ''
            if '数字人' in tag:
                video_type = 'digital_human'
            elif '口播' in tag or '智剪' in tag:
                video_type = 'real_human_cut'
            else:
                video_type = 'mixcut'
            
            try:
                material_ids = json.loads(render.material_ids)
            except Exception:
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
                else:
                    dh = DigitalHuman.query.get(mat_id)
                    if dh:
                        materials_data.append({
                            'id': dh.id,
                            'type': 'digital_human',
                            'url': dh.video_url or '',
                            'thumbnail': dh.cover_url or '',
                            'duration': '',
                            'name': dh.title
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
                'preview_url': video_url,
                'oss_url': render.oss_url,
                'oss_uploading': oss_uploading,
                'oss_uploaded': bool(render.oss_url),
                'server_video_url': render.server_video_url,
                'videoType': video_type,
            }
            combinations.append(combo_data)
        
        return jsonify({'combinations': combinations})
        
    except Exception as e:
        logger.error(f"[Renders] 获取渲染列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@renders_bp.route('/renders/<render_id>', methods=['GET'])
def get_render_by_id(render_id):
    if render_id in render_tasks:
        task = render_tasks[render_id]
        response = {
            'id': render_id,
            'status': task['status'],
            'progress': task.get('progress', 0),
            'stage': task.get('stage', ''),
            'type': task.get('type', ''),
        }
        if task['status'] == 'completed':
            response['video_url'] = task.get('video_url')
            response['oss_uploaded'] = task.get('oss_uploaded', False)
            response['duration'] = task.get('duration')
            combo_id = task.get('combo_id')
            if combo_id:
                render = Render.query.get(combo_id)
                if render:
                    response['combo_id'] = render.id
                    response['tag'] = render.tag
                    response['duration'] = render.duration
                    response['duration_seconds'] = render.duration_seconds
                    response['oss_url'] = render.oss_url
                    response['thumbnail'] = render.thumbnail
        elif task['status'] == 'failed':
            response['error'] = task.get('error')
        return jsonify(response)
    
    render = Render.query.get(render_id)
    if not render:
        return jsonify({'error': '渲染记录不存在'}), 404
    
    video_url = None
    if render.file_path and os.path.exists(render.file_path):
        video_url = f'/renders/{os.path.basename(render.file_path)}'
    elif render.oss_url:
        video_url = render.oss_url
    elif render.server_video_url:
        video_url = render.server_video_url
    
    tag = render.tag or ''
    if '数字人' in tag:
        video_type = 'digital_human'
    elif '口播' in tag or '智剪' in tag:
        video_type = 'real_human_cut'
    else:
        video_type = 'mixcut'
    
    try:
        material_ids = json.loads(render.material_ids)
    except Exception:
        material_ids = []
    
    materials_data = []
    from models import DigitalHuman
    for mat_id in material_ids:
        material = Material.query.get(mat_id)
        if material and material.user_id == render.user_id:
            materials_data.append({
                'id': material.id,
                'type': material.type,
                'url': f'/uploads/{os.path.basename(material.file_path)}',
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(material.thumbnail_path)}',
                'duration': material.duration,
                'name': material.original_name
            })
        else:
            dh = DigitalHuman.query.get(mat_id)
            if dh:
                materials_data.append({
                    'id': dh.id,
                    'type': 'digital_human',
                    'url': dh.video_url or '',
                    'thumbnail': dh.cover_url or '',
                    'duration': '',
                    'name': dh.title
                })
    
    return jsonify({
        'id': render.id,
        'index': render.combo_index,
        'materials': materials_data,
        'thumbnail': render.thumbnail,
        'duration': render.duration,
        'duration_seconds': render.duration_seconds,
        'tag': render.tag,
        'preview_status': 'completed' if video_url else 'pending',
        'preview_url': video_url,
        'oss_url': render.oss_url,
        'server_video_url': render.server_video_url,
        'status': render.status,
        'videoType': video_type,
    })


# ==================== 数字人视频渲染 ====================

@renders_bp.route('/digital-human/render', methods=['POST'])
def render_digital_human_video():
    """
    数字人视频渲染端点

    两种模式:
    - digital_human_pure: 纯口播，TTS + VideoRetalk，无字幕包装
    - digital_human_mix: 口播混剪，TTS + VideoRetalk + ICE字幕/BGM/音效

    请求体:
    {
        "user_id": "xxx",
        "digital_human_id": "xxx",
        "template_id": "xxx",
        "text": "要合成的文本",
        "voice_id": "可选",
        "video_type": "digital_human_pure" | "digital_human_mix"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        dh_id = data.get('digital_human_id')
        template_id = data.get('template_id')
        text = data.get('text', '').strip()
        voice_id = data.get('voice_id')
        video_type = data.get('video_type', 'digital_human_pure')
        sentences = data.get('sentences', [])

        if not user_id or not dh_id:
            return jsonify({'error': '缺少user_id或digital_human_id'}), 400
        if not text and not sentences:
            return jsonify({'error': '请输入文本或提供字幕数据'}), 400

        from models import DigitalHuman, Template
        dh = DigitalHuman.query.get(dh_id)
        if not dh:
            return jsonify({'error': '数字人不存在'}), 404
        if not dh.video_url:
            return jsonify({'error': '数字人未设置模板视频'}), 400

        effective_voice = voice_id or dh.voice_id
        if not effective_voice:
            return jsonify({'error': '未指定声音'}), 400

        template_config = {}
        if template_id:
            template = Template.query.get(template_id)
            if template:
                try:
                    template_config = json.loads(template.config) if isinstance(template.config, str) else template.config
                except Exception:
                    template_config = {}

        render_type = template_config.get('renderType', 'pure' if video_type == 'digital_human_pure' else 'mix')

        task_id = f"dh_render_{uuid.uuid4().hex[:8]}"
        app = current_app._get_current_object()

        render_tasks[task_id] = {
            'id': task_id,
            'status': 'processing',
            'progress': 0,
            'type': 'digital_human_render',
            'video_type': video_type,
            'render_type': render_type
        }

        def _render_pipeline():
            with app.app_context():
                try:
                    from utils.videoretalk import videoretalk_tool

                    render_tasks[task_id]['progress'] = 10
                    render_tasks[task_id]['stage'] = 'synthesizing'

                    from routes.digital_human import _synthesize_speech
                    tts_model = 'cosyvoice-v2' if effective_voice.endswith('_v2') else 'cosyvoice-v1'
                    audio_url = _synthesize_speech(text, effective_voice, tts_model)
                    if not audio_url:
                        render_tasks[task_id]['status'] = 'failed'
                        render_tasks[task_id]['error'] = 'TTS语音合成失败'
                        return

                    render_tasks[task_id]['progress'] = 30
                    render_tasks[task_id]['stage'] = 'videoretalk'

                    avatar_config = template_config.get('avatarConfig', {})
                    video_extension = avatar_config.get('video_extension', False)

                    vr_result = videoretalk_tool.generate_avatar_video(
                        video_url=dh.video_url,
                        audio_url=audio_url,
                        video_extension=video_extension,
                        wait=True
                    )

                    if not vr_result.get('success'):
                        render_tasks[task_id]['status'] = 'failed'
                        render_tasks[task_id]['error'] = f"VideoRetalk失败: {vr_result.get('error', '未知错误')}"
                        return

                    avatar_video_url = vr_result.get('video_url')
                    video_duration = vr_result.get('duration', 0)

                    logger.info(f"[DH-Render] VideoRetalk完成: type={render_type}, duration={video_duration}s")

                    if render_type == 'pure':
                        render_tasks[task_id]['status'] = 'completed'
                        render_tasks[task_id]['progress'] = 100
                        render_tasks[task_id]['video_url'] = avatar_video_url
                        render_tasks[task_id]['duration'] = video_duration

                        dh_obj = DigitalHuman.query.get(dh_id)
                        if dh_obj:
                            dh_obj.generated_video_url = avatar_video_url
                            dh_obj.generated_video_duration = video_duration
                            dh_obj.videoretalk_status = 'completed'
                            db.session.commit()

                        try:
                            from models import Render
                            render_id = f"dh_{uuid.uuid4().hex[:12]}"
                            combo_count = Render.query.filter_by(user_id=user_id).count()
                            thumbnail = dh.cover_url
                            if not thumbnail:
                                thumbnail = _extract_thumbnail_from_video(avatar_video_url, user_id)
                            render_record = Render(
                                id=render_id,
                                user_id=user_id,
                                combo_index=combo_count,
                                material_ids=json.dumps([dh_id]),
                                tag='数字人视频',
                                duration=f"{int(video_duration)//60:02d}:{int(video_duration)%60:02d}" if video_duration else "00:00",
                                duration_seconds=video_duration or 0,
                                thumbnail=thumbnail,
                                oss_url=avatar_video_url,
                                status='completed',
                                server_video_url=avatar_video_url,
                                server_video_status='completed',
                            )
                            db.session.add(render_record)
                            db.session.commit()
                            render_tasks[task_id]['combo_id'] = render_record.id
                            logger.info(f"[DH-Render] 结果已保存到Render: {render_record.id}")
                        except Exception as e:
                            logger.error(f"[DH-Render] 保存Render记录失败: {e}")

                        return

                    render_tasks[task_id]['progress'] = 60
                    render_tasks[task_id]['stage'] = 'compositing'

                    from utils.ice_renderer import (
                        generate_digital_human_timeline,
                        submit_ice_job,
                        ICE_SDK_AVAILABLE
                    )

                    if not sentences:
                        est_duration_ms = int(video_duration * 1000) if video_duration else len(text) * 200
                        sentences = [{
                            'id': f's_{i}',
                            'text': chunk,
                            'start': i * 3000,
                            'end': min((i + 1) * 3000, est_duration_ms)
                        } for i, chunk in enumerate(_split_text(text, 20))]

                    if ICE_SDK_AVAILABLE:
                        try:
                            timeline = generate_digital_human_timeline(
                                avatar_video_url=avatar_video_url,
                                sentences=sentences,
                                template_config=template_config,
                                video_duration_ms=int(video_duration * 1000) if video_duration else None
                            )

                            job_id, submit_media_id = submit_ice_job(
                                timeline, user_id,
                                output_filename=f"dh_{dh_id[:8]}_{int(time.time())}.mp4"
                            )

                            render_tasks[task_id]['progress'] = 80
                            render_tasks[task_id]['stage'] = 'ice_rendering'
                            render_tasks[task_id]['ice_job_id'] = job_id

                            for _ in range(120):
                                time.sleep(10)
                                status = get_job_status(job_id)
                                if status == 'Success':
                                    from config import ICE_CONFIG
                                    from alibabacloud_ice20201109.client import Client as ICEClient
                                    from alibabacloud_tea_openapi import models as open_api_models

                                    conf = open_api_models.Config(access_key_id=ICE_CONFIG['access_key_id'], access_key_secret=ICE_CONFIG['access_key_secret'])
                                    conf.endpoint = f"ice.{ICE_CONFIG['region']}.aliyuncs.com"
                                    ice_client = ICEClient(conf)

                                    from alibabacloud_ice20201109 import models as ice_models
                                    req = ice_models.GetMediaInfoRequest(media_id=submit_media_id)
                                    media_info = ice_client.get_media_info(req)

                                    final_url = None
                                    if media_info.body and media_info.body.media_info:
                                        final_url = media_info.body.media_info.media_url

                                    render_tasks[task_id]['status'] = 'completed'
                                    render_tasks[task_id]['progress'] = 100
                                    render_tasks[task_id]['video_url'] = final_url or avatar_video_url

                                    try:
                                        from models import Render
                                        render_id = f"dh_{uuid.uuid4().hex[:12]}"
                                        combo_count = Render.query.filter_by(user_id=user_id).count()
                                        thumbnail = dh.cover_url
                                        if not thumbnail:
                                            thumbnail = _extract_thumbnail_from_video(final_url or avatar_video_url, user_id)
                                        render_record = Render(
                                            id=render_id,
                                            user_id=user_id,
                                            combo_index=combo_count,
                                            material_ids=json.dumps([dh_id]),
                                            tag='数字人混剪',
                                            duration=f"{int(video_duration)//60:02d}:{int(video_duration)%60:02d}" if video_duration else "00:00",
                                            duration_seconds=video_duration or 0,
                                            thumbnail=thumbnail,
                                            oss_url=final_url or avatar_video_url,
                                            status='completed',
                                            server_video_url=final_url or avatar_video_url,
                                            server_video_status='completed',
                                        )
                                        db.session.add(render_record)
                                        db.session.commit()
                                        render_tasks[task_id]['combo_id'] = render_record.id
                                    except Exception as e:
                                        logger.error(f"[DH-Render] 保存Render记录失败: {e}")

                                    return
                                elif status == 'Failed':
                                    break

                        except Exception as e:
                            logger.error(f"[DH-Render] ICE渲染失败，使用原始视频: {e}")

                    render_tasks[task_id]['status'] = 'completed'
                    render_tasks[task_id]['progress'] = 100
                    render_tasks[task_id]['video_url'] = avatar_video_url

                    try:
                        from models import Render
                        render_id = f"dh_{uuid.uuid4().hex[:12]}"
                        combo_count = Render.query.filter_by(user_id=user_id).count()
                        thumbnail = dh.cover_url
                        if not thumbnail:
                            thumbnail = _extract_thumbnail_from_video(avatar_video_url, user_id)
                        render_record = Render(
                            id=render_id,
                            user_id=user_id,
                            combo_index=combo_count,
                            material_ids=json.dumps([dh_id]),
                            tag='数字人视频',
                            duration=f"{int(video_duration)//60:02d}:{int(video_duration)%60:02d}" if video_duration else "00:00",
                            duration_seconds=video_duration or 0,
                            thumbnail=thumbnail,
                            oss_url=avatar_video_url,
                            status='completed',
                            server_video_url=avatar_video_url,
                            server_video_status='completed',
                        )
                        db.session.add(render_record)
                        db.session.commit()
                        render_tasks[task_id]['combo_id'] = render_record.id
                    except Exception as e:
                        logger.error(f"[DH-Render] 保存Render记录失败: {e}")

                except Exception as e:
                    logger.error(f"[DH-Render] 渲染管线异常: {e}")
                    import traceback
                    traceback.print_exc()
                    render_tasks[task_id]['status'] = 'failed'
                    render_tasks[task_id]['error'] = str(e)

        t = threading.Thread(target=_render_pipeline, daemon=True)
        t.start()

        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': 'processing',
            'render_type': render_type,
            'message': f'数字人{"纯口播" if render_type == "pure" else "混剪"}视频渲染已启动'
        })

    except Exception as e:
        logger.error(f"[DH-Render] 请求异常: {e}")
        return jsonify({'error': str(e)}), 500


def _extract_thumbnail_from_video(video_url: str, user_id: str) -> str:
    try:
        tmp_dir = os.path.join(os.path.dirname(__file__), '..', 'tmp')
        os.makedirs(tmp_dir, exist_ok=True)
        thumb_path = os.path.join(tmp_dir, f"thumb_{uuid.uuid4().hex[:8]}.jpg")

        cmd = [
            'ffmpeg', '-y',
            '-i', video_url,
            '-ss', '00:00:01',
            '-vframes', '1',
            '-q:v', '2',
            '-vf', 'scale=300:400:force_original_aspect_ratio=decrease,pad=300:400:(ow-iw)/2:(oh-ih)/2',
            thumb_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not os.path.exists(thumb_path):
            logger.warning(f"[Thumbnail] ffmpeg提取缩略图失败: {result.stderr[:200]}")
            return None

        if oss_client.enabled:
            oss_key = f"users/{user_id}/thumbnails/dh_{uuid.uuid4().hex[:8]}.jpg"
            with open(thumb_path, 'rb') as f:
                oss_client.bucket.put_object(oss_key, f.read())
            if oss_client.cdn_domain:
                thumb_url = f"https://{oss_client.cdn_domain}/{oss_key}"
            else:
                thumb_url = f"https://{oss_client.bucket_name}.{oss_client.endpoint}/{oss_key}"
            try:
                os.remove(thumb_path)
            except Exception:
                pass
            logger.info(f"[Thumbnail] 缩略图上传OSS: {thumb_url}")
            return thumb_url

        thumb_url = f"/thumbnails/{os.path.basename(thumb_path)}"
        return thumb_url

    except Exception as e:
        logger.error(f"[Thumbnail] 提取缩略图异常: {e}")
        return None


def _split_text(text: str, max_len: int = 20):
    """将文本按标点或最大长度分割"""
    import re
    parts = re.split(r'([，。！？；：、\n,\.!\?;:])', text)
    chunks = []
    current = ''
    for part in parts:
        current += part
        if len(current) >= max_len or part in '，。！？；：\n,.!?;:':
            if current.strip():
                chunks.append(current.strip())
            current = ''
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


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
        'progress': task.get('progress', 0),
        'stage': task.get('stage', ''),
        'type': task.get('type', ''),
    }
    
    if task['status'] == 'completed':
        response['video_url'] = task.get('video_url')
        response['oss_uploaded'] = task.get('oss_uploaded', False)
        response['duration'] = task.get('duration')
    elif task['status'] == 'failed':
        response['error'] = task.get('error')
    
    return jsonify(response)


@renders_bp.route('/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """
    Download video - 强制使用OSS URL
    
    修复说明：
    1. 下载必须使用服务器FFmpeg渲染后上传到OSS的公网URL
    2. 不能使用客户端浏览器渲染的Blob URL（效果差）
    3. 不能使用服务器本地文件路径（CORS问题，且生产环境无法访问）
    4. 如果没有OSS URL，触发服务器渲染并返回processing状态
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
        if not render:
            return jsonify({
                'status': 'failed',
                'error': '视频不存在'
            }), 404
        
        # 优先级1: server_video_url（服务器FFmpeg高质量视频URL）
        if render.server_video_url:
            return jsonify({
                'status': 'completed',
                'video_url': render.server_video_url,
                'mode': 'redirect',
                'source': 'server_oss'
            })
        
        # 优先级2: oss_url（普通OSS URL）
        if render.oss_url:
            return jsonify({
                'status': 'completed',
                'video_url': render.oss_url,
                'mode': 'redirect',
                'source': 'oss'
            })
        
        # 优先级3: 触发服务器渲染+上传OSS
        # 检查是否已经在处理中
        for task_id, task in render_tasks.items():
            if task.get('combo_id') == combo_id and task.get('type') == 'server_concat':
                if task['status'] == 'processing':
                    return jsonify({
                        'status': 'processing',
                        'progress': task.get('progress', 0),
                        'message': '视频正在准备中，请稍后再试'
                    })
                elif task['status'] == 'completed' and task.get('oss_url'):
                    return jsonify({
                        'status': 'completed',
                        'video_url': task['oss_url'],
                        'mode': 'redirect',
                        'source': 'server_oss'
                    })
        
        # 启动服务器渲染任务
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
            return jsonify({
                'status': 'failed',
                'error': '素材文件不存在'
            }), 404
        
        # 生成输出路径
        timestamp = int(time.time())
        output_filename = f"combo_{combo_id}_{timestamp}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        # 启动服务器高质量渲染任务
        task_id = f"server_render_{uuid.uuid4().hex[:8]}"
        app = current_app._get_current_object()
        
        thread = threading.Thread(
            target=server_concat_task,
            args=(task_id, combo_id, material_files, output_path, user_id, app)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'processing',
            'task_id': task_id,
            'progress': 0,
            'message': '视频正在准备中，请稍后再试'
        })
        
    except Exception as e:
        import traceback
        current_app.logger.error(f"[Download] 下载处理失败: {e}")
        current_app.logger.error(f"[Download] 详细错误: {traceback.format_exc()}")
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
