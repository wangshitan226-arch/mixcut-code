import os
import re
import json
import time
import uuid
import logging
import requests
import subprocess
import threading
from flask import Blueprint, request, jsonify

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')
logger = logging.getLogger(__name__)

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', 'sk-a555a4e29a474a6989cb872de3a3070a')
DASHSCOPE_API_URL = 'https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription'
DASHSCOPE_TASK_URL = 'https://dashscope.aliyuncs.com/api/v1/tasks'
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-55c9e54b564a40dc903d39eb864c22ec')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'

extract_tasks = {}


def resolve_douyin_url(share_url: str) -> str:
    """解析抖音分享链接，获取真实视频URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Referer': 'https://www.douyin.com/',
    }
    try:
        resp = requests.get(share_url, headers=headers, allow_redirects=True, timeout=15)
        final_url = resp.url

        aweme_id_match = re.search(r'/video/(\d+)', final_url)
        if not aweme_id_match:
            aweme_id_match = re.search(r'modal_id=(\d+)', final_url)
        if not aweme_id_match:
            aweme_id_match = re.search(r'/note/(\d+)', final_url)

        if aweme_id_match:
            aweme_id = aweme_id_match.group(1)
            api_url = f'https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={aweme_id}'
            api_resp = requests.get(api_url, headers=headers, timeout=15)
            data = api_resp.json()
            video_info = data.get('aweme_detail', {}).get('video', {})
            play_addr = video_info.get('play_addr', {})
            url_list = play_addr.get('url_list', [])
            if url_list:
                video_url = url_list[0].replace('playwm', 'play')
                return video_url

        play_url_match = re.search(r'"playAddr"\s*:\s*\[\{"src"\s*:\s*"([^"]+)"', resp.text)
        if play_url_match:
            return play_url_match.group(1).replace('\\u002F', '/').replace('&amp;', '&')

        return None
    except Exception as e:
        logger.error(f'解析抖音链接失败: {e}')
        return None


def download_video(video_url: str) -> str:
    """下载视频到本地，返回本地路径"""
    os.makedirs('uploads', exist_ok=True)
    local_path = os.path.join('uploads', f'extract_{uuid.uuid4().hex[:8]}_{int(time.time())}.mp4')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36',
        'Referer': 'https://www.douyin.com/',
    }
    resp = requests.get(video_url, headers=headers, stream=True, timeout=120)
    resp.raise_for_status()
    with open(local_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return local_path


def extract_audio(video_path: str) -> str:
    """从视频中提取音频，返回音频路径"""
    audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vn',
        '-c:a', 'libmp3lame',
        '-b:a', '128k',
        '-ar', '44100',
        '-ac', '2',
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f'ffmpeg提取音频失败: {result.stderr[:200]}')
    return audio_path


def upload_audio_to_oss(audio_path: str) -> str:
    """上传音频到OSS，返回URL"""
    from utils.oss import oss_client
    if oss_client.enabled:
        oss_key = f'ai_copy/audio_{uuid.uuid4().hex[:8]}.mp3'
        oss_client.bucket.put_object_from_file(oss_key, audio_path)
        audio_url = f"https://{oss_client.bucket_name}.{oss_client.endpoint}/{oss_key}"
        return audio_url
    return audio_path


def run_asr(audio_url: str) -> str:
    """运行ASR，返回识别出的纯文本"""
    headers = {
        'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
        'Content-Type': 'application/json',
        'X-DashScope-Async': 'enable'
    }
    data = {
        'model': 'fun-asr',
        'input': {'file_urls': [audio_url]},
        'parameters': {'channel_id': [0], 'diarization_enabled': False}
    }
    resp = requests.post(DASHSCOPE_API_URL, headers=headers, json=data, timeout=30)
    result = resp.json()
    asr_task_id = result.get('output', {}).get('task_id')
    if not asr_task_id:
        raise Exception(f'ASR任务提交失败: {result}')

    for _ in range(300):
        query_resp = requests.post(f'{DASHSCOPE_TASK_URL}/{asr_task_id}', headers={
            'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
            'Content-Type': 'application/json'
        }, timeout=30)
        query_result = query_resp.json()
        status = query_result.get('output', {}).get('task_status')
        if status == 'SUCCEEDED':
            transcription_url = query_result['output']['results'][0]['transcription_url']
            trans_resp = requests.get(transcription_url, timeout=30)
            trans_data = trans_resp.json()
            paragraphs = trans_data.get('results', [{}])[0].get('transcripts', [{}])[0].get('sentences', [])
            text = ' '.join(s.get('text', '') for s in paragraphs if s.get('text'))
            return text.strip()
        elif status == 'FAILED':
            raise Exception('ASR识别失败')
        time.sleep(1)
    raise Exception('ASR识别超时')


def rewrite_copy_with_deepseek(original_text: str) -> str:
    """使用DeepSeek改写文案"""
    prompt = f"""你是一个专业的短视频文案改写专家。请根据以下原始视频文案，改写一版新的文案。

要求：
1. 保持核心意思不变，但用不同的表达方式
2. 语言更加生动、有吸引力
3. 适合短视频口播，节奏感强
4. 保留关键信息和数据
5. 字数与原文相近

原始文案：
{original_text}

