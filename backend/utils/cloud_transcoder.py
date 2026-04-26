"""
阿里云云端转码模块
使用ICE SubmitTranscodeJob 服务进行高质量视频转码
官方文档: https://help.aliyun.com/zh/ims/developer-reference/transcoding-task
"""
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 阿里云SDK
try:
    from alibabacloud_ice20201109.client import Client as ICEClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_ice20201109 import models as ice_models
    ICE_SDK_AVAILABLE = True
except ImportError:
    ICE_SDK_AVAILABLE = False
    logger.warning("阿里云ICE SDK未安装，云端转码功能将不可用")


def create_ice_client():
    """创建ICE客户端"""
    if not ICE_SDK_AVAILABLE:
        raise RuntimeError("阿里云ICE SDK未安装")

    from config import ICE_CONFIG

    # ICE转码服务只支持杭州地域
    region = 'cn-hangzhou'

    config = open_api_models.Config(
        access_key_id=ICE_CONFIG['access_key_id'],
        access_key_secret=ICE_CONFIG['access_key_secret']
    )
    config.endpoint = f"ice.{region}.aliyuncs.com"
    return ICEClient(config)


def get_transcode_template_id(quality: str) -> str:
    """
    获取转码模板ID
    使用阿里云ICE系统预设的窄带高清2.0转码模板（画质更好）
    文档: https://help.aliyun.com/zh/ims/developer-reference/preset-template-description
    """
    # 窄带高清2.0 - 画质优先模板（MP4-H.264）
    # 相比普通模板，画质更好，码率更优
    # S00000003-102221: 480P 画质优先 (≤850kbps)
    # S00000003-102231: 720P 画质优先 (≤1300kbps)
    # S00000003-102241: 1080P 画质优先 (≤1950kbps)
    templates = {
        'low': 'S00000003-102221',      # 480P 画质优先
        'medium': 'S00000003-102231',   # 720P 画质优先
        'high': 'S00000003-102241',     # 1080P 画质优先
        'ultra': 'S00000003-102241',    # 1080P 画质优先
    }
    return templates.get(quality, 'S00000003-102241')


def submit_transcode_job(
    input_url: str,
    output_url: str,
    quality: str = 'high',
    user_id: str = 'anonymous'
) -> str:
    """
    提交云端转码任务
    使用 SubmitTranscodeJob 接口（官方推荐）
    
    Args:
        input_url: 输入视频URL（OSS地址）
        output_url: 输出视频URL（OSS地址）
        quality: 转码质量（low/medium/high/ultra）
        user_id: 用户ID
    
    Returns:
        job_id: 转码任务ID（ParentJobId）
    """
    if not ICE_SDK_AVAILABLE:
        raise RuntimeError("阿里云ICE SDK未安装")
    
    client = create_ice_client()
    
    # 获取转码模板ID
    template_id = get_transcode_template_id(quality)
    
    # 构建转码请求
    # 参考官方文档: https://help.aliyun.com/zh/ims/developer-reference/transcoding-task
    request = ice_models.SubmitTranscodeJobRequest(
        name=f"transcode_{user_id}_{int(time.time())}",
        # 输入信息
        input_group=[
            ice_models.SubmitTranscodeJobRequestInputGroup(
                type='OSS',
                media=input_url
            )
        ],
        # 输出信息
        output_group=[
            ice_models.SubmitTranscodeJobRequestOutputGroup(
                output=ice_models.SubmitTranscodeJobRequestOutputGroupOutput(
                    type='OSS',
                    media=output_url
                ),
                process_config=ice_models.SubmitTranscodeJobRequestOutputGroupProcessConfig(
                    transcode=ice_models.SubmitTranscodeJobRequestOutputGroupProcessConfigTranscode(
                        template_id=template_id
                    )
                )
            )
        ]
    )
    
    # 发送提交任务请求
    response = client.submit_transcode_job(request)
    
    # 提取任务ID
    job_id = response.body.transcode_parent_job.parent_job_id
    
    logger.info(f"云端转码任务提交成功: job_id={job_id}, quality={quality}, template={template_id}")
    logger.info(f"  输入: {input_url}")
    logger.info(f"  输出: {output_url}")
    
    return job_id


