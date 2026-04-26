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

    logger.info(f"ICE本地裁剪模式: 原始片段 {len(sentences)} 个，保留 {len(kept_sentences)} 个")
    logger.info(f"删除的片段ID: {removed_segment_ids}")

    # 计算视频实际时长（保留片段的总时长）
    actual_duration_sec = calculate_actual_duration(kept_sentences) / 1000
    logger.info(f"保留片段总时长: {actual_duration_sec:.2f}s")

    # 获取模板配置
    subtitle_styles = template_config.get('subtitleStyles', SUBTITLE_STYLES)
    video_effects = template_config.get('videoEffects', {})
    bgm_config = template_config.get('backgroundMusic')
    sound_effects = template_config.get('soundEffects', [])

    logger.info(f"开始生成字幕clips，使用 {len(subtitle_styles)} 种样式")
    # 生成字幕clips（单轨道）
    subtitle_clips = generate_subtitle_clips(kept_sentences, subtitle_styles)
    logger.info(f"字幕clips生成完成: {len(subtitle_clips)} 个")
    
    # 生成视频clips（带效果）
    video_clips = generate_video_clips(video_url, actual_duration_sec, video_effects)
    
    # 生成多轨道音频
    audio_tracks = generate_audio_tracks(video_url, bgm_config, sound_effects, actual_duration_sec, kept_sentences)
    
    # 组装Timeline
    timeline = {
        "VideoTracks": [{"VideoTrackClips": video_clips}],
        "SubtitleTracks": [{"SubtitleTrackClips": subtitle_clips}],
        "AudioTracks": audio_tracks,
        "VideoSummary": {
            "Title": "智能剪辑视频",
            "Description": f"包含 {len(subtitle_clips)} 个字幕片段",
            "Duration": actual_duration_sec,
            "SubtitleCount": len(subtitle_clips),
            "HasBGM": bgm_config is not None and bgm_config.get('url') is not None,
            "HasSoundEffects": len(sound_effects) > 0
        }
    }

    logger.info(f"Timeline组装完成: {len(video_clips)} 视频clips, {len(subtitle_clips)} 字幕clips, {len(audio_tracks)} 音频轨道")
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


def calculate_keep_segments(sentences: List[Dict], removed_segment_ids: List[str], video_duration_ms: int) -> List[Tuple[int, int]]:
    """
    计算保留的时间段（用于ICE直接裁剪）
    
    Args:
        sentences: ASR识别的句子列表
        removed_segment_ids: 被删除的片段ID列表
        video_duration_ms: 视频总时长（毫秒）
    
    Returns:
        保留时间段列表，每个元素为 (start_ms, end_ms)
    """
    if not sentences:
        return [(0, video_duration_ms)]
    
    # 按时间排序
    sorted_sentences = sorted(sentences, key=lambda s: s.get('beginTime', 0))
    
    # 获取被删除的时间段
    removed_ranges = []
    for sent in sorted_sentences:
        if sent.get('id') in removed_segment_ids:
            begin = sent.get('beginTime', 0)
            end = sent.get('endTime', 0)
            # 添加缓冲时间（前后各150ms）
            removed_ranges.append((max(0, begin - 150), min(video_duration_ms, end + 150)))
    
    # 合并重叠的删除段
    if not removed_ranges:
        # 没有被删除的，保留整个视频
        return [(0, video_duration_ms)]
    
    removed_ranges.sort(key=lambda x: x[0])
    merged_removed = [removed_ranges[0]]
    for current in removed_ranges[1:]:
        last = merged_removed[-1]
        if current[0] <= last[1]:
            merged_removed[-1] = (last[0], max(last[1], current[1]))
        else:
            merged_removed.append(current)
    
    # 计算保留的时间段
    keep_segments = []
    current_time = 0
    
    for removed_start, removed_end in merged_removed:
        if current_time < removed_start:
            keep_segments.append((current_time, removed_start))
        current_time = max(current_time, removed_end)
    
    # 保留最后一段
    if current_time < video_duration_ms:
        keep_segments.append((current_time, video_duration_ms))
    
    return keep_segments


