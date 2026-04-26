"""
OSS上传相关路由
支持客户端直传OSS（使用STS临时签名）
"""
from flask import Blueprint, request, jsonify
import uuid
import time
import json
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
from models import KaipaiEdit
from extensions import db
from utils.oss import oss_client

oss_upload_bp = Blueprint('oss_upload', __name__, url_prefix='/api')


def get_iso_8601(expire):
    """获取ISO 8601格式的时间字符串"""
    return datetime.utcfromtimestamp(expire).strftime('%Y-%m-%dT%H:%M:%SZ')


@oss_upload_bp.route('/oss/sts-token', methods=['POST'])
def get_sts_token():
    """
    获取OSS直传的STS临时签名
    
    前端使用此签名直接上传文件到OSS，无需经过后端
    
    请求参数：
    - dir: 上传目录前缀（如 'users/{user_id}/renders/'）
    - expire_seconds: 签名过期时间（默认300秒）
    - bucket: 指定bucket（默认使用配置中的bucket，可选'mixcut'使用杭州bucket）
    
    返回：
    - accessid: AccessKey ID
    - policy: 编码后的Policy
    - signature: 签名
    - dir: 上传目录
    - host: OSS bucket域名
    - expire: 过期时间戳
    """
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id', 'anonymous')
        dir_prefix = data.get('dir', f"users/{user_id}/client-renders/")
        expire_seconds = data.get('expire_seconds', 300)
        bucket_name = data.get('bucket', oss_client.bucket_name)
        
        if not oss_client.enabled:
            return jsonify({'error': 'OSS未启用'}), 503
        
        # 根据bucket确定endpoint
        if bucket_name == 'mixcut':
            endpoint = 'oss-cn-hangzhou.aliyuncs.com'
        else:
            endpoint = oss_client.endpoint
        
        # 生成过期时间
        expire = int(time.time()) + expire_seconds
        
        # 构建Policy
        policy_dict = {
            'expiration': get_iso_8601(expire),
            'conditions': [
                {'bucket': bucket_name},
                ['content-length-range', 0, 2048 * 1024 * 1024],  # 最大2GB
                ['starts-with', '$key', dir_prefix]
            ]
        }
        
        # 编码Policy
        policy = base64.b64encode(json.dumps(policy_dict).encode()).decode()
        
        # 计算签名
        signature = base64.b64encode(
            hmac.new(
                oss_client.access_key_secret.encode(),
                policy.encode(),
                hashlib.sha1
            ).digest()
        ).decode()
        
        # 构建host
        host = f"https://{bucket_name}.{endpoint}"
        
        return jsonify({
            'accessid': oss_client.access_key_id,
            'policy': policy,
            'signature': signature,
            'dir': dir_prefix,
            'host': host,
            'expire': expire,
            'callback': None  # 可选：配置OSS回调
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@oss_upload_bp.route('/oss/upload-callback', methods=['POST'])
def oss_upload_callback():
    """
    OSS上传回调接口
    
    当前端直传OSS完成后，OSS可以回调此接口通知后端
    或者前端手动调用此接口通知后端上传完成
    
    请求参数：
    - edit_id: 剪辑任务ID
    - oss_url: OSS文件URL
    - file_size: 文件大小
    - duration: 视频时长
    """
    try:
        data = request.get_json(silent=True) or {}
        edit_id = data.get('edit_id')
        oss_url = data.get('oss_url')
        file_size = data.get('file_size', 0)
        duration = data.get('duration', 0)
        
        if not edit_id or not oss_url:
            return jsonify({'error': '缺少edit_id或oss_url'}), 400
        
        # 更新数据库
        edit = KaipaiEdit.query.get(edit_id)
        if not edit:
            return jsonify({'error': 'Edit not found'}), 404
        
        # 保存客户端渲染结果到OSS的URL
        # 注意：这里不修改output_video_url，而是保存为intermediate_url
        # 因为后续可能还有ICE模板渲染
        edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
        edit_params['client_render_url'] = oss_url
        edit_params['client_render_size'] = file_size
        edit_params['client_render_duration'] = duration
        edit.edit_params = json.dumps(edit_params, ensure_ascii=False)
        
        db.session.commit()
        
        return jsonify({
            'edit_id': edit_id,
            'status': 'uploaded',
            'oss_url': oss_url,
            'message': '客户端渲染结果已上传到OSS'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@oss_upload_bp.route('/kaipai/<edit_id>/client-render', methods=['POST'])
def submit_client_render(edit_id):
    """
    提交客户端渲染结果并触发ICE模板渲染
    
    前端客户端渲染完成后，调用此接口：
    1. 如果已选择模板：使用客户端渲染的OSS URL作为输入，提交ICE任务
    2. 如果没有模板：直接保存结果
    
    请求参数：
    - oss_url: 客户端渲染结果在OSS上的URL
    - duration: 视频时长（秒）
    """
    try:
        data = request.get_json(silent=True) or {}
        oss_url = data.get('oss_url')
        duration = data.get('duration', 0)
        
        if not oss_url:
            return jsonify({'error': '缺少oss_url'}), 400
        
        edit = KaipaiEdit.query.get(edit_id)
        if not edit:
            return jsonify({'error': 'Edit not found'}), 404
        
        # 保存客户端渲染结果
        edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
        edit_params['client_render_url'] = oss_url
        edit_params['client_render_duration'] = duration
        edit.edit_params = json.dumps(edit_params, ensure_ascii=False)
        
        # 检查是否选择了模板
        if edit.template_id:
            # 有模板：使用客户端渲染结果作为输入，提交ICE任务
            return _submit_ice_with_client_render(edit, oss_url, duration)
        else:
            # 无模板：直接保存结果
            edit.output_video_url = oss_url
            edit.status = 'completed'
            db.session.commit()
            
            return jsonify({
                'edit_id': edit_id,
                'status': 'completed',
                'output_url': oss_url,
                'message': '客户端渲染结果已保存（无模板）'
            })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _submit_ice_with_client_render(edit, client_render_url, duration):
    """
    使用客户端渲染结果提交ICE模板渲染
    
    流程：
    1. 使用客户端渲染的OSS URL作为视频输入
    2. 生成ICE Timeline
    3. 提交ICE任务
    """
    from utils.ice_renderer import (
        generate_ice_timeline,
        submit_ice_job
    )
    from models import Template
    import threading
    
    template = Template.query.get(edit.template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    template_config = json.loads(template.config) if template.config else {}
    
    # 获取ASR结果
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    sentences = asr_result.get('sentences', [])
    
    # 获取编辑参数
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    removed_ids = [s['id'] for s in removed_segments]
    
    # 创建任务
    task_id = str(uuid.uuid4())
    from routes.kaipai import _update_render_task
    _update_render_task(task_id, **{
        'status': 'processing',
        'progress': 0,
        'output_url': None,
        'error': None,
        'is_template': True,
        'use_client_render': True
    })
    
    edit.status = 'processing'
    db.session.commit()
    
    from flask import current_app
    app = current_app._get_current_object()
    
    def render_with_client_video():
        """使用客户端渲染的视频提交ICE任务"""
        with app.app_context():
            try:
                _update_render_task(task_id, progress=10)
                
                # 生成ICE Timeline（使用客户端渲染的URL）
                # 注意：客户端已经做了裁剪，所以不需要再裁剪
                # 直接使用客户端渲染结果作为输入
                timeline = generate_ice_timeline(
                    video_url=client_render_url,
                    sentences=sentences,
                    removed_segment_ids=[],  # 客户端已经裁剪，不需要再删除
                    template_config=template_config,
                    video_duration_ms=int(duration * 1000)
                )
                
                _update_render_task(task_id, progress=30)
                
                # 提交ICE任务
                output_filename = f"kaipai_template_{edit.id}_{int(time.time())}.mp4"
                job_id, output_url = submit_ice_job(timeline, edit.user_id, output_filename)
                
                _update_render_task(task_id, progress=50, ice_job_id=job_id)
                
                # 轮询ICE任务状态
                from utils.ice_renderer import get_job_status
                import time
                
                poll_interval = 2
                max_interval = 10
                
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
                            current_progress = render_tasks.get(task_id, {}).get('progress', 50)
                            new_progress = min(95, current_progress + 5)
                            _update_render_task(task_id, progress=new_progress)
                        
                        time.sleep(poll_interval)
                        poll_interval = min(poll_interval * 1.5, max_interval)
                        
                    except Exception as e:
                        time.sleep(5)
                
            except Exception as e:
                error_msg = str(e)
                _update_render_task(task_id, status='failed', error=error_msg)
                try:
                    with db.session.begin():
                        edit_update = KaipaiEdit.query.get(edit.id)
                        if edit_update:
                            edit_update.status = 'failed'
                except Exception:
                    pass
    
    # 启动渲染线程
    from routes.kaipai import render_executor
    render_executor.submit(render_with_client_video)
    
    return jsonify({
        'edit_id': edit.id,
        'status': 'processing',
        'task_id': task_id,
        'use_template': True,
        'use_client_render': True,
        'template_name': template.name,
        'message': '客户端渲染结果已提交，开始ICE模板渲染'
    })
