import os
import uuid
import json
import time
import logging
import requests
import threading
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import DigitalHuman, VoiceClone

digital_human_bp = Blueprint('digital_human', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', 'sk-a555a4e29a474a6989cb872de3a3070a')
DASHSCOPE_CUSTOMIZATION_URL = 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization'
DASHSCOPE_TTS_URL = 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer'

CLONE_REF_TEXT = '你好，我是你的专属AI克隆声音。I am your exclusive AI clone voice.'


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
            status='draft',
        )
        db.session.add(dh)
        db.session.commit()

        if video_url:
            _start_avatar_training(dh.id, title, video_url, cover_url)

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
            _start_avatar_training(dh.id, dh.title, dh.video_url, dh.cover_url)
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
        target_model = data.get('target_model', 'cosyvoice-v1')
        ref_text = data.get('ref_text', CLONE_REF_TEXT)

        logger.info(f"[VoiceClone] Create request: user={user_id}, title={title}, audio_url={audio_url}, target_model={target_model}")

        if not user_id:
            return jsonify({'error': '缺少user_id'}), 400
        if not title:
            return jsonify({'error': '请输入声音名称'}), 400
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
        target_model = vc.model_type or 'cosyvoice-v1'

        logger.info(f"[VoiceClone] Preview: voice_id={vc.clone_voice_id}, model={target_model}, text={text[:30]}")

        headers = {
            'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': target_model,
            'input': {
                'text': text,
            },
            'parameters': {
                'voice': vc.clone_voice_id,
                'format': 'mp3',
                'sample_rate': 22050,
            },
        }

        resp = requests.post(DASHSCOPE_TTS_URL, headers=headers, json=payload, timeout=60)
        logger.info(f"[VoiceClone] TTS response status: {resp.status_code}")

        if resp.status_code != 200:
            error_text = resp.text[:500]
            logger.error(f"[VoiceClone] TTS error: {error_text}")
            return jsonify({'error': f'语音合成失败: {error_text}'}), 500

        result = resp.json()
        audio_url = None

        if 'output' in result and 'audio' in result['output']:
            audio_url = result['output']['audio'].get('url')
        elif 'output' in result and 'results' in result['output']:
            for r in result['output']['results']:
                if 'url' in r:
                    audio_url = r['url']
                    break

        if not audio_url:
            task_id = result.get('output', {}).get('task_id')
            if task_id:
                for _ in range(30):
                    time.sleep(2)
                    task_resp = requests.get(
                        f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                        headers={'Authorization': f'Bearer {DASHSCOPE_API_KEY}'},
                        timeout=15
                    )
                    task_result = task_resp.json()
                    task_status = task_result.get('output', {}).get('task_status', '')
                    if task_status == 'SUCCEEDED':
                        audio_url = task_result.get('output', {}).get('results', [{}])[0].get('url')
                        break
                    elif task_status == 'FAILED':
                        return jsonify({'error': '语音合成失败'}), 500

        if audio_url:
            logger.info(f"[VoiceClone] Preview audio URL: {audio_url[:100]}")
            return jsonify({'audio_url': audio_url})
        else:
            return jsonify({'error': '未能获取预览音频', 'raw_response': result}), 500
    except Exception as e:
        logger.error(f"[VoiceClone] Preview error: {e}")
        return jsonify({'error': str(e)}), 500


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
        headers = {
            'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
            'Content-Type': 'application/json',
            'X-DashScope-Async': 'enable',
        }
        payload = {
            'model': target_model,
            'input': {
                'text': CLONE_REF_TEXT,
            },
            'parameters': {
                'voice': voice_id,
                'format': 'mp3',
                'sample_rate': 22050,
            },
        }

        logger.info(f"[VoiceClone] Generating preview audio: voice={voice_id}, model={target_model}")

        resp = requests.post(DASHSCOPE_TTS_URL, headers=headers, json=payload, timeout=30)
        result = resp.json()
        logger.info(f"[VoiceClone] TTS response: {json.dumps(result, ensure_ascii=False)[:300]}")

        task_id = result.get('output', {}).get('task_id')
        if task_id:
            for _ in range(30):
                time.sleep(2)
                task_resp = requests.get(
                    f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                    headers={'Authorization': f'Bearer {DASHSCOPE_API_KEY}'},
                    timeout=15
                )
                task_result = task_resp.json()
                task_status = task_result.get('output', {}).get('task_status', '')
                if task_status == 'SUCCEEDED':
                    audio_url = task_result.get('output', {}).get('results', [{}])[0].get('url')
                    if audio_url:
                        with app.app_context():
                            vc = VoiceClone.query.get(vc_id)
                            if vc:
                                vc.preview_url = audio_url
                                db.session.commit()
                                logger.info(f"[VoiceClone] Preview audio saved: {audio_url[:100]}")
                    return
                elif task_status == 'FAILED':
                    logger.error(f"[VoiceClone] Preview TTS failed: {task_result}")
                    return
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