def generate_opening_title_clip(title: str, title_config: Dict = None) -> Dict:
    """
    生成开场标题Clip
    
    从模板配置读取样式，默认：
    - 思源黑体、120号、黑字加粗
    - 底部黄色填充
    - 中间偏上方位置
    - 持续5秒
    - 弹入动画
    """
    if not title:
        return None
    
    # 默认配置
    default_config = {
        'enabled': True,
        'font': 'SourceHanSansCN-Bold',
        'font_size': 120,
        'font_color': '#000000',
        'font_weight': 'Bold',
        'background_color': '#FFD700',
        'x': 0,
        'y': 300,
        'alignment': 'Center',
        'duration': 5,
        'motion_in': 'bounce_in',
        'motion_out': 'fade_out'
    }
    
    # 使用模板配置覆盖默认值
    config = default_config.copy()
    if title_config:
        config.update(title_config)
    
    # 如果禁用则不生成
    if not config.get('enabled', True):
        return None
    
    # 根据阿里云ICE文档，字体样式应该放在 FontFace 对象中
    font_face = {}
    if config.get('font_weight') == 'Bold':
        font_face['Bold'] = True
    
    clip = {
        "Type": "Text",
        "Content": title,
        "TimelineIn": 0,
        "TimelineOut": config['duration'],
        "X": config['x'],
        "Y": config['y'],
        "Alignment": config['alignment'],
        "Font": config['font'],
        "FontSize": config['font_size'],
        "FontColor": config['font_color'],
        "SizeRequestType": "RealDim",
        "AdaptMode": "AutoWrap",
        "AaiMotionIn": 0.5,
        "AaiMotionOut": 0.3,
        "AaiMotionInEffect": config['motion_in'],
        "AaiMotionOutEffect": config['motion_out']
    }
    
    # 添加 FontFace 配置（如果存在）
    if font_face:
        clip['FontFace'] = font_face
    
    # 优先使用系统花字样式（EffectColorStyle）
    if config.get('effect_color_style'):
        clip['EffectColorStyle'] = config['effect_color_style']
    else:
        # 添加背景效果（使用 SubtitleEffects）
        subtitle_effects = config.get('subtitle_effects', [])
        if subtitle_effects:
            # 处理 subtitle_effects 中的参数，确保符合ICE文档要求
            processed_effects = []
            for effect in subtitle_effects:
                processed_effect = effect.copy()
                # 确保 Opacity 是数字类型
                if 'Opacity' in processed_effect:
                    try:
                        processed_effect['Opacity'] = float(processed_effect['Opacity'])
                    except (ValueError, TypeError):
                        processed_effect['Opacity'] = 1.0
                # 将 XBord/YBord 转换为 Bord（如果存在）
                if 'XBord' in processed_effect or 'YBord' in processed_effect:
                    xbord = processed_effect.pop('XBord', 0)
                    ybord = processed_effect.pop('YBord', 0)
                    # 使用较大的值作为 Bord
                    processed_effect['Bord'] = max(xbord, ybord, 20)
                processed_effects.append(processed_effect)
            clip['SubtitleEffects'] = processed_effects
        elif config.get('background_color'):
            # 兼容旧配置：如果没有 subtitle_effects 但有 background_color
            # 根据阿里云ICE文档，Color 不需要 # 前缀
            color = config['background_color']
            if color.startswith('#'):
                color = color[1:]
            # 黄底黑字效果：使用 Box 类型创建背景
            # 根据官方文档，使用 Bord 而不是 XBord/YBord
            clip['SubtitleEffects'] = [
                {
                    "Type": "Box",
                    "Color": color,
                    "Bord": 30,
                    "Radius": 10
                }
            ]
    
    return clip


def find_keyword_occurrences(
    sentences: List[Dict], 
    keywords: List[str], 
    keep_segments: List[Tuple[int, int]],
    video_duration_sec: float = None,
    max_keywords: int = 4
) -> List[Dict]:
    """
    查找关键词在字幕中出现的时间和位置
    
    Args:
        sentences: ASR句子列表（所有句子，包括被删除的）
        keywords: 关键词列表
        keep_segments: 保留的时间段（用于时间戳重映射）
        video_duration_sec: 视频总时长（秒），用于限制结束时间
        max_keywords: 最大关键词数量（默认4个）
    
    Returns:
        关键词出现记录列表（按时间戳排序，取前max_keywords个）
    """
    all_occurrences = []
    
    # 计算视频总时长（如果未提供）
    if video_duration_sec is None:
        video_duration_sec = sum((end_ms - start_ms) / 1000.0 for start_ms, end_ms in keep_segments)
    
    # 构建时间映射表：计算每个保留片段在时间线上的偏移
    segment_offsets = []
    current_offset = 0.0
    for start_ms, end_ms in keep_segments:
        segment_offsets.append({
            'start': start_ms,
            'end': end_ms,
            'offset': current_offset
        })
        current_offset += (end_ms - start_ms) / 1000.0
    
    def get_remapped_time(original_time_ms):
        """将原始时间（毫秒）映射到裁剪后的时间线（秒）"""
        for seg in segment_offsets:
            if seg['start'] <= original_time_ms < seg['end']:
                relative_time = (original_time_ms - seg['start']) / 1000.0
                return seg['offset'] + relative_time
        return None  # 不在任何保留片段中
    
    # 查找所有关键词的所有出现位置
    for keyword in keywords:
        # 遍历所有句子查找关键词
        for sent in sentences:
            text = sent.get('text', '')
            
            # 跳过无声片段
            if sent.get('type') == 'silence':
                continue
            
            # 精确匹配关键词
            if keyword in text:
                # 找到关键词在句子中的位置
                keyword_index = text.find(keyword)
                
                # 计算关键词在句子中的大致时间位置
                words = sent.get('words', [])
                if words:
                    # 找到关键词对应的word
                    keyword_words = []
                    char_count = 0
                    for word in words:
                        word_text = word.get('text', '')
                        word_begin = word.get('beginTime', 0)
                        word_end = word.get('endTime', 0)
                        
                        # 检查这个词是否在关键词范围内
                        word_start_idx = char_count
                        word_end_idx = char_count + len(word_text)
                        
                        # 如果这个词与关键词有重叠
                        if word_start_idx < keyword_index + len(keyword) and word_end_idx > keyword_index:
                            keyword_words.append({'begin': word_begin, 'end': word_end})
                        
                        char_count += len(word_text)
                    
                    if keyword_words:
                        # 使用第一个匹配word的开始时间
                        keyword_begin_ms = keyword_words[0]['begin']
                    else:
                        # 回退到字数比例
                        total_chars = len(text)
                        char_position = keyword_index
                        time_ratio = char_position / total_chars if total_chars > 0 else 0
                        sent_begin_ms = sent.get('beginTime', 0)
                        sent_end_ms = sent.get('endTime', 0)
                        sent_duration_ms = sent_end_ms - sent_begin_ms
                        keyword_begin_ms = sent_begin_ms + (sent_duration_ms * time_ratio)
                else:
                    # 没有word级别信息，使用句子开始时间
                    keyword_begin_ms = sent.get('beginTime', 0)
                
                # 将原始时间映射到裁剪后的时间线
                keyword_begin = get_remapped_time(keyword_begin_ms)
                
                # 如果关键词不在任何保留片段中，跳过
                if keyword_begin is None:
                    print(f"[DEBUG-ICE] 关键词 '{keyword}' 在 {keyword_begin_ms}ms 处，但该片段已被删除")
                    continue
                
                # 确保结束时间不超过视频时长
                keyword_end = min(keyword_begin + 2, video_duration_sec)
                
                # 如果开始时间已经超过视频时长，跳过
                if keyword_begin >= video_duration_sec:
                    print(f"[DEBUG-ICE] 关键词 '{keyword}' 的开始时间 {keyword_begin:.2f}s 超过视频时长 {video_duration_sec:.2f}s，跳过")
                    continue
                
                all_occurrences.append({
                    'keyword': keyword,
                    'begin_time': keyword_begin,
                    'end_time': keyword_end,
                    'text': text
                })
                print(f"[DEBUG-ICE] 关键词 '{keyword}' 找到！原始时间 {keyword_begin_ms}ms, 重映射后 {keyword_begin:.2f}s")
                break  # 找到第一个出现位置就跳出，继续下一个关键词
    
    # 按时间戳排序，取前max_keywords个
    all_occurrences.sort(key=lambda x: x['begin_time'])
    
    # 特殊处理第4个关键词：使用句子开始时间，避免出现在视频结尾
    if len(all_occurrences) >= 4:
        # 找到第4个关键词的句子开始时间
        fourth_keyword = all_occurrences[3]['keyword']
        for sent in sentences:
            text = sent.get('text', '')
            if sent.get('type') == 'silence':
                continue
            if fourth_keyword in text:
                # 使用句子开始时间
                sent_begin_ms = sent.get('beginTime', 0)
                sentence_start = get_remapped_time(sent_begin_ms)
                if sentence_start is not None and sentence_start < video_duration_sec - 2:
                    all_occurrences[3]['begin_time'] = sentence_start
                    all_occurrences[3]['end_time'] = min(sentence_start + 2, video_duration_sec)
                    print(f"[DEBUG-ICE] 第4个关键词 '{fourth_keyword}' 调整到句子开始: {sentence_start:.2f}s")
                break
    
    occurrences = all_occurrences[:max_keywords]
    
    print(f"[DEBUG-ICE] 共找到 {len(all_occurrences)} 个关键词，取时间戳最早的前 {len(occurrences)} 个")
    for occ in occurrences:
        print(f"[DEBUG-ICE]   - {occ['keyword']}: {occ['begin_time']:.2f}s - {occ['end_time']:.2f}s")
    
    return occurrences