def get_transcode_status(job_id: str) -> Dict[str, Any]:
    """
    查询转码任务状态
    
    Args:
        job_id: 转码任务ID（ParentJobId）
    
    Returns:
        {
            'status': 'Success' | 'Fail' | 'Processing' | 'Submitted',
            'progress': 0-100,
            'output_url': str | None,
            'error': str | None
        }
    """
    if not ICE_SDK_AVAILABLE:
        raise RuntimeError("阿里云ICE SDK未安装")
    
    client = create_ice_client()
    
    # 构造查询任务请求
    request = ice_models.GetTranscodeJobRequest(
        parent_job_id=job_id
    )
    
    # 发送查询任务情况请求
    response = client.get_transcode_job(request)
    
    job = response.body.transcode_parent_job
    
    result = {
        'status': job.status,
        'progress': getattr(job, 'percent', 0),
        'output_url': None,
        'error': None
    }
    
    if job.status == 'Success':
        # 获取输出URL
        if job.output_group and len(job.output_group) > 0:
            output = job.output_group[0]
            if output.output:
                result['output_url'] = output.output.media
    elif job.status == 'Fail':
        result['error'] = getattr(job, 'message', '转码失败')
    
    return result


def transcode_video_sync(
    input_url: str,
    output_url: str,
    quality: str = 'high',
    user_id: str = 'anonymous',
    timeout: int = 1800
) -> str:
    """
    同步转码视频（阻塞等待完成）
    
    Args:
        input_url: 输入视频URL
        output_url: 输出视频URL
        quality: 转码质量
        user_id: 用户ID
        timeout: 超时时间（秒）
    
    Returns:
        output_url: 转码后的视频URL
    
    Raises:
        TimeoutError: 转码超时
        RuntimeError: 转码失败
    """
    job_id = submit_transcode_job(input_url, output_url, quality, user_id)
    
    start_time = time.time()
    poll_interval = 5  # 初始轮询间隔5秒
    
    while time.time() - start_time < timeout:
        status = get_transcode_status(job_id)
        
        logger.info(f"转码进度: {status['progress']}% - {status['status']}")
        
        if status['status'] == 'Success':
            logger.info(f"转码完成: {status['output_url']}")
            return status['output_url']
        elif status['status'] == 'Fail':
            raise RuntimeError(f"转码失败: {status['error']}")
        
        # 指数退避
        time.sleep(poll_interval)
        poll_interval = min(poll_interval * 1.2, 30)
    
    raise TimeoutError(f"转码超时（>{timeout}秒）")


# 全局转码任务存储（用于异步查询）
transcode_tasks = {}


def submit_transcode_async(
    input_url: str,
    output_url: str,
    quality: str = 'high',
    user_id: str = 'anonymous',
    render_id: str = None
) -> str:
    """
    异步提交转码任务
    
    Args:
        render_id: 关联的render_id，用于转码完成后更新数据库
    
    Returns:
        task_id: 本地任务ID（用于查询状态）
    """
    task_id = str(uuid.uuid4())
    
    job_id = submit_transcode_job(input_url, output_url, quality, user_id)
    
    transcode_tasks[task_id] = {
        'job_id': job_id,
        'status': 'processing',
        'progress': 0,
        'output_url': None,
        'error': None,
        'input_url': input_url,
        'output_url': output_url,
        'start_time': time.time(),
        'render_id': render_id  # 存储render_id用于后续更新
    }
    
    return task_id


def get_async_transcode_status(task_id: str) -> Dict[str, Any]:
    """获取异步转码任务状态"""
    if task_id not in transcode_tasks:
        return {'status': 'not_found', 'error': '任务不存在'}
    
    task = transcode_tasks[task_id]
    
    # 如果已经完成或失败，直接返回
    if task['status'] in ['completed', 'failed']:
        return task.copy()
    
    # 查询云端状态
    try:
        cloud_status = get_transcode_status(task['job_id'])
        task['status'] = cloud_status['status'].lower()
        task['progress'] = cloud_status['progress']
        
        if cloud_status['status'] == 'Success':
            task['status'] = 'completed'
            task['output_url'] = cloud_status['output_url']
        elif cloud_status['status'] == 'Fail':
            task['status'] = 'failed'
            task['error'] = cloud_status['error']
    except Exception as e:
        logger.error(f"查询转码状态失败: {e}")
        task['error'] = str(e)
    
    return task.copy()
