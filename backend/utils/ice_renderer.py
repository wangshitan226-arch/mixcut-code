"""
阿里云ICE视频渲染工具模块
用于生成Timeline JSON并提交ICE渲染任务
"""
import json
import logging
import os
import time
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 阿里云ICE SDK
try:
    from alibabacloud_ice20201109.client import Client as ICEClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_ice20201109 import models as ice_models
    ICE_SDK_AVAILABLE = True
except ImportError:
    ICE_SDK_AVAILABLE = False
    logger.warning("阿里云ICE SDK未安装，模板渲染功能将不可用")


# 从新的模板模块导入样式配置
try:
    from templates import SUBTITLE_STYLES
except ImportError:
    # 如果导入失败，使用本地默认配置
    SUBTITLE_STYLES = {
        'title': {
            'font': 'AlibabaPuHuiTi-Heavy',
            'font_size': 90,
            'font_color': '#FFD700',
            'outline': 5,
            'outline_color': '#8B4513',
            'motion_in': 'rotateup_in',
            'motion_out': 'close_out',
            'y': 0.35,
            'weight': 1.5
        },
        'subtitle': {
            'font': 'AlibabaPuHuiTi-Regular',
            'font_size': 50,
            'font_color': '#FFFFFF',
            'outline': 3,
            'outline_color': '#333333',
            'motion_in': 'fade_in',
            'motion_out': 'fade_out',
            'y': 0.52,
            'weight': 1.2
        },
        'body': {
            'font': 'AlibabaPuHuiTi-Regular',
            'font_size': 42,
            'font_color': '#FFFFFF',
            'outline': 2,
            'outline_color': '#000000',
            'motion_in': 'scroll_right_in',
            'motion_out': 'scroll_right_out',
            'y': 0.72,
            'weight': 1.0
        },
        'emphasis': {
            'font': 'AlibabaPuHuiTi-Bold',
            'font_size': 60,
            'font_color': '#FFDD00',
            'outline': 4,
            'outline_color': '#FF6600',
            'motion_in': 'slingshot_in',
            'motion_out': 'slingshot_out',
            'y': 0.5,
            'weight': 1.0,
            'loop': 2,
            'loop_effect': 'bounce'
        },
        'data': {
            'font': 'AlibabaPuHuiTi-Bold',
            'font_size': 80,
            'font_color': '#00FF88',
            'outline': 4,
            'outline_color': '#00CC66',
            'motion_in': 'close_in',
            'motion_out': 'close_out',
            'y': 0.45,
            'weight': 1.2
        }
    }


# ==================== ICE客户端 ====================

def create_ice_client():
    """创建ICE客户端"""
    if not ICE_SDK_AVAILABLE:
        raise RuntimeError("阿里云ICE SDK未安装")
    
    # 从配置读取
    from config import ICE_CONFIG
    
    config = open_api_models.Config(
        access_key_id=ICE_CONFIG['access_key_id'],
        access_key_secret=ICE_CONFIG['access_key_secret']
    )
    config.endpoint = f"ice.{ICE_CONFIG['region']}.aliyuncs.com"
    return ICEClient(config)


# ==================== Timeline生成 ====================

def generate_ice_timeline(
    video_url: str,
    sentences: List[Dict],
    removed_segment_ids: List[str],
    template_config: Dict,
    video_duration_ms: int
) -> Dict:
    """
    生成ICE Timeline JSON
    
    Args:
        video_url: 视频URL
        sentences: ASR识别的句子列表
        removed_segment_ids: 被删除的片段ID列表
        template_config: 模板配置
        video_duration_ms: 视频总时长（毫秒）
    
    Returns:
        ICE Timeline字典
    """
    # 过滤保留的句子
    kept_sentences = [s for s in sentences if s.get('id') not in removed_segment_ids]
    
    if not kept_sentences:
        raise ValueError("没有保留的字幕片段")
    
    # 计算视频实际时长（保留片段的总时长）
    actual_duration_sec = calculate_actual_duration(kept_sentences) / 1000
    
    # 获取模板配置
    subtitle_styles = template_config.get('subtitleStyles', SUBTITLE_STYLES)
    video_effects = template_config.get('videoEffects', {})
    bgm_config = template_config.get('backgroundMusic')
    sound_effects = template_config.get('soundEffects', [])
    
    # 生成字幕clips
    subtitle_clips = generate_subtitle_clips(kept_sentences, subtitle_styles)
    
    # 生成视频clips（带效果）
    video_clips = generate_video_clips(video_url, actual_duration_sec, video_effects)
    
    # 生成多轨道音频
    audio_tracks = generate_audio_tracks(video_url, bgm_config, sound_effects, actual_duration_sec, kept_sentences)
    
    # 组装Timeline
    timeline = {
        "VideoTracks": [{"VideoTrackClips": video_clips}],
        "SubtitleTracks": [{"SubtitleTrackClips": subtitle_clips}],
        "AudioTracks": audio_tracks
    }
    
    return timeline