def generate_keyword_flower_clips(keyword_occurrences: List[Dict], keyword_config: Dict = None) -> List[Dict]:
    """
    生成关键词气泡字clips
    
    样式：
    - 从BS0001-000001、BS0001-000002、BS0001-000004、BS0005-000001随机选择且不重复
    - 弹跳进入（bounce_in）
    - 顺时针旋转30度（Angle=330，因为文档说逆时针旋转）
    - 持续2秒
    """
    # 默认配置
    default_config = {
        'enabled': True,
        'font': 'SourceHanSansCN-Bold',
        'font_size': 80,
        'font_color': '#FFFFFF',
        'x': 0.3,
        'y': 0.3,
        'alignment': 'TopLeft',
        'duration': 2,
        'motion_in': 'bounce_in',
        'motion_out': 'fade_out'
    }
    
    # 使用模板配置覆盖默认值
    config = default_config.copy()
    if keyword_config:
        config.update(keyword_config)
    
    # 如果禁用则不生成
    if not config.get('enabled', True):
        return []
    
    # 气泡字样式列表（从用户指定的4个中随机选择且不重复）
    bubble_styles = ['BS0001-000001', 'BS0001-000002', 'BS0001-000004', 'BS0005-000001']
    import random
    random.shuffle(bubble_styles)
    
    clips = []
    
    # 随机决定哪两个气泡字倾斜（生成两个随机索引）
    tilt_indices = set()
    if len(keyword_occurrences) >= 2:
        tilt_indices = set(random.sample(range(len(keyword_occurrences)), 2))
    
    for i, occ in enumerate(keyword_occurrences):
        # 选择气泡字样式（不重复）
        style_index = i % len(bubble_styles)
        bubble_style_id = bubble_styles[style_index]
        
        # 位置错开（使用相对坐标）
        x_pos = config['x'] + (i % 2) * 0.15
        y_pos = config['y'] + (i % 2) * 0.1
        
        # 随机两个倾斜30度，其他正常
        angle = 330 if i in tilt_indices else 0  # 330=顺时针30度, 0=正常
        
        # 气泡字配置
        clip = {
            "Type": "Text",
            "Content": occ['keyword'],
            "TimelineIn": round(occ['begin_time'], 3),
            "TimelineOut": round(occ['begin_time'] + config['duration'], 3),
            "X": x_pos,
            "Y": y_pos,
            "Alignment": config['alignment'],
            "Font": config['font'],
            "FontSize": config['font_size'],
            "FontColor": config['font_color'],
            "BubbleStyleId": bubble_style_id,  # 使用气泡字样式
            "BubbleWidth": 0.3,  # 气泡宽度（相对值）
            "BubbleHeight": 0.18,  # 气泡高度（相对值）
            "Angle": angle,
            "AaiMotionIn": 0.5,
            "AaiMotionOut": 0.3,
            "AaiMotionInEffect": config['motion_in'],
            "AaiMotionOutEffect": config['motion_out']
        }
        clips.append(clip)
        tilt_status = "倾斜30度" if i in tilt_indices else "正常"
        print(f"[DEBUG-ICE] 气泡字clip {i+1}: 关键词='{occ['keyword']}', 样式={bubble_style_id}, {tilt_status}, 时间={occ['begin_time']:.2f}s")
    
    logger.info(f"生成了 {len(clips)} 个关键词气泡字clips")
    return clips