请直接输出改写后的文案，不要加任何前缀说明："""

    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'deepseek-chat',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.8,
        'max_tokens': 2000
    }
    resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)
    result = resp.json()
    return result['choices'][0]['message']['content'].strip()


def _process_extract_task(task_id: str, input_text: str):
    """异步处理文案提取任务"""
    try:
        extract_tasks[task_id]['status'] = 'resolving'
        extract_tasks[task_id]['progress'] = '解析链接...'

        video_url = input_text.strip()
        is_douyin = any(d in video_url for d in ['douyin.com', 'v.douyin.com', 'iesdouyin.com'])

        if is_douyin:
            resolved = resolve_douyin_url(video_url)
            if resolved:
                video_url = resolved
            else:
                extract_tasks[task_id]['status'] = 'failed'
                extract_tasks[task_id]['error'] = '无法解析抖音链接，请尝试直接粘贴视频URL'
                return

        extract_tasks[task_id]['status'] = 'downloading'
        extract_tasks[task_id]['progress'] = '下载视频...'

        local_video = download_video(video_url)

        extract_tasks[task_id]['status'] = 'extracting'
        extract_tasks[task_id]['progress'] = '提取音频...'

        audio_path = extract_audio(local_video)
        audio_url = upload_audio_to_oss(audio_path)

        extract_tasks[task_id]['status'] = 'transcribing'
        extract_tasks[task_id]['progress'] = '语音识别中...'

        original_text = run_asr(audio_url)

        if not original_text:
            extract_tasks[task_id]['status'] = 'failed'
            extract_tasks[task_id]['error'] = '语音识别结果为空，视频可能没有语音内容'
            return

        extract_tasks[task_id]['status'] = 'rewriting'
        extract_tasks[task_id]['progress'] = 'AI改写文案中...'

        rewritten_text = rewrite_copy_with_deepseek(original_text)

        extract_tasks[task_id]['status'] = 'completed'
        extract_tasks[task_id]['original_text'] = original_text
        extract_tasks[task_id]['rewritten_text'] = rewritten_text

        for f in [local_video, audio_path]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass

    except Exception as e:
        logger.error(f'文案提取任务失败: {e}')
        import traceback
        traceback.print_exc()
        extract_tasks[task_id]['status'] = 'failed'
        extract_tasks[task_id]['error'] = str(e)


@ai_bp.route('/extract-copy', methods=['POST'])
def extract_copy():
    """提取视频文案 + AI改写"""
    data = request.get_json(silent=True) or {}
    input_text = data.get('input', '').strip()

    if not input_text:
        return jsonify({'error': '请输入视频链接'}), 400

    task_id = str(uuid.uuid4())
    extract_tasks[task_id] = {
        'status': 'pending',
        'progress': '',
        'original_text': '',
        'rewritten_text': '',
        'error': '',
        'created_at': time.time()
    }

    thread = threading.Thread(target=_process_extract_task, args=(task_id, input_text))
    thread.daemon = True
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


@ai_bp.route('/extract-copy/<task_id>/status', methods=['GET'])
def get_extract_status(task_id):
    """查询文案提取任务状态"""
    if task_id not in extract_tasks:
        return jsonify({'error': '任务不存在'}), 404

    task = extract_tasks[task_id]
    result = {
        'task_id': task_id,
        'status': task['status'],
        'progress': task.get('progress', ''),
    }

    if task['status'] == 'completed':
        result['original_text'] = task['original_text']
        result['rewritten_text'] = task['rewritten_text']
    elif task['status'] == 'failed':
        result['error'] = task.get('error', '未知错误')

    return jsonify(result)


@ai_bp.route('/copy', methods=['POST'])
def generate_copy():
    """通用AI文案生成接口"""
    data = request.get_json(silent=True) or {}
    tool = data.get('tool', '')
    input_text = data.get('input', '').strip()

    if not input_text:
        return jsonify({'error': '请输入内容'}), 400

    prompts = {
        'persona': f"""你是一个专业的IP人设文案生成专家。请根据以下描述，生成一段适合短视频口播的人设文案，要求：
1. 突出个人特色和专业领域
2. 语言亲切自然，有信任感
3. 30-60秒口播时长
4. 开头有记忆点的自我介绍

人设描述：{input_text}

请直接输出文案：""",
        'rewrite': f"""你是一个专业的文案改写专家。请改写以下文案，要求：
1. 保持核心意思不变
2. 表达更生动、更有吸引力
3. 适合短视频口播
4. 节奏感强，有记忆点

原始文案：{input_text}

请直接输出改写后的文案：""",
        'translate': f"""请将以下内容翻译为中文（如果是中文则翻译为英文），保持原文的语气和风格：

{input_text}

请直接输出翻译结果：""",
        'local_traffic': f"""你是一个同城流量文案专家。请根据以下业务描述，生成一段适合短视频的同城引流文案，要求：
1. 突出本地特色和地理位置
2. 有明确的到店引导
3. 包含优惠或限时信息
4. 30-60秒口播时长

业务描述：{input_text}

请直接输出文案：""",
        'franchise': f"""你是一个招商加盟文案专家。请根据以下品牌信息，生成一段有吸引力的招商加盟文案，要求：
1. 突出品牌优势和盈利模式
2. 有数据支撑和成功案例感
3. 明确的加盟政策亮点
4. 有行动号召

品牌信息：{input_text}

请直接输出文案：""",
        'store': f"""你是一个门店获客文案专家。请根据以下门店信息，生成一段吸引客户的短视频文案，要求：
1. 突出产品/服务特色
2. 有明确的到店理由
3. 包含限时优惠或独家福利
4. 30-60秒口播时长

门店信息：{input_text}

请直接输出文案：""",
    }

    prompt = prompts.get(tool)
    if not prompt:
        return jsonify({'error': '不支持的工具类型'}), 400

    try:
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json'
        }
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json={
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.8,
            'max_tokens': 2000
        }, timeout=60)
        result = resp.json()
        content = result['choices'][0]['message']['content'].strip()
        return jsonify({'success': True, 'result': content})
    except Exception as e:
        logger.error(f'AI文案生成失败: {e}')
        return jsonify({'error': f'生成失败: {str(e)}'}), 500