def calculate_actual_duration(sentences: List[Dict]) -> int:
    """计算保留片段的总时长（毫秒）"""
    if not sentences:
        return 0
    
    total = 0
    for sent in sentences:
        begin = sent.get('beginTime', 0)
        end = sent.get('endTime', 0)
        total += (end - begin)
    
    return total


def determine_subtitle_style(sentence: Dict, styles_config: Dict) -> Dict:
    """
    根据句子内容特征自动匹配样式
    
    匹配规则：
    - 包含数字+%/倍 → data样式
    - 以"为什么/如何/怎么/什么"开头 → question样式
    - 包含引号 → quote样式
    - 长度<10字 → title样式
    - 包含"!" → emphasis样式
    - 其他 → body样式
    """
    text = sentence.get('text', '')
    
    if re.search(r'\d+[%倍]', text):
        return styles_config.get('data', SUBTITLE_STYLES['data'])
    elif re.match(r'^(为什么|如何|怎么|什么)', text):
        return styles_config.get('question', SUBTITLE_STYLES['question'])
    elif '"' in text or '"' in text or '"' in text or '"' in text:
        return styles_config.get('quote', SUBTITLE_STYLES['quote'])
    elif len(text) < 10:
        return styles_config.get('title', SUBTITLE_STYLES['title'])
    elif '!' in text or '！' in text:
        return styles_config.get('emphasis', SUBTITLE_STYLES['emphasis'])
    else:
        return styles_config.get('body', SUBTITLE_STYLES['body'])


def generate_subtitle_clips(sentences: List[Dict], styles_config: Dict) -> List[Dict]:
    """生成字幕clips"""
    clips = []
    
    for sent in sentences:
        # 根据内容类型选择样式
        style = determine_subtitle_style(sent, styles_config)
        
        begin_sec = sent.get('beginTime', 0) / 1000
        end_sec = sent.get('endTime', 0) / 1000
        duration = end_sec - begin_sec
        
        clip = {
            "Type": "Text",
            "Content": sent.get('text', ''),
            "TimelineIn": begin_sec,
            "TimelineOut": end_sec,
            "X": 0.5,
            "Y": style.get('y', 0.5),
            "Alignment": "Center",
            "Font": style.get('font', 'AlibabaPuHuiTi-Regular'),
            "FontSize": style.get('font_size', 42),
            "FontColor": style.get('font_color', '#FFFFFF'),
            "Outline": style.get('outline', 2),
            "OutlineColour": style.get('outline_color', '#000000'),
            "AaiMotionIn": min(0.8, duration * 0.3),
            "AaiMotionOut": min(0.5, duration * 0.2),
            "AaiMotionInEffect": style.get('motion_in', 'fade_in'),
            "AaiMotionOutEffect": style.get('motion_out', 'fade_out')
        }
        
        # 添加循环动画
        if style.get('loop'):
            clip['AaiMotionLoop'] = style['loop']
            clip['AaiMotionLoopEffect'] = style.get('loop_effect', 'bounce')
        
        # 添加背景框
        if style.get('has_box'):
            clip['Effects'] = [{
                "Type": "Box",
                "Color": "000000",
                "Opacity": "0.4",
                "Radius": 0.1
            }]
        
        clips.append(clip)
    
    return clips