def generate_keyword_sound_effects(keyword_occurrences: List[Dict], keyword_sound_config: Dict = None) -> List[Dict]:
    """
    生成关键词音效clips
    
    样式：
    - 4个音效随机选择且不重复
    - 与关键词出现时间同步
    """
    # 默认配置（4个音效）
    default_config = {
        'enabled': True,
        'sound_urls': [
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/dragon-studio-wow-423653.mp3",
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/u_7xr5ffk4oq-opening-bell-421471.mp3",
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/dragon-studio-pop-402324.mp3",
            "https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/kauasilbershlachparodes-camera-flash-494027.mp3"
        ],
        'duration': 1.5,
        'volume': 0.7
    }
    
    # 使用模板配置覆盖默认值
    config = default_config.copy()
    if keyword_sound_config:
        config.update(keyword_sound_config)
    
    # 如果禁用则不生成
    if not config.get('enabled', True):
        return []
    
    # 随机打乱音效列表（确保不重复）
    import random
    sound_urls = config['sound_urls'].copy()
    random.shuffle(sound_urls)
    
    clips = []
    
    for i, occ in enumerate(keyword_occurrences):
        # 选择音效（不重复，如果关键词多于音效则循环使用）
        effect_url = sound_urls[i % len(sound_urls)]
        
        clip = {
            "Type": "Audio",
            "MediaURL": effect_url,
            "TimelineIn": round(occ['begin_time'], 3),
            "TimelineOut": round(occ['begin_time'] + config['duration'], 3),
            "Effects": [{
                "Type": "Volume",
                "Gain": config['volume']
            }]
        }
        clips.append(clip)
        print(f"[DEBUG-ICE] 音效clip {i+1}: 关键词='{occ['keyword']}', 音效={effect_url.split('/')[-1]}, 时间={occ['begin_time']:.2f}s")
    
    logger.info(f"生成了 {len(clips)} 个关键词音效clips")
    return clips


