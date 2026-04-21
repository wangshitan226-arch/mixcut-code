"""
Kaipai ASR (Automatic Speech Recognition) utilities
开拍式语音识别工具 - 使用阿里云 DashScope FunASR
"""
import os
import uuid
import requests
import json
import logging
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 阿里云 DashScope 配置
DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', 'sk-a555a4e29a474a6989cb872de3a3070a')
DASHSCOPE_API_URL = 'https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription'
DASHSCOPE_TASK_URL = 'https://dashscope.aliyuncs.com/api/v1/tasks'

# 语气词列表
FILLER_WORDS = {'嗯', '啊', '哦', '呃', '唉', '哎', '哟', '哈', '嘿', '哼', '呢', '吧', '吗'}


def is_filler_word(text: str) -> bool:
    """判断是否为语气词"""
    return text.strip() in FILLER_WORDS


def format_time(ms: int) -> str:
    """毫秒转时间字符串 mm:ss"""
    seconds = ms // 1000
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"


def split_words_by_silence(words: List[Dict], min_split_gap: int = 100, silence_threshold: int = 300) -> List[Dict]:
    """
    按字间静音分割words列表
    - >100ms 分割成新短句
    - >300ms 设为静音段
    """
    if not words:
        return []
    
    # 计算所有词间间隔
    word_gaps = []
    for i in range(1, len(words)):
        prev_word = words[i-1]
        curr_word = words[i]
        prev_end = prev_word.get('end_time', 0)
        curr_begin = curr_word.get('begin_time', 0)
        gap = curr_begin - prev_end
        
        prev_text = prev_word.get('text', '') + prev_word.get('punctuation', '')
        curr_text = curr_word.get('text', '') + curr_word.get('punctuation', '')
        
        word_gaps.append({
            'index': i,
            'prev_text': prev_text,
            'curr_text': curr_text,
            'gap': gap,
            'should_split': gap >= min_split_gap,
            'is_silence': gap >= silence_threshold
        })
    
    # 按间隔分割
    groups = []
    current_group = [words[0]]
    current_silence_before = 0
    
    for i in range(1, len(words)):
        gap_info = word_gaps[i-1]
        
        if gap_info['should_split']:
            groups.append({
                'words': current_group,
                'silence_before': current_silence_before,
                'is_silence': current_silence_before >= silence_threshold
            })
            current_group = [words[i]]
            current_silence_before = gap_info['gap']
        else:
            current_group.append(words[i])
    
    if current_group:
        groups.append({
            'words': current_group,
            'silence_before': current_silence_before,
            'is_silence': current_silence_before >= silence_threshold
        })
    
    return groups