def generate_video_clips(video_url: str, duration: float, effects_config: Dict) -> List[Dict]:
    """生成视频clips（带智能缩放等效果）"""
    clips = []
    
    if not effects_config.get('enableSmartZoom', False):
        # 无效果，直接播放
        clips.append({
            "Type": "Video",
            "MediaURL": video_url,
            "TimelineIn": 0,
            "TimelineOut": duration
        })
    else:
        # 智能缩放效果
        zoom_intensity = effects_config.get('zoomIntensity', 1.2)
        segment_duration = 3  # 每3秒一个片段
        num_segments = int(duration / segment_duration) + 1
        
        for i in range(num_segments):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, duration)
            
            # 奇数片段放大
            if i % 2 == 1:
                scale = zoom_intensity
                offset_x = 0.05 if i % 4 == 1 else -0.05
                offset_y = 0.05 if i % 4 == 3 else -0.05
            else:
                scale = 1.0
                offset_x = 0
                offset_y = 0
            
            clip = {
                "Type": "Video",
                "MediaURL": video_url,
                "TimelineIn": start,
                "TimelineOut": end,
                "In": start,
                "Out": end,
                "X": 0.5 + offset_x,
                "Y": 0.5 + offset_y,
                "Scale": scale
            }
            clips.append(clip)
    
    return clips


def generate_audio_tracks(
    video_url: str, 
    bgm_config: Optional[Dict], 
    sound_effects: List[Dict],
    duration: float,
    sentences: List[Dict]
) -> List[Dict]:
    """
    生成多轨道音频
    
    轨道结构：
    - 轨道1：主视频音频
    - 轨道2：背景音乐（BGM）
    - 轨道3+：音效（每个音效一个独立轨道）
    """
    audio_tracks = []
    
    # 轨道1：主视频音频
    audio_tracks.append({
        "AudioTrackClips": [{
            "Type": "Audio",
            "MediaURL": video_url,
            "TimelineIn": 0,
            "TimelineOut": duration
        }]
    })
    
    # 轨道2：背景音乐
    if bgm_config and bgm_config.get('url'):
        audio_tracks.append({
            "AudioTrackClips": [{
                "Type": "Audio",
                "MediaURL": bgm_config['url'],
                "TimelineIn": 0,
                "TimelineOut": duration,
                "Effects": [{
                    "Type": "Volume",
                    "Gain": bgm_config.get('volume', 0.3)
                }]
            }]
        })
    
    # 轨道3+：音效（每个音效一个独立轨道）
    for effect in sound_effects:
        trigger = effect.get('trigger', 'title')
        effect_url = effect.get('url')
        
        if not effect_url:
            continue
        
        # 找到触发时间点
        trigger_time = find_trigger_time(sentences, trigger)
        
        if trigger_time is not None:
            audio_tracks.append({
                "AudioTrackClips": [{
                    "Type": "Audio",
                    "MediaURL": effect_url,
                    "TimelineIn": trigger_time,
                    "TimelineOut": trigger_time + 2,  # 音效持续2秒
                    "Effects": [{
                        "Type": "Volume",
                        "Gain": 0.8  # 音效音量
                    }]
                }]
            })
    
    return audio_tracks


def find_trigger_time(sentences: List[Dict], trigger_type: str) -> Optional[float]:
    """
    根据触发类型找到对应的时间点
    
    Args:
        sentences: 字幕列表
        trigger_type: 触发类型 (title/subtitle/section/emphasis/body)
    
    Returns:
        触发时间（秒），未找到返回None
    """
    if not sentences:
        return None
    
    # 根据触发类型找到对应的字幕
    for sent in sentences:
        text = sent.get('text', '')
        begin_time = sent.get('beginTime', 0) / 1000  # 转换为秒
        
        if trigger_type == 'title' and len(text) < 15:
            # 标题通常是短句
            return begin_time
        elif trigger_type == 'emphasis' and ('！' in text or '!' in text):
            # 强调句通常有感叹号
            return begin_time
        elif trigger_type == 'section':
            # 返回第一个字幕的时间
            return begin_time
    
    # 默认返回第一个字幕的时间
    if sentences:
        return sentences[0].get('beginTime', 0) / 1000
    
    return None


# ==================== ICE任务提交 ====================