def generate_ice_timeline_with_crop(
    video_url: str,
    sentences: List[Dict],
    removed_segment_ids: List[str],
    template_config: Dict,
    video_duration_ms: int,
    asr_result: Dict = None
) -> Dict:
    """
    生成ICE Timeline JSON（带In/Out裁剪参数）

    直接在ICE端完成视频裁剪，无需本地FFmpeg处理

    Args:
        video_url: 原始视频URL（OSS地址）
        sentences: ASR识别的句子列表
        removed_segment_ids: 被删除的片段ID列表
        template_config: 模板配置
        video_duration_ms: 视频总时长（毫秒）
        asr_result: ASR完整结果（用于获取标题和关键词）

    Returns:
        ICE Timeline字典
    """
    # 从asr_result中获取标题和关键词
    video_title = None
    keywords = []
    print(f"[DEBUG-ICE] asr_result类型: {type(asr_result)}, 内容: {asr_result}")
    if asr_result and isinstance(asr_result, dict):
        metadata = asr_result.get('metadata', {})
        print(f"[DEBUG-ICE] metadata: {metadata}")
        video_title = metadata.get('title', '')
        keywords = metadata.get('keywords', [])
        print(f"[DEBUG-ICE] 从ASR结果获取标题: '{video_title}'")
        print(f"[DEBUG-ICE] 从ASR结果获取关键词: {keywords}")
    else:
        print(f"[DEBUG-ICE] asr_result为空或不是字典")

    # 过滤保留的句子
    kept_sentences = [s for s in sentences if s.get('id') not in removed_segment_ids]

    if not kept_sentences:
        raise ValueError("没有保留的字幕片段")

    # 计算保留的时间段
    keep_segments = calculate_keep_segments(sentences, removed_segment_ids, video_duration_ms)

    if not keep_segments:
        raise ValueError("没有可保留的视频片段")

    logger.info(f"ICE直接裁剪: 原始片段 {len(sentences)} 个，保留 {len(kept_sentences)} 个，分成 {len(keep_segments)} 个时间段")
    logger.info(f"保留时间段: {keep_segments}")
    logger.info(f"删除的片段ID: {removed_segment_ids}")
    
    # 获取模板配置
    subtitle_styles = template_config.get('subtitleStyles', SUBTITLE_STYLES)
    video_effects = template_config.get('videoEffects', {})
    bgm_config = template_config.get('backgroundMusic')
    sound_effects = template_config.get('soundEffects', [])
    
    # 获取开场标题配置（从模板读取）
    title_config = template_config.get('openingTitle', {})
    print(f"[DEBUG-ICE] 开场标题配置: {title_config}")
    print(f"[DEBUG-ICE] 标题内容: '{video_title}', enabled: {title_config.get('enabled', True)}")
    
    # 获取关键词花字配置（从模板读取）
    keyword_config = template_config.get('keywordFlower', {})
    print(f"[DEBUG-ICE] 关键词花字配置: {keyword_config}")
    print(f"[DEBUG-ICE] 关键词列表: {keywords}, enabled: {keyword_config.get('enabled', True)}")
    
    # 获取关键词音效配置（从模板读取）
    keyword_sound_config = template_config.get('keywordSound', {})
    print(f"[DEBUG-ICE] 关键词音效配置: {keyword_sound_config}")
    
    # 如果关键词音效启用，则禁用旧版soundEffects以避免冲突
    if keyword_sound_config.get('enabled', False):
        print(f"[DEBUG-ICE] 关键词音效已启用，禁用旧版soundEffects")
        sound_effects = []
    
    # 生成视频clips - 只保留基本裁剪，不添加任何视觉效果
    video_clips = []
    timeline_position = 0.0  # 时间线位置（秒）

    for start_ms, end_ms in keep_segments:
        start_sec = start_ms / 1000.0
        end_sec = end_ms / 1000.0
        duration = end_sec - start_sec

        # 基础视频clip，不添加任何放缩、位移等效果
        clip = {
            "Type": "Video",
            "MediaURL": video_url,
            "In": start_sec,                    # 素材入点（裁剪开始）
            "Out": end_sec,                     # 素材出点（裁剪结束）
            "TimelineIn": timeline_position,    # 在时间线上的位置
            "TimelineOut": timeline_position + duration
        }

        video_clips.append(clip)
        timeline_position += duration

    logger.info(f"视频clips生成完成: {len(video_clips)} 个，无放缩/位移效果")
    
    actual_duration_sec = timeline_position
    logger.info(f"视频裁剪后总时长: {actual_duration_sec}s")
    
    # 重新映射字幕时间戳（根据裁剪后的时间线）
    logger.info(f"开始生成字幕clips，使用 {len(subtitle_styles)} 种样式")
    subtitle_clips = generate_subtitle_clips_with_remapping(
        kept_sentences,
        subtitle_styles,
        keep_segments
    )
    logger.info(f"字幕clips生成完成: {len(subtitle_clips)} 个")
    
    # 生成开场标题clip（从模板配置读取）
    print(f"[DEBUG-ICE] 开始生成开场标题，标题='{video_title}'")
    opening_title_clip = generate_opening_title_clip(video_title, title_config)
    if opening_title_clip:
        subtitle_clips.append(opening_title_clip)
        print(f"[DEBUG-ICE] 添加开场标题成功: '{video_title}'")
        print(f"[DEBUG-ICE] 开场标题clip: {opening_title_clip}")
    else:
        print(f"[DEBUG-ICE] 开场标题未生成，标题='{video_title}'")
    
    # 查找关键词出现时间（限制前4个，且不超过视频时长）
    print(f"[DEBUG-ICE] 开始查找关键词出现时间，关键词={keywords}, 句子数={len(kept_sentences)}")
    keyword_occurrences = find_keyword_occurrences(
        kept_sentences, 
        keywords, 
        keep_segments,
        video_duration_sec=actual_duration_sec,
        max_keywords=4
    )
    print(f"[DEBUG-ICE] 找到 {len(keyword_occurrences)} 个关键词出现记录")
    for occ in keyword_occurrences:
        print(f"[DEBUG-ICE]   - {occ['keyword']}: {occ['begin_time']:.2f}s - {occ['end_time']:.2f}s")
    
    # 生成关键词花字clips（从模板配置读取）
    if keyword_occurrences:
        print(f"[DEBUG-ICE] 开始生成关键词花字clips")
        keyword_clips = generate_keyword_flower_clips(keyword_occurrences, keyword_config)
        print(f"[DEBUG-ICE] 生成 {len(keyword_clips)} 个关键词花字clips")
        subtitle_clips.extend(keyword_clips)
    else:
        print(f"[DEBUG-ICE] 没有找到关键词出现记录")
    
    # 生成多轨道音频（使用原始视频URL，ICE会自动裁剪音频）
    audio_tracks = generate_audio_tracks_with_crop(
        video_url, 
        bgm_config, 
        sound_effects, 
        actual_duration_sec, 
        kept_sentences,
        keep_segments
    )
    
    # 添加关键词音效（从模板配置读取）
    if keyword_occurrences:
        keyword_sound_clips = generate_keyword_sound_effects(keyword_occurrences, keyword_sound_config)
        # 为每个音效创建独立的音频轨道，避免混音问题
        for clip in keyword_sound_clips:
            audio_tracks.append({"AudioTrackClips": [clip]})
        if keyword_sound_clips:
            logger.info(f"关键词音效: 创建了 {len(keyword_sound_clips)} 个独立音频轨道")
    
    # 组装Timeline
    # 使用DeepSeek提取的标题，如果没有则使用默认
    final_title = video_title if video_title else "智能剪辑视频"

    timeline = {
        "VideoTracks": [{"VideoTrackClips": video_clips}],
        "SubtitleTracks": [{"SubtitleTrackClips": subtitle_clips}],
        "AudioTracks": audio_tracks,
        "VideoSummary": {
            "Title": final_title,
            "Description": f"包含 {len(subtitle_clips)} 个字幕片段，{len(keep_segments)} 个视频段，{len(keyword_occurrences)} 个关键词",
            "Duration": actual_duration_sec,
            "SubtitleCount": len(subtitle_clips),
            "VideoSegmentCount": len(keep_segments),
            "HasBGM": bgm_config is not None and bgm_config.get('url') is not None,
            "HasSoundEffects": len(sound_effects) > 0,
            "Keywords": keywords,
            "KeywordCount": len(keyword_occurrences)
        }
    }

    logger.info(f"Timeline组装完成: 标题='{final_title}', {len(video_clips)} 视频clips, {len(subtitle_clips)} 字幕clips, {len(keyword_occurrences)} 关键词")
    return timeline