def convert_to_kaipai_format(asr_result: Dict, video_duration_ms: int) -> Dict:
    """
    将ASR结果转换为开拍格式
    """
    transcripts = asr_result.get('transcripts', [])
    all_words = []
    
    for transcript in transcripts:
        for sent in transcript.get('sentences', []):
            all_words.extend(sent.get('words', []))
    
    if not all_words:
        return {'sentences': [], 'videoInfo': {'duration': video_duration_ms // 1000}}
    
    all_words.sort(key=lambda w: w.get('begin_time', 0))
    
    segments = []
    segment_id = 1
    
    # 1. 检测视频开头静音
    first_word_begin = all_words[0].get('begin_time', 0)
    if first_word_begin >= 300:
        segments.append({
            'id': str(segment_id),
            'time': format_time(0),
            'beginTime': 0,
            'endTime': first_word_begin,
            'text': f'[无声 {first_word_begin/1000:.2f}s]',
            'words': [],
            'type': 'silence',
            'silenceDuration': first_word_begin,
            'selected': False,
            'expanded': False
        })
        segment_id += 1
    
    # 2. 按词间静音分割
    word_groups = split_words_by_silence(all_words, min_split_gap=100, silence_threshold=300)
    
    for i, group in enumerate(word_groups):
        words = group['words']
        silence_before = group['silence_before']
        is_silence = group['is_silence']
        
        # 添加静音段
        if is_silence and i > 0:
            prev_end = words[0].get('begin_time', 0) - silence_before
            curr_begin = words[0].get('begin_time', 0)
            segments.append({
                'id': str(segment_id),
                'time': format_time(prev_end),
                'beginTime': prev_end,
                'endTime': curr_begin,
                'text': f'[无声 {silence_before/1000:.2f}s]',
                'words': [],
                'type': 'silence',
                'silenceDuration': silence_before,
                'selected': False,
                'expanded': False
            })
            segment_id += 1
        
        # 添加语音段
        text = ''.join([w.get('text', '') + w.get('punctuation', '') for w in words])
        begin_time = words[0].get('begin_time', 0)
        end_time = words[-1].get('end_time', 0)
        
        word_list = []
        has_filler = False
        for w in words:
            word_text = w.get('text', '').strip()
            word_info = {
                'text': word_text + w.get('punctuation', ''),
                'beginTime': w.get('begin_time', 0),
                'endTime': w.get('end_time', 0),
                'isFiller': is_filler_word(word_text)
            }
            word_list.append(word_info)
            if word_info['isFiller']:
                has_filler = True
        
        segments.append({
            'id': str(segment_id),
            'time': format_time(begin_time),
            'beginTime': begin_time,
            'endTime': end_time,
            'text': text,
            'words': word_list,
            'type': 'speech',
            'hasFiller': has_filler,
            'selected': False,
            'expanded': False
        })
        segment_id += 1
    
    # 3. 检测视频结尾静音
    last_word_end = all_words[-1].get('end_time', 0)
    ending_silence = video_duration_ms - last_word_end
    if ending_silence >= 300:
        segments.append({
            'id': str(segment_id),
            'time': format_time(last_word_end),
            'beginTime': last_word_end,
            'endTime': video_duration_ms,
            'text': f'[无声 {ending_silence/1000:.2f}s]',
            'words': [],
            'type': 'silence',
            'silenceDuration': ending_silence,
            'selected': False,
            'expanded': False
        })
    
    return {
        'sentences': segments,
        'videoInfo': {
            'duration': video_duration_ms // 1000,
            'format': asr_result.get('properties', {}).get('audio_format', 'unknown')
        }
    }


# ==================== DashScope API 调用 ====================

def submit_asr_task(file_url: str) -> Dict:
    """提交语音识别任务到 DashScope"""
    headers = {
        'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
        'Content-Type': 'application/json',
        'X-DashScope-Async': 'enable'
    }
    
    data = {
        'model': 'fun-asr',
        'input': {
            'file_urls': [file_url]
        },
        'parameters': {
            'channel_id': [0],
            'diarization_enabled': False
        }
    }
    
    response = requests.post(DASHSCOPE_API_URL, headers=headers, json=data, timeout=30)
    return response.json()


def query_asr_task(task_id: str) -> Dict:
    """查询ASR任务状态"""
    headers = {
        'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(f'{DASHSCOPE_TASK_URL}/{task_id}', headers=headers, timeout=30)
    return response.json()


def fetch_transcription_result(transcription_url: str) -> Dict:
    """获取识别结果"""
    response = requests.get(transcription_url, timeout=30)
    return response.json()


# ==================== 视频切分工具 ====================

def split_video_segments(video_url: str, segments: List[Dict], edit_id: str, user_id: str) -> List[Dict]:
    """
    将视频按时间段切分成多个片段并上传到OSS
    
    Args:
        video_url: 原始视频URL
        segments: ASR识别出的片段列表
        edit_id: 编辑任务ID
        user_id: 用户ID
        
    Returns:
        包含OSS URL的片段列表
    """
    import subprocess
    import os
    from utils.oss import oss_client
    
    segment_urls = []
    
    logger.info(f"开始切分视频: edit_id={edit_id}, video_url={video_url[:80]}..., segments={len(segments)}")
    
    try:
        # 下载原始视频到本地
        local_video_path = os.path.join('uploads', f'temp_segment_{edit_id}.mp4')
        logger.info(f"下载视频到: {local_video_path}")
        
        if video_url.startswith('http'):
            logger.info(f"从URL下载视频...")
            response = requests.get(video_url, timeout=120)
            logger.info(f"下载完成，大小: {len(response.content)} bytes")
            with open(local_video_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"视频保存完成")
        else:
            local_video_path = video_url.lstrip('/')
            logger.info(f"使用本地视频: {local_video_path}")
        
        # 为每个片段切分视频
        logger.info(f"开始切分 {len(segments)} 个片段")
        for i, segment in enumerate(segments):
            begin_time = segment['beginTime']
            end_time = segment['endTime']
            duration = (end_time - begin_time) / 1000  # 转换为秒
            start_sec = begin_time / 1000
            
            logger.info(f"切分片段 {i+1}/{len(segments)}: {start_sec}s - {start_sec+duration}s")
            
            # 生成片段文件名
            segment_filename = f"segment_{i:04d}.mp4"
            segment_path = os.path.join('uploads', f'segments_{edit_id}', segment_filename)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(segment_path), exist_ok=True)
            
            # 使用ffmpeg切分（不重新编码，快速）
            cmd = [
                'ffmpeg', '-y', '-ss', str(start_sec), '-t', str(duration),
                '-i', local_video_path, '-c', 'copy', segment_path
            ]
            
            logger.info(f"执行ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"ffmpeg完成，返回码: {result.returncode}")
            
            # 检查文件是否生成
            if not os.path.exists(segment_path):
                logger.error(f"片段文件未生成: {segment_path}")
                continue
            
            file_size = os.path.getsize(segment_path)
            logger.info(f"片段文件生成: {segment_path}, 大小: {file_size} bytes")
            
            # 上传到OSS
            from datetime import datetime
            date_str = datetime.now().strftime('%Y/%m/%d')
            oss_key = f"users/{user_id}/kaipai/{edit_id}/segments/{segment_filename}"
            
            if oss_client.enabled:
                logger.info(f"上传到OSS: {oss_key}")
                oss_client.bucket.put_object_from_file(oss_key, segment_path)
                segment_url = f"https://{oss_client.bucket_name}.{oss_client.endpoint}/{oss_key}"
                logger.info(f"OSS上传完成: {segment_url[:80]}...")
            else:
                # OSS未启用，使用本地路径
                segment_url = f"/uploads/segments_{edit_id}/{segment_filename}"
                logger.info(f"使用本地路径: {segment_url}")
            
            segment_urls.append({
                'id': segment['id'],
                'url': segment_url,
                'beginTime': begin_time,
                'endTime': end_time,
                'duration': duration
            })
            
            # 清理本地临时文件
            if os.path.exists(segment_path):
                os.remove(segment_path)
                logger.info(f"清理临时文件: {segment_path}")
        
        # 清理原始视频临时文件
        if os.path.exists(local_video_path) and 'temp_' in local_video_path:
            os.remove(local_video_path)
            logger.info(f"清理原始视频临时文件: {local_video_path}")
        
        # 清理空目录
        segment_dir = os.path.join('uploads', f'segments_{edit_id}')
        if os.path.exists(segment_dir) and not os.listdir(segment_dir):
            os.rmdir(segment_dir)
        
        logger.info(f"视频切分全部完成: {len(segment_urls)} 个片段")
        return segment_urls
        
    except Exception as e:
        logger.error(f"切分视频片段失败: {e}")
        import traceback
        traceback.print_exc()
        return []


# ==================== 任务管理（内存存储） ====================

# 全局任务存储（生产环境建议使用Redis）
asr_tasks = {}


def create_asr_task(task_id: str, file_url: str) -> Dict:
    """创建新的ASR任务"""
    asr_tasks[task_id] = {
        'id': task_id,
        'status': 'pending',
        'file_url': file_url,
        'created_at': datetime.now().isoformat(),
        'result': None,
        'error': None
    }
    return asr_tasks[task_id]


def get_asr_task(task_id: str) -> Optional[Dict]:
    """获取任务状态"""
    return asr_tasks.get(task_id)


def extract_and_upload_audio(video_url: str, edit_id: str) -> str:
    """提取视频音频并上传到OSS，返回音频URL"""
    import subprocess
    import os
    from utils.oss import oss_client
    
    try:
        # 下载视频到本地
        local_video_path = os.path.join('uploads', f'temp_audio_extract_{edit_id}.mp4')
        if video_url.startswith('http'):
            response = requests.get(video_url, timeout=120)
            with open(local_video_path, 'wb') as f:
                f.write(response.content)
        else:
            local_video_path = video_url.lstrip('/')
        
        # 提取音频并重新编码
        audio_path = os.path.join('uploads', f'audio_{edit_id}.mp3')
        cmd = [
            'ffmpeg', '-y',
            '-i', local_video_path,
            '-vn',  # 不处理视频
            '-c:a', 'libmp3lame',
            '-b:a', '128k',
            '-ar', '44100',
            '-ac', '2',
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"提取音频失败: {result.stderr}")
            return video_url  # 失败时返回原视频URL
        
        # 上传到OSS
        if oss_client.enabled:
            oss_key = f"kaipai/audio_{edit_id}.mp3"
            oss_client.bucket.put_object_from_file(oss_key, audio_path)
            audio_url = f"https://{oss_client.bucket_name}.{oss_client.endpoint}/{oss_key}"
        else:
            audio_url = f"/uploads/audio_{edit_id}.mp3"
        
        # 清理临时文件
        if os.path.exists(local_video_path) and 'temp_' in local_video_path:
            os.remove(local_video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        logger.info(f"音频提取完成: {audio_url}")
        return audio_url
        
    except Exception as e:
        logger.error(f"提取音频失败: {e}")
        return video_url  # 失败时返回原视频URL


def process_asr_task(task_id: str, file_url: str, edit_id: str = None, user_id: str = None):
    """异步处理ASR任务（在线程中执行）"""
    
    def _process():
        try:
            asr_tasks[task_id]['status'] = 'transcribing'
            
            # 提取音频并重新编码，确保音频流连续
            logger.info(f"开始提取音频: {edit_id}")
            audio_url = extract_and_upload_audio(file_url, edit_id) if edit_id else file_url
            logger.info(f"使用音频URL进行识别: {audio_url[:80]}...")
            
            # 提交任务
            submit_result = submit_asr_task(audio_url)
            asr_task_id = submit_result.get('output', {}).get('task_id')
            
            if not asr_task_id:
                raise Exception('未能获取ASR任务ID')
            
            asr_tasks[task_id]['asr_task_id'] = asr_task_id
            
            # 轮询等待
            max_attempts = 300
            for i in range(max_attempts):
                result = query_asr_task(asr_task_id)
                status = result.get('output', {}).get('task_status')
                
                if status == 'SUCCEEDED':
                    transcription_url = result.get('output', {}).get('results', [{}])[0].get('transcription_url')
                    if not transcription_url:
                        raise Exception('未能获取识别结果URL')
                    
                    raw_result = fetch_transcription_result(transcription_url)
                    video_duration = raw_result.get('properties', {}).get('original_duration_in_milliseconds', 0)
                    frontend_data = convert_to_kaipai_format(raw_result, video_duration)
                    
                    # ASR完成，立即标记完成并返回结果
                    asr_tasks[task_id]['status'] = 'completed'
                    asr_tasks[task_id]['result'] = frontend_data
                    logger.info(f"ASR任务 {task_id} 完成，开始后台视频分割")
                    
                    # 如果有edit_id和user_id，在后台线程中切分视频片段
                    # 这样ASR结果可以立即返回给前端，视频分割在后台进行
                    if edit_id and user_id and frontend_data.get('sentences'):
                        asr_tasks[task_id]['segment_status'] = 'processing'
                        # 启动新的后台线程进行视频分割
                        split_thread = threading.Thread(
                            target=_split_video_in_background,
                            args=(task_id, file_url, frontend_data['sentences'], edit_id, user_id)
                        )
                        split_thread.daemon = True
                        split_thread.start()
                    else:
                        asr_tasks[task_id]['segment_status'] = 'completed'
                        asr_tasks[task_id]['segment_urls'] = []
                    
                    return
                    
                elif status == 'FAILED':
                    results = result.get('output', {}).get('results', [])
                    error_info = results[0] if results else {}
                    raise Exception(f"[{error_info.get('code', '未知错误')}] {error_info.get('message', '无详细信息')}")
                
                time.sleep(1)
            
            raise Exception('等待语音识别结果超时')
            
        except Exception as e:
            logger.error(f"ASR任务 {task_id} 失败: {e}")
            asr_tasks[task_id]['status'] = 'failed'
            asr_tasks[task_id]['error'] = str(e)
    
    def _split_video_in_background(task_id, file_url, sentences, edit_id, user_id):
        """后台线程：切分视频片段"""
        try:
            logger.info(f"后台开始切分视频片段: {edit_id}, 共 {len(sentences)} 个片段")
            segment_urls = split_video_segments(file_url, sentences, edit_id, user_id)
            
            if not segment_urls:
                logger.error(f"视频片段切分返回空列表: {edit_id}")
                asr_tasks[task_id]['segment_status'] = 'failed'
                asr_tasks[task_id]['segment_error'] = '视频片段切分失败，返回空列表'
                return
            
            asr_tasks[task_id]['segment_urls'] = segment_urls
            asr_tasks[task_id]['segment_status'] = 'completed'
            logger.info(f"视频片段切分完成: {len(segment_urls)} 个片段")
        except Exception as e:
            logger.error(f"视频片段切分失败: {e}")
            import traceback
            traceback.print_exc()
            asr_tasks[task_id]['segment_status'] = 'failed'
            asr_tasks[task_id]['segment_error'] = str(e)
    
    thread = threading.Thread(target=_process)
    thread.daemon = True
    thread.start()