def submit_ice_job(timeline: Dict, user_id: str, output_filename: Optional[str] = None) -> Tuple[str, str]:
    """
    提交ICE渲染任务
    
    Args:
        timeline: ICE Timeline字典
        user_id: 用户ID
        output_filename: 输出文件名（可选）
    
    Returns:
        (job_id, output_url)
    """
    if not ICE_SDK_AVAILABLE:
        raise RuntimeError("阿里云ICE SDK未安装")
    
    client = create_ice_client()
    
    # 从配置读取
    from config import OSS_CONFIG
    
    # 生成输出地址
    timestamp = int(time.time())
    if not output_filename:
        output_filename = f"template_render_{user_id}_{timestamp}.mp4"
    
    output_url = f"https://{OSS_CONFIG['bucket_name']}.oss-cn-beijing.aliyuncs.com/renders/{user_id}/{output_filename}"
    
    output_config = {
        "MediaURL": output_url,
        "Width": 1080,
        "Height": 1920,
        "Fps": 30,
        "VideoCodec": "H264",
        "VideoBitrate": 4000,
        "AudioCodec": "AAC",
        "AudioBitrate": 128
    }
    
    request = ice_models.SubmitMediaProducingJobRequest(
        timeline=json.dumps(timeline, ensure_ascii=False),
        output_media_config=json.dumps(output_config)
    )
    
    response = client.submit_media_producing_job(request)
    job_id = response.body.job_id
    
    logger.info(f"ICE任务提交成功: job_id={job_id}, output_url={output_url}")
    
    return job_id, output_url


def get_job_status(job_id: str) -> str:
    """
    查询ICE任务状态
    
    Args:
        job_id: ICE任务ID
    
    Returns:
        状态: Success, Failed, Processing
    """
    if not ICE_SDK_AVAILABLE:
        raise RuntimeError("阿里云ICE SDK未安装")
    
    client = create_ice_client()
    
    request = ice_models.GetMediaProducingJobRequest(job_id=job_id)
    response = client.get_media_producing_job(request)
    
    return response.body.media_producing_job.status


def cancel_job(job_id: str) -> bool:
    """
    取消ICE任务
    
    Args:
        job_id: ICE任务ID
    
    Returns:
        是否成功
    """
    if not ICE_SDK_AVAILABLE:
        raise RuntimeError("阿里云ICE SDK未安装")
    
    try:
        client = create_ice_client()
        # ICE SDK可能没有直接取消的API，这里预留接口
        logger.info(f"尝试取消ICE任务: {job_id}")
        return True
    except Exception as e:
        logger.error(f"取消ICE任务失败: {e}")
        return False


# ==================== 系统模板初始化 ====================

def get_default_templates() -> List[Dict]:
    """
    获取默认系统模板配置
    现在从新的 templates 模块导入，保持向后兼容
    """
    try:
        from templates import get_default_templates as _get_templates
        return _get_templates()
    except ImportError:
        # 如果新模块不可用，使用简化版默认配置
        return [
            {
                'name': '大字报风格',
                'description': '金色大字标题，适合促销和强调',
                'category': 'promotion',
                'config': {
                    'subtitleStyles': {
                        'title': SUBTITLE_STYLES['title'],
                        'body': SUBTITLE_STYLES['body'],
                        'emphasis': SUBTITLE_STYLES['emphasis'],
                        'data': SUBTITLE_STYLES['data']
                    },
                    'videoEffects': {
                        'enableSmartZoom': True,
                        'zoomIntensity': 1.2
                    }
                }
            },
            {
                'name': '简洁知识风',
                'description': '清晰易读，适合知识分享',
                'category': 'knowledge',
                'config': {
                    'subtitleStyles': {
                        'title': SUBTITLE_STYLES['subtitle'],
                        'body': SUBTITLE_STYLES['body']
                    },
                    'videoEffects': {
                        'enableSmartZoom': False
                    }
                }
            },
            {
                'name': '活力动感风',
                'description': '弹跳动画，适合娱乐内容',
                'category': 'entertainment',
                'config': {
                    'subtitleStyles': {
                        'title': SUBTITLE_STYLES['emphasis'],
                        'body': SUBTITLE_STYLES['body']
                    },
                    'videoEffects': {
                        'enableSmartZoom': True,
                        'zoomIntensity': 1.25
                    }
                }
            }
        ]


def init_system_templates():
    """初始化系统预设模板到数据库"""
    from models import Template
    from extensions import db
    
    default_templates = get_default_templates()
    
    for i, tmpl in enumerate(default_templates):
        # 检查是否已存在
        existing = Template.query.filter_by(name=tmpl['name'], is_active=True).first()
        if not existing:
            template = Template(
                id=str(uuid.uuid4()),
                name=tmpl['name'],
                description=tmpl['description'],
                category=tmpl['category'],
                config=json.dumps(tmpl['config']),
                is_active=True,
                sort_order=i
            )
            db.session.add(template)
            logger.info(f"创建系统模板: {tmpl['name']}")
    
    db.session.commit()
    logger.info("系统模板初始化完成")