def generate_subtitle_clips_with_remapping(
    sentences: List[Dict],
    styles_config: Dict,
    keep_segments: List[Tuple[int, int]]
) -> List[Dict]:
    """
    生成字幕clips（带时间戳重映射，单轨道）

    由于视频被裁剪拼接，字幕时间戳需要映射到新的时间线
    从模板配置读取样式，字体大小默认为150
    """
    clips = []
    skipped_count = 0
    silence_count = 0

    # 先过滤掉静音段，避免显示"[无声 x.xx s]"这样的字幕
    speech_sentences = []
    for sent in sentences:
        if sent.get('type') == 'silence':
            silence_count += 1
            continue
        # 也过滤掉文本为空或只有空白的情况
        text = sent.get('text', '').strip()
        if not text or text.startswith('[无声'):
            silence_count += 1
            continue
        speech_sentences.append(sent)

    if silence_count > 0:
        logger.info(f"过滤了 {silence_count} 个静音段")

    # 构建时间映射表 - 改进逻辑：确保字幕完全包含在保留段内
    time_mapping = {}  # sent_id -> {'begin': float, 'end': float}
    current_offset = 0.0

    for start_ms, end_ms in keep_segments:
        segment_duration = (end_ms - start_ms) / 1000.0

        for sent in speech_sentences:
            sent_id = sent.get('id')
            sent_begin = sent.get('beginTime', 0)
            sent_end = sent.get('endTime', 0)

            # 检查字幕是否与当前保留段有重叠
            # 条件：字幕开始时间在段内，或字幕结束时间在段内，或字幕完全包含该段
            overlap_start = max(sent_begin, start_ms)
            overlap_end = min(sent_end, end_ms)

            if overlap_start < overlap_end:  # 有重叠
                # 计算该字幕在新时间线上的位置
                relative_start = (overlap_start - start_ms) / 1000.0
                relative_end = (overlap_end - start_ms) / 1000.0

                # 限制在段时长范围内
                relative_start = max(0, min(relative_start, segment_duration))
                relative_end = max(0, min(relative_end, segment_duration))

                if sent_id not in time_mapping:
                    time_mapping[sent_id] = {
                        'begin': current_offset + relative_start,
                        'end': current_offset + relative_end,
                        'sent': sent
                    }
                else:
                    # 如果字幕跨越多个保留段，延长结束时间
                    time_mapping[sent_id]['end'] = current_offset + relative_end

        current_offset += segment_duration

    # 生成字幕clips
    for sent_id, mapped in time_mapping.items():
        begin_sec = mapped['begin']
        end_sec = mapped['end']
        sent = mapped['sent']
        duration = end_sec - begin_sec

        if duration <= 0.1:  # 持续时间太短，跳过
            skipped_count += 1
            continue

        # 从模板获取样式
        style = determine_subtitle_style(sent, styles_config)

        # 确保样式有效
        if not style:
            style = SUBTITLE_STYLES['body']
            logger.warning(f"字幕样式未找到，使用默认body样式: {sent.get('text', '')[:20]}")

        # 构建字幕clip - 从模板读取样式，字体大小默认150
        clip = {
            "Type": "Text",
            "Content": sent.get('text', ''),
            "TimelineIn": round(begin_sec, 3),
            "TimelineOut": round(end_sec, 3),
            "X": style.get('x', 0),
            "Y": style.get('y', 500),
            "Alignment": style.get('alignment', 'TopLeft'),
            "Font": style.get('font', 'SimSun'),
            "FontSize": style.get('font_size', 150),  # 默认150
            "SizeRequestType": style.get('size_request_type', 'RealDim'),
            "FontColor": style.get('font_color', '#FFFFFF'),
            "Outline": style.get('outline', 40),
            "OutlineColour": style.get('outline_color', '#000000'),
            "AdaptMode": style.get('adapt_mode', 'AutoWrap'),
            "AaiMotionIn": min(0.8, duration * 0.3),
            "AaiMotionOut": min(0.5, duration * 0.2),
            "AaiMotionInEffect": style.get('motion_in', 'fade_in'),
            "AaiMotionOutEffect": style.get('motion_out', 'fade_out')
        }

        # 添加花字效果（如果模板配置有）
        if style.get('effect_color_style'):
            clip['EffectColorStyle'] = style['effect_color_style']

        clips.append(clip)

    if skipped_count > 0:
        logger.info(f"跳过了 {skipped_count} 个持续时间太短的字幕片段")

    logger.info(f"生成了 {len(clips)} 个字幕clips")
    return clips


