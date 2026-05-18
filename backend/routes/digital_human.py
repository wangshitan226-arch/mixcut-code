import os
import re
import uuid
import json
import time
import logging
import requests
import threading
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import DigitalHuman, VoiceClone
from utils.videoretalk import videoretalk_tool
from utils.oss import oss_client

digital_human_bp = Blueprint('digital_human', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', 'sk-a555a4e29a474a6989cb872de3a3070a')
DASHSCOPE_CUSTOMIZATION_URL = 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization'
DASHSCOPE_TTS_URL = 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer'

CLONE_REF_TEXT = '你好，我是你的专属AI克隆声音。I am your exclusive AI clone voice.'

SYSTEM_VOICES = [
    {"id": "longxiaocheng_v2", "name": "龙小诚", "gender": "male", "style": "沉稳男声", "scenario": "有声阅读"},
    {"id": "longxiaochun_v2", "name": "龙小春", "gender": "female", "style": "温柔女声", "scenario": "有声阅读"},
    {"id": "longlaotie_v2", "name": "龙老铁", "gender": "male", "style": "东北老铁", "scenario": "短视频配音"},
    {"id": "longshuo_v2", "name": "龙硕", "gender": "male", "style": "磁性男声", "scenario": "有声阅读"},
    {"id": "longyue_v2", "name": "龙悦", "gender": "female", "style": "温柔女声", "scenario": "有声阅读"},
    {"id": "longfei_v2", "name": "龙飞", "gender": "male", "style": "激情男声", "scenario": "有声阅读"},
    {"id": "longjielidou_v2", "name": "龙杰力豆", "gender": "male", "style": "活泼男童", "scenario": "童声"},
    {"id": "longshuoer_v2", "name": "龙硕尔", "gender": "female", "style": "温柔女童", "scenario": "童声"},
    {"id": "longyingxiao_v2", "name": "龙盈笑", "gender": "female", "style": "甜美销售", "scenario": "电话销售"},
    {"id": "longjiqi_v2", "name": "龙机七", "gender": "neutral", "style": "呆萌机器人", "scenario": "短视频配音"},
    {"id": "longhouge_v2", "name": "龙猴哥", "gender": "male", "style": "经典猴王", "scenario": "短视频配音"},
    {"id": "longjixin_v2", "name": "龙吉星", "gender": "female", "style": "尖酸刻薄女", "scenario": "短视频配音"},
    {"id": "longdaiyu_v2", "name": "龙黛玉", "gender": "female", "style": "柔弱才女", "scenario": "短视频配音"},
    {"id": "longgaoseng_v2", "name": "龙高僧", "gender": "male", "style": "悟道高僧", "scenario": "短视频配音"},
    {"id": "longanli_v2", "name": "龙安理", "gender": "female", "style": "干练女声", "scenario": "语音助手"},
    {"id": "longanlang_v2", "name": "龙安朗", "gender": "male", "style": "清新男声", "scenario": "语音助手"},
    {"id": "longxiaobai_v2", "name": "龙小白", "gender": "female", "style": "亲切女声", "scenario": "客服"},
    {"id": "longxiaoye_v2", "name": "龙小野", "gender": "male", "style": "低沉男声", "scenario": "有声阅读"},
    {"id": "longwan_v2", "name": "龙婉", "gender": "female", "style": "知性女声", "scenario": "新闻播报"},
    {"id": "longcheng_v2", "name": "龙诚", "gender": "male", "style": "浑厚男声", "scenario": "新闻播报"},
    {"id": "longmiao_v2", "name": "龙淼", "gender": "female", "style": "温柔女声", "scenario": "情感电台"},
    {"id": "longjing_v2", "name": "龙晶", "gender": "female", "style": "清亮女声", "scenario": "语音助手"},
    {"id": "longhua_v2", "name": "龙华", "gender": "male", "style": "大气男声", "scenario": "纪录片"},
    {"id": "longxiaomo_v2", "name": "龙小墨", "gender": "male", "style": "低沉男声", "scenario": "有声阅读"},
]


@digital_human_bp.route('/system-voices', methods=['GET'])
def get_system_voices():
    """获取阿里云系统语音列表"""
    scenario = request.args.get('scenario')
    gender = request.args.get('gender')
    voices = SYSTEM_VOICES
    if scenario:
        voices = [v for v in voices if v['scenario'] == scenario]
    if gender:
        voices = [v for v in voices if v['gender'] == gender]
    return jsonify({'voices': voices})


@digital_human_bp.route('/system-voices/preview', methods=['POST'])
def preview_system_voice():
    """试听系统语音"""
    try:
        data = request.get_json(silent=True) or {}
        voice_id = data.get('voice_id', '')
        text = data.get('text', '你好，这是系统语音试听效果。')

        if not voice_id:
            return jsonify({'error': '请指定语音ID'}), 400

        audio_url = _synthesize_speech(text, voice_id, 'cosyvoice-v2')
        if audio_url:
            return jsonify({'success': True, 'audio_url': audio_url})
        else:
            return jsonify({'error': '语音合成失败'}), 500
    except Exception as e:
        logger.error(f"[SystemVoice] 试听异常: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/users/<user_id>/digital-humans', methods=['GET'])
def list_digital_humans(user_id):
    try:
        humans = DigitalHuman.query.filter_by(user_id=user_id).order_by(DigitalHuman.updated_at.desc()).all()
        logger.info(f"[DigitalHuman] Listed {len(humans)} digital humans for user {user_id}")
        return jsonify({'digital_humans': [h.to_dict() for h in humans]})
    except Exception as e:
        logger.error(f"[DigitalHuman] List error: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/digital-humans', methods=['POST'])
def create_digital_human():
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        title = data.get('title', '').strip()
        video_url = data.get('video_url')
        cover_url = data.get('cover_url')
        voice_id = data.get('voice_id')
        voice_name = data.get('voice_name')

        logger.info(f"[DigitalHuman] Create request: user={user_id}, title={title}, video_url={video_url}, voice_id={voice_id}")

        if not user_id:
            return jsonify({'error': '缺少user_id'}), 400
        if not title:
            return jsonify({'error': '请输入数字人名称'}), 400

        dh = DigitalHuman(
            user_id=user_id,
            title=title,
            video_url=video_url,
            cover_url=cover_url,
            voice_id=voice_id,
            voice_name=voice_name,
            status='ready' if video_url else 'draft',
        )
        db.session.add(dh)
        db.session.commit()

        logger.info(f"[DigitalHuman] Created: id={dh.id}, status={dh.status}")
        return jsonify(dh.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"[DigitalHuman] Create error: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/digital-humans/<dh_id>', methods=['GET'])
def get_digital_human(dh_id):
    try:
        dh = DigitalHuman.query.get(dh_id)
        if not dh:
            return jsonify({'error': '数字人不存在'}), 404
        if dh.status == 'training' and dh.avatar_id:
            _check_avatar_status(dh)
        if dh.videoretalk_status in ('processing', 'submitted') and dh.videoretalk_task_id:
            _check_videoretalk_status(dh)
        return jsonify(dh.to_dict())
    except Exception as e:
        logger.error(f"[DigitalHuman] Get error: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/digital-humans/<dh_id>', methods=['PUT'])
def update_digital_human(dh_id):
    try:
        dh = DigitalHuman.query.get(dh_id)
        if not dh:
            return jsonify({'error': '数字人不存在'}), 404
        data = request.get_json(silent=True) or {}
        if 'title' in data:
            dh.title = data['title'].strip()
        if 'video_url' in data:
            dh.video_url = data['video_url']
        if 'cover_url' in data:
            dh.cover_url = data['cover_url']
        if 'voice_id' in data:
            dh.voice_id = data['voice_id']
        if 'voice_name' in data:
            dh.voice_name = data['voice_name']
        if data.get('video_url') and dh.status == 'draft':
            dh.status = 'ready'
        db.session.commit()
        return jsonify(dh.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/digital-humans/<dh_id>', methods=['DELETE'])
def delete_digital_human(dh_id):
    try:
        dh = DigitalHuman.query.get(dh_id)
        if not dh:
            return jsonify({'error': '数字人不存在'}), 404
        db.session.delete(dh)
        db.session.commit()
        return jsonify({'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== VideoRetalk 对口型生成 ====================

@digital_human_bp.route('/digital-humans/<dh_id>/generate', methods=['POST'])
def generate_avatar_video(dh_id):
    """
    提交数字人对口型视频生成任务

    流程:
    1. 使用 DashScope TTS 将文本合成为音频
    2. 使用 VideoRetalk 将模板视频驱动音频生成对口型视频
    3. 下载生成的视频并上传到OSS

    请求体:?
    {
        "text": "要合成的文本",
        "voice_id": "可选，覆盖数字人默认声音",
        "video_extension": false
    }
    """
    try:
        dh = DigitalHuman.query.get(dh_id)
        if not dh:
            return jsonify({'error': '数字人不存在'}), 404

        if not dh.video_url:
            return jsonify({'error': '数字人未设置模板视频，无法生成对口型视频'}), 400

        data = request.get_json(silent=True) or {}
        text = data.get('text', '').strip()
        voice_id = data.get('voice_id', dh.voice_id)
        video_extension = data.get('video_extension', False)

        if not text:
            return jsonify({'error': '请输入要合成的文本'}), 400

        if not voice_id:
            return jsonify({'error': '数字人未设置声音，请先选择声音'}), 400

        if dh.videoretalk_status in ('processing', 'submitted'):
            return jsonify({
                'error': '已有生成任务进行中',
                'task_id': dh.videoretalk_task_id,
                'status': dh.videoretalk_status
            }), 409

        dh.videoretalk_status = 'synthesizing'
        db.session.commit()

        app = current_app._get_current_object()

        def _generate_pipeline():
            with app.app_context():
                try:
                    dh_obj = DigitalHuman.query.get(dh_id)
                    if not dh_obj:
                        return

                    logger.info(f"[VideoRetalk] 开始生成管线 dh={dh_id}, text={text[:30]}...")

                    audio_url = _synthesize_speech(text, voice_id)
                    if not audio_url:
                        logger.error(f"[VideoRetalk] TTS合成失败: dh={dh_id}")
                        dh_obj = DigitalHuman.query.get(dh_id)
                        if dh_obj:
                            dh_obj.videoretalk_status = 'failed'
                            db.session.commit()
                        return

                    logger.info(f"[VideoRetalk] TTS合成成功: {audio_url[:80]}...")

                    dh_obj = DigitalHuman.query.get(dh_id)
                    if not dh_obj:
                        return
                    dh_obj.videoretalk_status = 'submitted'

                    result = videoretalk_tool.submit_task(
                        video_url=dh_obj.video_url,
                        audio_url=audio_url,
                        video_extension=video_extension
                    )

                    if not result.get('success'):
                        error_msg = result.get('error', '提交任务失败')
                        logger.error(f"[VideoRetalk] 提交任务失败: {error_msg}")
                        dh_obj = DigitalHuman.query.get(dh_id)
                        if dh_obj:
                            dh_obj.videoretalk_status = 'failed'
                            db.session.commit()
                        return

                    task_id = result.get('task_id')
                    logger.info(f"[VideoRetalk] 任务已提交 task_id={task_id}")

                    dh_obj = DigitalHuman.query.get(dh_id)
                    if dh_obj:
                        dh_obj.videoretalk_task_id = task_id
                        dh_obj.videoretalk_status = 'processing'
                        db.session.commit()

                    _poll_videoretalk_task(app, dh_id, task_id, dh_obj.user_id)

                except Exception as e:
                    logger.error(f"[VideoRetalk] 生成管线异常: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        dh_obj = DigitalHuman.query.get(dh_id)
                        if dh_obj:
                            dh_obj.videoretalk_status = 'failed'
                            db.session.commit()
                    except Exception:
                        pass

        t = threading.Thread(target=_generate_pipeline, daemon=True)
        t.start()

        return jsonify({
            'success': True,
            'message': '数字人视频生成任务已提交',
            'dh_id': dh_id,
            'status': 'synthesizing'
        })

    except Exception as e:
        logger.error(f"[VideoRetalk] 生成请求异常: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/digital-humans/<dh_id>/generate/status', methods=['GET'])
def get_generate_status(dh_id):
    """查询数字人视频生成任务状态"""
    try:
        dh = DigitalHuman.query.get(dh_id)
        if not dh:
            return jsonify({'error': '数字人不存在'}), 404

        if dh.videoretalk_status in ('processing', 'submitted') and dh.videoretalk_task_id:
            _check_videoretalk_status(dh)

        return jsonify({
            'dh_id': dh_id,
            'videoretalk_status': dh.videoretalk_status,
            'videoretalk_task_id': dh.videoretalk_task_id,
            'generated_video_url': dh.generated_video_url,
            'generated_video_duration': dh.generated_video_duration,
        })
    except Exception as e:
        logger.error(f"[VideoRetalk] 查询状态异常 {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/digital-humans/<dh_id>/generate', methods=['DELETE'])
def cancel_generate(dh_id):
    """取消/重置数字人视频生成任务"""
    try:
        dh = DigitalHuman.query.get(dh_id)
        if not dh:
            return jsonify({'error': '数字人不存在'}), 404

        dh.videoretalk_status = 'idle'
        dh.videoretalk_task_id = None
        db.session.commit()

        return jsonify({'message': '已重置生成状态', 'videoretalk_status': 'idle'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== 语音合成 (TTS) ====================

@digital_human_bp.route('/digital-humans/tts', methods=['POST'])
def text_to_speech():
    """
    独立的TTS接口 - 将文本合成为语音

    请求体:?
    {
        "text": "要合成的文本",
        "voice_id": "声音ID",
        "model": "cosyvoice-v2"  // 可选
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        text = data.get('text', '').strip()
        voice_id = data.get('voice_id', '')
        target_model = data.get('model', 'cosyvoice-v2')

        if not text:
            return jsonify({'error': '请输入要合成的文本'}), 400
        if not voice_id:
            return jsonify({'error': '请指定声音ID'}), 400

        audio_url = _synthesize_speech(text, voice_id, target_model)

        if audio_url:
            return jsonify({'success': True, 'audio_url': audio_url})
        else:
            return jsonify({'error': '语音合成失败'}), 500

    except Exception as e:
        logger.error(f"[TTS] 语音合成异常: {e}")
        return jsonify({'error': str(e)}), 500


def _synthesize_speech(text: str, voice_id: str, target_model: str = 'cosyvoice-v2') -> str:
    """
    使用 DashScope CosyVoice TTS 将文本合成为语音

    API: POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer
    文档: https://help.aliyun.com/zh/model-studio/non-realtime-cosyvoice-api

    Returns:
        音频URL，失败返回None
    """
    max_length = 500
    if len(text) > max_length:
        text = text[:max_length] + "..."
        logger.warning(f"[TTS] 文本超过{max_length}字，已截断")

    headers = {
        'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': target_model,
        'input': {
            'text': text,
            'voice': voice_id,
            'format': 'mp3',
            'sample_rate': 22050,
        },
    }

    try:
        logger.info(f"[TTS] 合成语音: voice={voice_id}, model={target_model}, text={text[:30]}...")

        resp = requests.post(DASHSCOPE_TTS_URL, headers=headers, json=payload, timeout=60)

        if resp.status_code != 200:
            logger.error(f"[TTS] 合成失败: status={resp.status_code}, body={resp.text[:300]}")
            return None

        content_type = resp.headers.get('Content-Type', '')

        if 'audio' in content_type or (len(resp.content) > 1000 and not resp.text.strip().startswith('{')):
            temp_dir = os.path.join(os.path.dirname(__file__), '..', 'tmp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"tts_{uuid.uuid4().hex[:8]}_{int(time.time())}.mp3")
            with open(temp_path, 'wb') as f:
                f.write(resp.content)

            logger.info(f"[TTS] 音频已保存到本地: {temp_path}, 大小={len(resp.content)} bytes")

            try:
                from utils.oss import oss_client
                if oss_client.enabled:
                    oss_key = f"tts/{uuid.uuid4().hex[:8]}_{int(time.time())}.mp3"
                    oss_client.bucket.put_object(oss_key, resp.content)
                    if oss_client.cdn_domain:
                        audio_url = f"https://{oss_client.cdn_domain}/{oss_key}"
                    else:
                        audio_url = f"https://{oss_client.bucket_name}.{oss_client.endpoint}/{oss_key}"
                    logger.info(f"[TTS] 音频已上传OSS: {audio_url}")
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                    return audio_url
            except Exception as e:
                logger.error(f"[TTS] OSS上传失败: {e}")

            return f"file://{temp_path}"

        try:
            result = resp.json()
        except Exception:
            result = {}

        audio_url = None
        if isinstance(result, dict):
            output = result.get('output', {})
            if isinstance(output, dict):
                if 'audio' in output and isinstance(output['audio'], dict):
                    audio_url = output['audio'].get('url')
                elif 'url' in output:
                    audio_url = output['url']

        if audio_url:
            logger.info(f"[TTS] 合成成功: {audio_url[:80]}...")
            return audio_url

        logger.error(f"[TTS] 未能获取音频: content_type={content_type}, body_len={len(resp.content)}, resp={resp.text[:300]}")
        return None

    except Exception as e:
        logger.error(f"[TTS] 合成异常: {e}")
        import traceback
        traceback.print_exc()
        return None


# ==================== VideoRetalk 后台任务 ====================

def _poll_videoretalk_task(app, dh_id, task_id, user_id):
    """轮询 VideoRetalk 任务状态，完成后下载视频并上传 OSS"""
    max_wait = 600
    poll_interval = 10
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        with app.app_context():
            try:
                dh = DigitalHuman.query.get(dh_id)
                if not dh or dh.videoretalk_status not in ('processing', 'submitted'):
                    return

                result = videoretalk_tool.query_task(task_id)
                status = result.get('status', '')

                logger.info(f"[VideoRetalk] 轮询: task={task_id[:20]}..., status={status}, elapsed={elapsed}s")

                if status == 'SUCCEEDED' and result.get('video_url'):
                    video_url = result.get('video_url')
                    video_duration = result.get('video_duration', 0)

                    logger.info(f"[VideoRetalk] 任务完成，开始下载视频 {video_url[:80]}...")

                    oss_url = _download_and_upload_video(video_url, dh_id, user_id)

                    dh = DigitalHuman.query.get(dh_id)
                    if dh:
                        dh.videoretalk_status = 'completed'
                        dh.generated_video_url = oss_url or video_url
                        dh.generated_video_duration = video_duration
                        db.session.commit()
                        logger.info(f"[VideoRetalk] 视频生成完成: dh={dh_id}, url={dh.generated_video_url[:80]}...")
                    return

                elif status == 'FAILED':
                    error_msg = result.get('error_message', result.get('error', '任务失败'))
                    logger.error(f"[VideoRetalk] 任务失败: {error_msg}")
                    dh = DigitalHuman.query.get(dh_id)
                    if dh:
                        dh.videoretalk_status = 'failed'
                        db.session.commit()
                    return

            except Exception as e:
                logger.error(f"[VideoRetalk] 轮询异常: {e}")

    with app.app_context():
        try:
            dh = DigitalHuman.query.get(dh_id)
            if dh and dh.videoretalk_status in ('processing', 'submitted'):
                dh.videoretalk_status = 'timeout'
                db.session.commit()
                logger.warning(f"[VideoRetalk] 任务超时: dh={dh_id}")
        except Exception:
            pass


def _download_and_upload_video(video_url: str, dh_id: str, user_id: str) -> str:
    """下载 VideoRetalk 生成的视频并上传到OSS"""
    try:
        logger.info(f"[VideoRetalk] 下载视频: {video_url[:80]}...")
        response = requests.get(video_url, timeout=300)
        response.raise_for_status()
        video_content = response.content

        safe_id = re.sub(r'[^\w]', '_', dh_id)[:20]
        output_filename = f"avatar_{safe_id}_{int(time.time())}.mp4"

        local_temp_dir = os.path.join(os.path.dirname(__file__), '..', 'tmp')
        os.makedirs(local_temp_dir, exist_ok=True)
        local_temp_path = os.path.join(local_temp_dir, output_filename)

        with open(local_temp_path, 'wb') as f:
            f.write(video_content)

        logger.info(f"[VideoRetalk] 视频下载完成，大小 {len(video_content)} bytes")

        if oss_client.enabled:
            try:
                date_str = time.strftime('%Y/%m/%d')
                oss_key = f"users/{user_id}/generated/{date_str}/{output_filename}"
                oss_client.bucket.put_object(oss_key, video_content)

                if oss_client.cdn_domain:
                    oss_url = f"https://{oss_client.cdn_domain}/{oss_key}"
                else:
                    oss_url = f"https://{oss_client.bucket_name}.{oss_client.endpoint}/{oss_key}"

                logger.info(f"[VideoRetalk] 视频上传OSS成功: {oss_url}")

                try:
                    os.remove(local_temp_path)
                except Exception:
                    pass

                return oss_url
            except Exception as e:
                logger.error(f"[VideoRetalk] OSS上传失败: {e}")
                import traceback
                traceback.print_exc()

        logger.info(f"[VideoRetalk] OSS未启用，使用本地文件: {local_temp_path}")
        return video_url

    except Exception as e:
        logger.error(f"[VideoRetalk] 下载视频失败: {e}")
        import traceback
        traceback.print_exc()
        return video_url


def _check_videoretalk_status(dh):
    """检查VideoRetalk 任务状态（同步查询）"""
    if not dh.videoretalk_task_id:
        return
    try:
        result = videoretalk_tool.query_task(dh.videoretalk_task_id)
        status = result.get('status', '')

        if status == 'SUCCEEDED' and result.get('video_url'):
            if not dh.generated_video_url:
                dh.generated_video_url = result.get('video_url')
                dh.generated_video_duration = result.get('video_duration', 0)
            dh.videoretalk_status = 'completed'
            db.session.commit()
        elif status == 'FAILED':
            dh.videoretalk_status = 'failed'
            db.session.commit()
        elif status in ('PENDING', 'PRE-PROCESSING', 'RUNNING', 'POST-PROCESSING'):
            pass
    except Exception as e:
        logger.error(f"[VideoRetalk] 检查状态异常 {e}")


# ==================== 声音克隆 (已有功能，保持不变) ====================

@digital_human_bp.route('/users/<user_id>/voice-clones', methods=['GET'])
def list_voice_clones(user_id):
    try:
        voices = VoiceClone.query.filter_by(user_id=user_id).order_by(VoiceClone.updated_at.desc()).all()
        logger.info(f"[VoiceClone] Listed {len(voices)} voices for user {user_id}")
        return jsonify({'voice_clones': [v.to_dict() for v in voices]})
    except Exception as e:
        logger.error(f"[VoiceClone] List error: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/voice-clones', methods=['POST'])
def create_voice_clone():
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        title = data.get('title', '').strip()
        audio_url = data.get('audio_url')
        target_model = data.get('target_model', 'cosyvoice-v2')
        ref_text = data.get('ref_text', CLONE_REF_TEXT)
        system_voice_id = data.get('system_voice_id')
        is_system_voice = data.get('is_system_voice', False)

        logger.info(f"[VoiceClone] Create request: user={user_id}, title={title}, system_voice={system_voice_id}, is_system={is_system_voice}")

        if not user_id:
            return jsonify({'error': '缺少user_id'}), 400
        if not title:
            return jsonify({'error': '请输入声音名称'}), 400

        if is_system_voice and system_voice_id:
            vc = VoiceClone(
                user_id=user_id,
                title=title,
                audio_url=audio_url or '',
                model_type=target_model,
                ref_text=ref_text or '',
                clone_voice_id=system_voice_id,
                clone_task_id=f"system_{system_voice_id}",
                status='ready',
            )
            db.session.add(vc)
            db.session.commit()

            logger.info(f"[VoiceClone] System voice added: id={vc.id}, voice_id={system_voice_id}")
            return jsonify(vc.to_dict()), 201

        if not audio_url:
            return jsonify({'error': '缺少音频URL'}), 400

        prefix = f"mc{user_id.replace('-', '')[:8]}"

        vc = VoiceClone(
            user_id=user_id,
            title=title,
            audio_url=audio_url,
            model_type=target_model,
            ref_text=ref_text,
            status='cloning',
        )
        db.session.add(vc)
        db.session.commit()

        _start_voice_clone(vc.id, audio_url, prefix, target_model)

        logger.info(f"[VoiceClone] Created: id={vc.id}, status={vc.status}")
        return jsonify(vc.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"[VoiceClone] Create error: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/voice-clones/<vc_id>', methods=['GET'])
def get_voice_clone(vc_id):
    try:
        vc = VoiceClone.query.get(vc_id)
        if not vc:
            return jsonify({'error': '声音不存在'}), 404
        if vc.status == 'cloning':
            _check_clone_status(vc)
        return jsonify(vc.to_dict())
    except Exception as e:
        logger.error(f"[VoiceClone] Get error: {e}")
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/voice-clones/<vc_id>', methods=['DELETE'])
def delete_voice_clone(vc_id):
    try:
        vc = VoiceClone.query.get(vc_id)
        if not vc:
            return jsonify({'error': '声音不存在'}), 404
        db.session.delete(vc)
        db.session.commit()
        return jsonify({'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@digital_human_bp.route('/voice-clones/<vc_id>/preview', methods=['POST'])
def preview_voice_clone(vc_id):
    try:
        vc = VoiceClone.query.get(vc_id)
        if not vc:
            return jsonify({'error': '声音不存在'}), 404
        if not vc.clone_voice_id:
            return jsonify({'error': '声音尚未克隆完成'}), 400

        data = request.get_json(silent=True) or {}
        text = data.get('text', CLONE_REF_TEXT)
        target_model = vc.model_type or 'cosyvoice-v2'

        logger.info(f"[VoiceClone] Preview: voice_id={vc.clone_voice_id}, model={target_model}, text={text[:30]}")

        audio_url = _synthesize_speech(text, vc.clone_voice_id, target_model)

        if audio_url:
            logger.info(f"[VoiceClone] Preview audio URL: {audio_url[:100]}")
            return jsonify({'audio_url': audio_url})
        else:
            return jsonify({'error': '语音合成失败'}), 500
    except Exception as e:
        logger.error(f"[VoiceClone] Preview error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== ICE Avatar 训练 (已有功能，保持不变) ====================

def _start_avatar_training(dh_id, title, video_url, cover_url=None):
    app = current_app._get_current_object()

    def _train():
        with app.app_context():
            try:
                dh = DigitalHuman.query.get(dh_id)
                if not dh:
                    return

                dh.status = 'training'
                db.session.commit()
                logger.info(f"[Avatar] Starting training for dh={dh_id}, video_url={video_url}")

                try:
                    from utils.ice_renderer import create_ice_client
                    from alibabacloud_ice20201109 import models as ice_models

                    client = create_ice_client()

                    register_req = ice_models.RegisterMediaInfoRequest(
                        input_url=video_url,
                        media_type='video',
                        title=title,
                    )
                    register_resp = client.register_media_info(register_req)
                    media_id = register_resp.body.media_id
                    logger.info(f"[Avatar] Registered media: {media_id}")

                    train_req = ice_models.CreateAvatarTrainingJobRequest(
                        avatar_name=title[:7],
                        avatar_type='2DAvatar',
                        video=media_id,
                    )
                    if cover_url:
                        train_req.thumbnail = cover_url

                    train_resp = client.create_avatar_training_job(train_req)
                    job_id = train_resp.body.data.job_id if train_resp.body.data else None

                    if job_id:
                        dh.avatar_id = job_id
                        db.session.commit()
                        logger.info(f"[Avatar] Training job created: {job_id}")
                        _poll_avatar_status(app, dh_id, job_id)
                    else:
                        resp_str = str(train_resp.body)
                        logger.error(f"[Avatar] No job_id in response: {resp_str}")
                        dh.status = 'failed'
                        db.session.commit()

                except Exception as e:
                    logger.error(f"[Avatar] ICE API error: {e}")
                    import traceback
                    traceback.print_exc()
                    dh = DigitalHuman.query.get(dh_id)
                    if dh:
                        dh.status = 'failed'
                        db.session.commit()
            except Exception as e:
                logger.error(f"[Avatar] Training thread error: {e}")

    t = threading.Thread(target=_train, daemon=True)
    t.start()


def _poll_avatar_status(app, dh_id, job_id):
    for attempt in range(120):
        time.sleep(15)
        with app.app_context():
            try:
                dh = DigitalHuman.query.get(dh_id)
                if not dh or dh.status not in ('training',):
                    return

                from utils.ice_renderer import create_ice_client
                from alibabacloud_ice20201109 import models as ice_models

                client = create_ice_client()
                req = ice_models.GetAvatarTrainingJobRequest(job_id=job_id)
                resp = client.get_avatar_training_job(req)

                job_data = resp.body.data if resp.body.data else None
                status = job_data.status if job_data else None
                avatar_id = job_data.avatar_id if job_data else None
                thumbnail = job_data.thumbnail if job_data else None

                logger.info(f"[Avatar] Poll #{attempt}: job={job_id}, status={status}, avatar_id={avatar_id}")

                if status in ('Success', 'SUCCESS', 'Completed', 'COMPLETED', 'Finished'):
                    dh.status = 'ready'
                    if avatar_id:
                        dh.avatar_id = avatar_id
                    if thumbnail:
                        dh.cover_url = thumbnail
                    db.session.commit()
                    logger.info(f"[Avatar] Training completed: {dh_id}, avatar_id={avatar_id}")
                    return
                elif status in ('Failed', 'FAILED'):
                    dh.status = 'failed'
                    db.session.commit()
                    logger.error(f"[Avatar] Training failed: {dh_id}")
                    return

            except Exception as e:
                logger.error(f"[Avatar] Poll error: {e}")

    with app.app_context():
        try:
            dh = DigitalHuman.query.get(dh_id)
            if dh and dh.status == 'training':
                dh.status = 'failed'
                db.session.commit()
        except Exception:
            pass


def _check_avatar_status(dh):
    if not dh.avatar_id:
        return
    try:
        from utils.ice_renderer import create_ice_client
        from alibabacloud_ice20201109 import models as ice_models

        client = create_ice_client()
        req = ice_models.GetAvatarTrainingJobRequest(job_id=dh.avatar_id)
        resp = client.get_avatar_training_job(req)

        job_data = resp.body.data if resp.body.data else None
        status = job_data.status if job_data else None

        if status in ('Success', 'SUCCESS', 'Completed', 'COMPLETED', 'Finished'):
            dh.status = 'ready'
            if job_data and job_data.avatar_id:
                dh.avatar_id = job_data.avatar_id
            if job_data and job_data.thumbnail:
                dh.cover_url = job_data.thumbnail
            db.session.commit()
        elif status in ('Failed', 'FAILED'):
            dh.status = 'failed'
            db.session.commit()
    except Exception as e:
        logger.error(f"[Avatar] Check status error: {e}")


# ==================== 声音克隆后台任务 (已有功能，保持不变) ====================

def _start_voice_clone(vc_id, audio_url, prefix, target_model):
    app = current_app._get_current_object()

    def _clone():
        with app.app_context():
            try:
                vc = VoiceClone.query.get(vc_id)
                if not vc:
                    return

                headers = {
                    'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
                    'Content-Type': 'application/json',
                }
                payload = {
                    'model': 'voice-enrollment',
                    'input': {
                        'action': 'create_voice',
                        'target_model': target_model,
                        'url': audio_url,
                        'prefix': prefix,
                    },
                }

                logger.info(f"[VoiceClone] Calling Bailian API: prefix={prefix}, target_model={target_model}, url={audio_url[:80]}")

                resp = requests.post(DASHSCOPE_CUSTOMIZATION_URL, headers=headers, json=payload, timeout=60)
                result = resp.json()

                logger.info(f"[VoiceClone] Bailian API response: status={resp.status_code}, body={json.dumps(result, ensure_ascii=False)[:300]}")

                if resp.status_code != 200:
                    logger.error(f"[VoiceClone] API error: {result}")
                    vc.status = 'failed'
                    vc.clone_task_id = f"error_{resp.status_code}"
                    db.session.commit()
                    return

                voice_id = result.get('output', {}).get('voice')
                if voice_id:
                    vc.clone_voice_id = voice_id
                    vc.clone_task_id = voice_id
                    vc.status = 'ready'
                    db.session.commit()
                    logger.info(f"[VoiceClone] Clone succeeded immediately: voice_id={voice_id}")

                    _generate_preview_audio(app, vc_id, voice_id, target_model)
                else:
                    task_id = result.get('output', {}).get('task_id')
                    if task_id:
                        vc.clone_task_id = task_id
                        db.session.commit()
                        logger.info(f"[VoiceClone] Async task submitted: {task_id}")
                        _poll_clone_status(app, vc_id, task_id, target_model)
                    else:
                        logger.error(f"[VoiceClone] No voice_id or task_id in response: {result}")
                        vc.status = 'failed'
                        db.session.commit()

            except Exception as e:
                logger.error(f"[VoiceClone] Thread error: {e}")
                import traceback
                traceback.print_exc()
                try:
                    vc = VoiceClone.query.get(vc_id)
                    if vc and vc.status == 'cloning':
                        vc.status = 'failed'
                        db.session.commit()
                except Exception:
                    pass

    t = threading.Thread(target=_clone, daemon=True)
    t.start()


def _poll_clone_status(app, vc_id, task_id, target_model):
    for _ in range(60):
        time.sleep(5)
        with app.app_context():
            try:
                vc = VoiceClone.query.get(vc_id)
                if not vc or vc.status not in ('cloning',):
                    return

                headers = {'Authorization': f'Bearer {DASHSCOPE_API_KEY}'}
                resp = requests.get(
                    f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                    headers=headers, timeout=15
                )
                result = resp.json()
                task_status = result.get('output', {}).get('task_status', '')

                logger.info(f"[VoiceClone] Poll: task={task_id}, status={task_status}")

                if task_status == 'SUCCEEDED':
                    voice_id = result.get('output', {}).get('voice')
                    if not voice_id:
                        results = result.get('output', {}).get('results', [])
                        if results:
                            voice_id = results[0].get('voice_id') or results[0].get('voice')
                    vc.clone_voice_id = voice_id or vc.clone_task_id
                    vc.status = 'ready'
                    db.session.commit()
                    logger.info(f"[VoiceClone] Clone succeeded: voice_id={vc.clone_voice_id}")
                    _generate_preview_audio(app, vc_id, vc.clone_voice_id, target_model)
                    return
                elif task_status == 'FAILED':
                    vc.status = 'failed'
                    db.session.commit()
                    logger.error(f"[VoiceClone] Clone failed: {result}")
                    return
            except Exception as e:
                logger.error(f"[VoiceClone] Poll error: {e}")

    with app.app_context():
        try:
            vc = VoiceClone.query.get(vc_id)
            if vc and vc.status == 'cloning':
                vc.status = 'failed'
                db.session.commit()
        except Exception:
            pass


def _generate_preview_audio(app, vc_id, voice_id, target_model):
    try:
        logger.info(f"[VoiceClone] Generating preview audio: voice={voice_id}, model={target_model}")

        with app.app_context():
            audio_url = _synthesize_speech(CLONE_REF_TEXT, voice_id, target_model)

            if audio_url:
                vc = VoiceClone.query.get(vc_id)
                if vc:
                    vc.preview_url = audio_url
                    db.session.commit()
                    logger.info(f"[VoiceClone] Preview audio saved: {audio_url[:100]}")
            else:
                logger.error(f"[VoiceClone] Preview TTS failed for voice={voice_id}")
    except Exception as e:
        logger.error(f"[VoiceClone] Preview generation error: {e}")


def _check_clone_status(vc):
    if not vc.clone_task_id:
        return
    try:
        headers = {'Authorization': f'Bearer {DASHSCOPE_API_KEY}'}
        resp = requests.get(
            f"https://dashscope.aliyuncs.com/api/v1/tasks/{vc.clone_task_id}",
            headers=headers, timeout=15
        )
        result = resp.json()
        task_status = result.get('output', {}).get('task_status', '')
        if task_status == 'SUCCEEDED':
            voice_id = result.get('output', {}).get('voice')
            if not voice_id:
                results = result.get('output', {}).get('results', [])
                if results:
                    voice_id = results[0].get('voice_id') or results[0].get('voice')
            vc.clone_voice_id = voice_id or vc.clone_task_id
            vc.status = 'ready'
            db.session.commit()
        elif task_status == 'FAILED':
            vc.status = 'failed'
            db.session.commit()
    except Exception as e:
        logger.error(f"[VoiceClone] Check status error: {e}")