def generate_audio_tracks_with_crop(
    video_url: str, 
    bgm_config: Optional[Dict], 
    sound_effects: List[Dict],
    duration: float,
    sentences: List[Dict],
    keep_segments: List[Tuple[int, int]]
) -> List[Dict]:
    """
    生成多轨道音频（带裁剪参数）
    
    主视频音频使用相同的In/Out参数进行裁剪
    """
    audio_tracks = []
    
    # 轨道1：主视频音频（使用裁剪参数）
    video_audio_clips = []
    timeline_position = 0.0
    
    for start_ms, end_ms in keep_segments:
        start_sec = start_ms / 1000.0
        end_sec = end_ms / 1000.0
        segment_duration = end_sec - start_sec
        
        clip = {
            "Type": "Audio",
            "MediaURL": video_url,
            "In": start_sec,
            "Out": end_sec,
            "TimelineIn": timeline_position,
            "TimelineOut": timeline_position + segment_duration
        }
        video_audio_clips.append(clip)
        timeline_position += segment_duration
    
    audio_tracks.append({"AudioTrackClips": video_audio_clips})
    logger.info(f"音频轨道1（主视频音频）: {len(video_audio_clips)} 个clips")
    # 打印视频原声音轨的详细信息用于调试
    for i, clip in enumerate(video_audio_clips):
        logger.info(f"  视频音频clip {i+1}: In={clip['In']:.2f}s, Out={clip['Out']:.2f}s, "
                   f"TimelineIn={clip['TimelineIn']:.2f}s, TimelineOut={clip['TimelineOut']:.2f}s")

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
        logger.info(f"音频轨道2（BGM）: {bgm_config['url'][:50]}...，音量 {bgm_config.get('volume', 0.3)}")
    else:
        logger.info("音频轨道2（BGM）: 未配置")

    # 轨道3+：音效（时间戳需要重新映射）
    effect_count = 0
    for effect in sound_effects:
        trigger = effect.get('trigger', 'title')
        effect_url = effect.get('url')
        
        if not effect_url:
            continue
        
        # 找到触发时间点（使用重新映射后的时间）
        trigger_time = find_trigger_time_with_remapping(sentences, trigger, keep_segments)
        
        if trigger_time is not None:
            audio_tracks.append({
                "AudioTrackClips": [{
                    "Type": "Audio",
                    "MediaURL": effect_url,
                    "TimelineIn": trigger_time,
                    "TimelineOut": trigger_time + 2,
                    "Effects": [{
                        "Type": "Volume",
                        "Gain": 0.8
                    }]
                }]
            })
            effect_count += 1

    if effect_count > 0:
        logger.info(f"音频轨道3+（音效）: {effect_count} 个音效")
    else:
        logger.info("音频轨道3+（音效）: 未配置")

    logger.info(f"音频轨道总计: {len(audio_tracks)} 个轨道")
    return audio_tracks


def find_trigger_time_with_remapping(
    sentences: List[Dict], 
    trigger_type: str,
    keep_segments: List[Tuple[int, int]]
) -> Optional[float]:
    """
    根据触发类型找到对应的时间点（带时间戳重映射）
    """
    if not sentences:
        return None
    
    # 构建时间映射
    time_mapping = {}
    current_offset = 0.0
    
    for start_ms, end_ms in keep_segments:
        segment_duration = (end_ms - start_ms) / 1000.0
        for sent in sentences:
            sent_begin = sent.get('beginTime', 0)
            if start_ms <= sent_begin < end_ms:
                relative_start = (sent_begin - start_ms) / 1000.0
                time_mapping[sent.get('id')] = current_offset + relative_start
        current_offset += segment_duration
    
    # 根据触发类型找到对应的字幕
    for sent in sentences:
        text = sent.get('text', '')
        sent_id = sent.get('id')
        
        if sent_id not in time_mapping:
            continue
        
        mapped_time = time_mapping[sent_id]
        
        if trigger_type == 'title' and len(text) < 15:
            return mapped_time
        elif trigger_type == 'emphasis' and ('！' in text or '!' in text):
            return mapped_time
        elif trigger_type == 'section':
            return mapped_time
    
    # 默认返回第一个字幕的时间
    if sentences:
        first_id = sentences[0].get('id')
        if first_id in time_mapping:
            return time_mapping[first_id]
    
    return None


def extract_keywords(text: str) -> List[str]:
    """
    从文本中提取关键词
    
    提取规则：
    - 数字+%/倍（如"增长50%"、"翻了两倍"）
    - 核心数据（如"100万"、"第一"）
    - 重要名词短语
    """
    keywords = []
    
    # 提取数字+%/倍
    data_patterns = re.findall(r'\d+[%倍]', text)
    keywords.extend(data_patterns)
    
    # 提取数字+量词（如100万、第一）
    number_patterns = re.findall(r'\d+[万亿]?|第[一二三四五六七八九十\d]+', text)
    keywords.extend(number_patterns)
    
    return keywords


def extract_video_title(sentences: List[Dict]) -> str:
    """
    从所有字幕中提取视频标题
    
    策略：
    1. 优先选择包含数字/数据的句子
    2. 其次选择第一句
    3. 最后选择最长的一句
    """
    if not sentences:
        return "智能剪辑视频"
    
    # 过滤掉静音段
    speech_sentences = [s for s in sentences if s.get('type') != 'silence']
    if not speech_sentences:
        return "智能剪辑视频"
    
    # 优先选择包含数字/数据的句子
    for sent in speech_sentences:
        text = sent.get('text', '')
        if re.search(r'\d+[%倍万亿]', text):
            return text[:30]  # 限制长度
    
    # 其次选择第一句
    first_text = speech_sentences[0].get('text', '')
    if first_text:
        return first_text[:30]
    
    # 最后选择最长的一句
    longest = max(speech_sentences, key=lambda s: len(s.get('text', '')))
    return longest.get('text', '智能剪辑视频')[:30]


def determine_subtitle_style(sentence: Dict, styles_config: Dict) -> Dict:
    """
    根据句子内容特征自动匹配样式
    
    从 styles_config 或 SUBTITLE_STYLES 获取样式配置
    """
    text = sentence.get('text', '')
    
    # 确定样式名称
    style_name = 'body'  # 默认使用body样式
    
    # 可以根据内容特征选择不同样式（可选）
    if re.search(r'\d+[%倍]', text):
        style_name = 'data'
    elif '!' in text or '！' in text:
        style_name = 'emphasis'
    
    # 优先从 styles_config 获取，如果不存在则从 SUBTITLE_STYLES 获取
    if style_name in styles_config:
        style = styles_config[style_name].copy()
    elif style_name in SUBTITLE_STYLES:
        style = SUBTITLE_STYLES[style_name].copy()
    else:
        # 默认样式
        style = {
            'font': 'SimSun',
            'font_size': 150,  # 默认150
            'font_color': '#FFFFFF',
            'outline': 40,
            'outline_color': '#000000',
            'motion_in': 'fade_in',
            'motion_out': 'fade_out',
            'x': 0,
            'y': 500,
            'alignment': 'TopLeft',
            'adapt_mode': 'AutoWrap',
            'size_request_type': 'RealDim'
        }
    
    return style


def generate_subtitle_clips(sentences: List[Dict], styles_config: Dict) -> List[Dict]:
    """
    生成字幕clips（单轨道）
    
    从模板配置读取样式，字体大小默认为150
    """
    clips = []
    skipped_count = 0
    silence_count = 0

    for sent in sentences:
        # 过滤静音段
        if sent.get('type') == 'silence':
            silence_count += 1
            continue

        text = sent.get('text', '').strip()
        if not text or text.startswith('[无声'):
            silence_count += 1
            continue

        # 从模板获取样式
        style = determine_subtitle_style(sent, styles_config)

        begin_sec = sent.get('beginTime', 0) / 1000
        end_sec = sent.get('endTime', 0) / 1000
        duration = end_sec - begin_sec

        if duration <= 0.1:  # 持续时间太短，跳过
            skipped_count += 1
            continue

        # 构建字幕clip - 从模板读取样式，字体大小默认150
        clip = {
            "Type": "Text",
            "Content": text,
            "TimelineIn": round(begin_sec, 3),
            "TimelineOut": round(end_sec, 3),
            "X": style.get('x', 0),
            "Y": style.get('y', 500),
            "Alignment": style.get('alignment', 'TopLeft'),
            "Font": style.get('font', 'SimSun'),
            "FontSize": style.get('font_size', 150),  # 默认150
            "SizeRequestType": style.get('size_request_type', 'RealDim'),
            "FontColor": style.get('font_color', '#FFFFFF'),
            "Outline": style.get('outline', 40),
            "OutlineColour": style.get('outline_color', '#000000'),
            "AdaptMode": style.get('adapt_mode', 'AutoWrap'),
            "AaiMotionIn": min(0.8, duration * 0.3),
            "AaiMotionOut": min(0.5, duration * 0.2),
            "AaiMotionInEffect": style.get('motion_in', 'fade_in'),
            "AaiMotionOutEffect": style.get('motion_out', 'fade_out')
        }

        # 添加花字效果（如果模板配置有）
        if style.get('effect_color_style'):
            clip['EffectColorStyle'] = style['effect_color_style']

        clips.append(clip)

    if silence_count > 0:
        logger.info(f"generate_subtitle_clips: 过滤了 {silence_count} 个静音段")
    if skipped_count > 0:
        logger.info(f"generate_subtitle_clips: 跳过了 {skipped_count} 个持续时间太短的字幕片段")

    logger.info(f"generate_subtitle_clips: 生成了 {len(clips)} 个字幕clips")
    return clips


def generate_video_clips(video_url: str, duration: float, effects_config: Dict) -> List[Dict]:
    """生成视频clips - 只保留基础播放，不添加任何视觉效果"""
    clips = []

    # 基础视频clip，不添加任何放缩、位移等效果
    clips.append({
        "Type": "Video",
        "MediaURL": video_url,
        "TimelineIn": 0,
        "TimelineOut": duration
    })

    logger.info(f"generate_video_clips: 生成基础视频clip，时长 {duration:.2f}s，无视觉效果")
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
        logger.info(f"generate_audio_tracks BGM: {bgm_config['url'][:50]}...，音量 {bgm_config.get('volume', 0.3)}")
    else:
        logger.info("generate_audio_tracks BGM: 未配置")

    # 轨道3+：音效（每个音效一个独立轨道）
    effect_count = 0
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
            effect_count += 1

    if effect_count > 0:
        logger.info(f"generate_audio_tracks 音效: {effect_count} 个")
    else:
        logger.info("generate_audio_tracks 音效: 未配置")

    logger.info(f"generate_audio_tracks 总计: {len(audio_tracks)} 个轨道")
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
    
    output_url = f"https://{OSS_CONFIG['bucket_name']}.oss-cn-hangzhou.aliyuncs.com/renders/{user_id}/{output_filename}"
    
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
