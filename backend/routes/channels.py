"""
视频号运营 API 路由
"""
import os
import uuid
import time
import threading
import traceback
import tempfile
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from extensions import db
from models import ChannelsAccount, ChannelsPublishRecord, ChannelsVideoMonitor, ChannelsComment
from services.channels_service import (
    login_manager,
    check_login_status,
    get_cookie_path,
    ChannelsPublisher,
    ChannelsCommentMonitor,
    ChannelsAPIClient,
    VIDEO_STORAGE_DIR
)

channels_bp = Blueprint('channels', __name__, url_prefix='/api/channels')

_publish_tasks = {}


def handle_error(e):
    print(f"[Channels API Error] {e}", flush=True)
    traceback.print_exc()
    import sys
    print(f"[Channels API Error] Type: {type(e).__name__}", flush=True)
    print(f"[Channels API Error] Module: {type(e).__module__}", flush=True)
    if hasattr(e, '__cause__'):
        print(f"[Channels API Error] Cause: {e.__cause__}", flush=True)
    return jsonify({'error': str(e), 'type': type(e).__name__}), 500


@channels_bp.errorhandler(Exception)
def channels_handle_error(e):
    print(f"[Channels Error] {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
    return jsonify({'error': str(e), 'type': type(e).__name__}), 500


@channels_bp.before_request
def before_channels_request():
    print(f"[Channels Before Request] {request.method} {request.path}", flush=True)


# ==================== 账号管理 ====================

@channels_bp.route('/accounts', methods=['GET'])
def get_accounts():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少 user_id'}), 400

        accounts = ChannelsAccount.query.filter_by(user_id=user_id).all()

        result = []
        for account in accounts:
            data = account.to_dict()
            try:
                is_valid = check_login_status(str(account.id))
                if not is_valid and account.status == 'normal':
                    account.status = 'expired'
                    db.session.commit()
                data['status'] = account.status
            except Exception as e:
                print(f"检查账号 {account.id} 状态失败: {e}")
                data['status'] = account.status
            result.append(data)

        return jsonify({'accounts': result})
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/accounts', methods=['POST'])
def add_account():
    try:
        data = request.json or {}
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': '缺少 user_id'}), 400

        account = ChannelsAccount(
            user_id=user_id,
            nickname='待登录',
            cookie_path='',
            status='pending',
        )
        db.session.add(account)
        db.session.commit()

        task_id = str(account.id)

        result = login_manager.start_login(task_id)

        if 'error' in result:
            db.session.delete(account)
            db.session.commit()
            return jsonify({'error': result['error']}), 400

        return jsonify({
            'task_id': task_id,
            'status': 'opening',
            'message': '请在浏览器窗口中登录'
        })
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/login-status/<task_id>', methods=['GET'])
def get_login_status(task_id):
    try:
        status = login_manager.get_login_status(task_id)

        if status['status'] == 'success':
            user_id = request.args.get('user_id')
            if user_id:
                account = ChannelsAccount.query.get(int(task_id))
                if account:
                    account_info = status.get('account_info') or {}
                    nickname = account_info.get('nickname', '视频号账号')
                    cookie_path = get_cookie_path(task_id)
                    account.nickname = nickname
                    account.cookie_path = cookie_path
                    account.status = 'normal'
                    account.last_login_at = datetime.now()
                    db.session.commit()
                    status['account'] = account.to_dict()

        return jsonify(status)
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/login-tasks/<task_id>/cancel', methods=['POST'])
def cancel_login_task(task_id):
    try:
        login_manager.cleanup_task(task_id)
        return jsonify({'message': '登录任务已取消'})
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/accounts/<int:account_id>/relogin', methods=['POST'])
def relogin_account(account_id):
    try:
        account = ChannelsAccount.query.get(account_id)

        task_id = str(account_id)
        result = login_manager.start_login(task_id)

        if 'error' in result:
            return jsonify({'error': result['error']}), 400

        return jsonify({
            'task_id': task_id,
            'status': 'opening',
            'message': '请在浏览器窗口中重新登录'
        })
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    try:
        account = ChannelsAccount.query.get(account_id)

        if os.path.exists(account.cookie_path):
            os.remove(account.cookie_path)

        db.session.delete(account)
        db.session.commit()

        return jsonify({'message': '账号已删除'})
    except Exception as e:
        return handle_error(e)


# ==================== 发布功能 ====================

def download_video_to_local(video_url: str) -> str:
    try:
        import uuid as uuid_mod
        filename = f"video_{uuid_mod.uuid4().hex[:12]}.mp4"
        local_path = os.path.join(VIDEO_STORAGE_DIR, filename)

        print(f"[Publish] 下载视频: {video_url}")
        response = requests.get(video_url, stream=True, timeout=120)
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        file_size = os.path.getsize(local_path)
        print(f"[Publish] 视频已下载到: {local_path}, 大小: {file_size} bytes")

        if file_size < 1024:
            print(f"[Publish] 警告: 视频文件过小({file_size} bytes)，可能下载不完整")

        return local_path
    except Exception as e:
        print(f"[Publish] 下载视频失败: {e}")
        raise


@channels_bp.route('/publish', methods=['POST'])
def publish_video():
    try:
        data = request.json or {}

        user_id = data.get('user_id')
        account_id = data.get('account_id')
        render_id = data.get('render_id')
        video_url = data.get('video_path')
        title = data.get('title')
        tags = data.get('tags', '')
        description = data.get('description', '')
        cover_path = data.get('cover_path')

        if not all([user_id, account_id, video_url, title]):
            return jsonify({'error': '缺少必要参数'}), 400

        account = ChannelsAccount.query.get(account_id)
        if not account:
            return jsonify({'error': '账号不存在'}), 404

        if account.status != 'normal':
            return jsonify({'error': '账号状态异常，请重新登录'}), 400

        try:
            local_video_path = download_video_to_local(video_url)
        except Exception as e:
            return jsonify({'error': f'视频下载失败: {str(e)}'}), 400

        record = ChannelsPublishRecord(
            user_id=user_id,
            account_id=account_id,
            render_id=render_id,
            title=title,
            tags=tags,
            description=description,
            cover_url=cover_path,
            video_path=local_video_path,
            status='pending'
        )
        db.session.add(record)
        db.session.commit()

        task_id = f"publish_{record.id}"

        thread = threading.Thread(
            target=_do_publish,
            args=(task_id, record.id, account_id, local_video_path, title, tags, description, cover_path)
        )
        thread.daemon = True
        thread.start()

        _publish_tasks[task_id] = {
            'id': task_id,
            'record_id': record.id,
            'status': 'pending',
            'progress': 0,
            'stage': 'starting'
        }

        return jsonify({
            'success': True,
            'task_id': task_id,
            'record_id': record.id,
            'status': 'pending',
            'message': '发布任务已启动'
        })
    except Exception as e:
        return handle_error(e)


def _do_publish(task_id, record_id, account_id, video_path, title, tags, description, cover_path):
    task = _publish_tasks.get(task_id)
    if not task:
        print(f"[PublishTask] 任务不存在: {task_id}", flush=True)
        return

    def progress_callback(stage, progress):
        task['stage'] = stage
        task['progress'] = progress
        print(f"[PublishTask] {task_id}: {stage} - {progress}%", flush=True)

    try:
        task['status'] = 'processing'
        print(f"[PublishTask] 开始发布: task_id={task_id}, account_id={account_id}, video={video_path}, title={title}", flush=True)

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        publisher = ChannelsPublisher(str(account_id))
        result = publisher.publish_video(
            video_path=video_path,
            title=title,
            tags=tags,
            description=description,
            cover_path=cover_path,
            progress_callback=progress_callback
        )

        print(f"[PublishTask] 发布结果: {result}", flush=True)

        from extensions import db as db_ref
        record = ChannelsPublishRecord.query.get(record_id)
        if record:
            if result.get('success'):
                record.status = 'success'
                record.completed_at = datetime.now()
                task['status'] = 'success'

                try:
                    api_client = ChannelsAPIClient(str(account_id))
                    feed_id = api_client.find_video_id_by_title(title)
                    if feed_id:
                        record.platform_video_id = feed_id
                        print(f"[PublishTask] 获取到 platform_video_id: {feed_id}")
                    else:
                        print(f"[PublishTask] 未能自动获取 platform_video_id，可手动刷新")
                except Exception as e:
                    print(f"[PublishTask] 获取 platform_video_id 失败: {e}")

                db_ref.session.commit()
            else:
                record.status = 'failed'
                record.error_msg = result.get('error', '未知错误')
                task['status'] = 'failed'
                task['error'] = result.get('error')

                db_ref.session.commit()

    except Exception as e:
        print(f"[PublishTask] 发布异常: {e}", flush=True)
        traceback.print_exc()
        task['status'] = 'failed'
        task['error'] = str(e)

        try:
            from extensions import db as db_ref
            record = ChannelsPublishRecord.query.get(record_id)
            if record:
                record.status = 'failed'
                record.error_msg = str(e)
                db_ref.session.commit()
        except:
            pass


@channels_bp.route('/publish-tasks/<task_id>', methods=['GET'])
def get_publish_task(task_id):
    try:
        task = _publish_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        return jsonify(task)
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/publish-records', methods=['GET'])
def get_publish_records():
    try:
        user_id = request.args.get('user_id')
        account_id = request.args.get('account_id')
        status = request.args.get('status')

        if not user_id:
            return jsonify({'error': '缺少 user_id'}), 400

        query = ChannelsPublishRecord.query.filter_by(user_id=user_id)

        if account_id:
            query = query.filter_by(account_id=account_id)
        if status:
            query = query.filter_by(status=status)

        records = query.order_by(ChannelsPublishRecord.created_at.desc()).all()

        return jsonify({
            'records': [record.to_dict() for record in records]
        })
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/publish-records/<int:record_id>', methods=['DELETE'])
def delete_publish_record(record_id):
    try:
        record = ChannelsPublishRecord.query.get(record_id)
        db.session.delete(record)
        db.session.commit()

        return jsonify({'message': '记录已删除'})
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/publish-records/<int:record_id>/refresh', methods=['POST'])
def refresh_publish_record(record_id):
    try:
        record = ChannelsPublishRecord.query.get(record_id)

        if record.status != 'success':
            return jsonify({'error': '只能刷新已成功的发布记录'}), 400

        if record.platform_video_id:
            return jsonify({'message': '已有视频ID', 'platform_video_id': record.platform_video_id})

        try:
            api_client = ChannelsAPIClient(str(record.account_id))
            feed_id = api_client.find_video_id_by_title(record.title, max_retries=3, retry_interval=3)
            if feed_id:
                record.platform_video_id = feed_id
                db.session.commit()
                return jsonify({
                    'message': '已获取视频ID',
                    'platform_video_id': feed_id,
                    'record': record.to_dict()
                })
            else:
                return jsonify({'error': '未找到匹配的视频，请确认视频已发布成功'}), 404
        except FileNotFoundError:
            return jsonify({'error': '账号Cookie不存在，请重新登录'}), 400
        except Exception as e:
            return jsonify({'error': f'获取视频ID失败: {str(e)}'}), 500

    except Exception as e:
        return handle_error(e)


@channels_bp.route('/publish-records/<int:record_id>/set-video-id', methods=['POST'])
def set_publish_video_id(record_id):
    try:
        record = ChannelsPublishRecord.query.get(record_id)
        data = request.json or {}
        video_id = data.get('platform_video_id', '').strip()

        if not video_id:
            return jsonify({'error': '视频ID不能为空'}), 400

        record.platform_video_id = video_id
        db.session.commit()

        return jsonify({
            'message': '视频ID已设置',
            'record': record.to_dict()
        })
    except Exception as e:
        return handle_error(e)


# ==================== 评论管理 ====================

@channels_bp.route('/monitors', methods=['GET'])
def get_monitors():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少 user_id'}), 400

        monitors = ChannelsVideoMonitor.query.filter_by(user_id=user_id).all()
        return jsonify({
            'monitors': [monitor.to_dict() for monitor in monitors]
        })
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/monitors', methods=['POST'])
def create_monitor():
    try:
        data = request.json or {}

        user_id = data.get('user_id')
        account_id = data.get('account_id')
        publish_record_id = data.get('publish_record_id')
        platform_video_id = data.get('platform_video_id')

        if not all([user_id, account_id, publish_record_id, platform_video_id]):
            return jsonify({'error': '缺少必要参数'}), 400

        existing = ChannelsVideoMonitor.query.filter_by(
            publish_record_id=publish_record_id
        ).first()

        if existing:
            return jsonify({'error': '该视频已在监控中'}), 400

        monitor = ChannelsVideoMonitor(
            user_id=user_id,
            account_id=account_id,
            publish_record_id=publish_record_id,
            platform_video_id=platform_video_id,
            status='monitoring'
        )
        db.session.add(monitor)
        db.session.commit()

        return jsonify({
            'monitor': monitor.to_dict(),
            'message': '监控任务已创建'
        })
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/monitors/<int:monitor_id>/fetch', methods=['POST'])
def fetch_comments(monitor_id):
    try:
        monitor = ChannelsVideoMonitor.query.get(monitor_id)
        if not monitor:
            return jsonify({'error': '监控任务不存在'}), 404

        if monitor.status != 'monitoring':
            return jsonify({'error': '监控任务已停止'}), 400

        if not monitor.platform_video_id:
            return jsonify({'error': '缺少视频ID，请先刷新发布记录获取视频ID'}), 400

        cm = ChannelsCommentMonitor(str(monitor.account_id))
        comments = cm.fetch_comments(monitor.platform_video_id)

        new_count = 0
        high_intent_count = 0

        for comment_data in comments:
            existing = ChannelsComment.query.filter_by(
                monitor_id=monitor.id,
                content=comment_data['content']
            ).first()

            if not existing:
                comment = ChannelsComment(
                    monitor_id=monitor.id,
                    commenter_name=comment_data['commenter_name'],
                    content=comment_data['content'],
                    platform_comment_id=comment_data.get('platform_comment_id'),
                    is_high_intent=comment_data['is_high_intent'],
                    intent_keywords=comment_data.get('intent_keywords'),
                    is_new=True
                )
                db.session.add(comment)
                new_count += 1

                if comment_data['is_high_intent']:
                    high_intent_count += 1

        monitor.last_fetch_at = datetime.now()
        monitor.total_comments = ChannelsComment.query.filter_by(monitor_id=monitor.id).count()
        monitor.new_comments = ChannelsComment.query.filter_by(monitor_id=monitor.id, is_new=True).count()
        monitor.unreplied_comments = ChannelsComment.query.filter_by(
            monitor_id=monitor.id, reply_status='pending'
        ).count()
        monitor.high_intent_comments = ChannelsComment.query.filter_by(
            monitor_id=monitor.id, is_high_intent=True
        ).count()

        db.session.commit()

        return jsonify({
            'message': f'抓取完成，新增 {new_count} 条评论',
            'new_comments': new_count,
            'high_intent_count': high_intent_count,
            'total_comments': monitor.total_comments
        })
    except FileNotFoundError as e:
        return jsonify({'error': f'账号Cookie不存在，请重新登录: {str(e)}'}), 400
    except Exception as e:
        print(f"[fetch_comments ERROR] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500


@channels_bp.route('/monitors/<int:monitor_id>/comments', methods=['GET'])
def get_comments(monitor_id):
    try:
        filter_type = request.args.get('filter', 'all')

        query = ChannelsComment.query.filter_by(monitor_id=monitor_id)

        if filter_type == 'unreplied':
            query = query.filter_by(reply_status='pending')
        elif filter_type == 'replied':
            query = query.filter_by(reply_status='replied')
        elif filter_type == 'high_intent':
            query = query.filter_by(is_high_intent=True)

        comments = query.order_by(ChannelsComment.created_at.desc()).all()

        return jsonify({
            'comments': [comment.to_dict() for comment in comments]
        })
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/comments/<int:comment_id>/reply', methods=['POST'])
def reply_comment(comment_id):
    try:
        data = request.json or {}
        reply_text = data.get('reply_text')

        if not reply_text:
            return jsonify({'error': '缺少回复内容'}), 400

        comment = ChannelsComment.query.get(comment_id)
        monitor = ChannelsVideoMonitor.query.get(comment.monitor_id)

        if not monitor:
            return jsonify({'error': '监控任务不存在'}), 404

        if not monitor.platform_video_id:
            return jsonify({'error': '缺少视频ID，无法回复'}), 400

        cm = ChannelsCommentMonitor(str(monitor.account_id))
        success = cm.reply_comment(
            comment.platform_comment_id or str(comment.id),
            reply_text,
            feed_id=monitor.platform_video_id
        )

        if success:
            comment.reply_status = 'replied'
            comment.reply_content = reply_text
            comment.replied_at = datetime.now()
            db.session.commit()

            return jsonify({'message': '回复成功'})
        else:
            comment.reply_status = 'replied'
            comment.reply_content = reply_text
            comment.replied_at = datetime.now()
            db.session.commit()

            return jsonify({'message': '回复已记录（平台回复可能失败，请手动确认）'})
    except FileNotFoundError as e:
        return jsonify({'error': f'账号Cookie不存在，请重新登录: {str(e)}'}), 400
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/comments/<int:comment_id>/ignore', methods=['POST'])
def ignore_comment(comment_id):
    try:
        comment = ChannelsComment.query.get(comment_id)
        comment.reply_status = 'ignored'
        db.session.commit()

        return jsonify({'message': '已忽略'})
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/comments/<int:comment_id>/mark-read', methods=['POST'])
def mark_comment_read(comment_id):
    try:
        comment = ChannelsComment.query.get(comment_id)
        comment.is_new = False
        db.session.commit()

        return jsonify({'message': '已标记为已读'})
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/monitors/<int:monitor_id>', methods=['DELETE'])
def delete_monitor(monitor_id):
    try:
        monitor = ChannelsVideoMonitor.query.get(monitor_id)
        monitor.status = 'stopped'
        db.session.commit()

        return jsonify({'message': '监控已停止'})
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/monitors/<int:monitor_id>/auto-reply', methods=['POST'])
def update_auto_reply(monitor_id):
    try:
        data = request.json or {}
        monitor = ChannelsVideoMonitor.query.get(monitor_id)

        monitor.auto_reply_enabled = data.get('enabled', monitor.auto_reply_enabled)
        monitor.auto_reply_text = data.get('reply_text', monitor.auto_reply_text)
        monitor.auto_reply_only_high_intent = data.get('only_high_intent', monitor.auto_reply_only_high_intent)

        db.session.commit()

        return jsonify({
            'message': '自动回复配置已更新',
            'monitor': monitor.to_dict()
        })
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/monitors/<int:monitor_id>/batch-reply', methods=['POST'])
def batch_reply_comments(monitor_id):
    try:
        data = request.json or {}
        reply_text = data.get('reply_text')
        comment_ids = data.get('comment_ids', [])

        if not reply_text:
            return jsonify({'error': '缺少回复内容'}), 400

        monitor = ChannelsVideoMonitor.query.get(monitor_id)

        if not monitor.platform_video_id:
            return jsonify({'error': '缺少视频ID，无法回复'}), 400

        if not comment_ids:
            comments = ChannelsComment.query.filter_by(
                monitor_id=monitor_id,
                reply_status='pending'
            ).all()
            comment_ids = [c.id for c in comments]

        success_count = 0
        failed_count = 0

        cm = ChannelsCommentMonitor(str(monitor.account_id))
        for comment_id in comment_ids:
            comment = ChannelsComment.query.get(comment_id)
            if not comment or comment.reply_status != 'pending':
                continue

            api_success = cm.reply_comment(
                comment.platform_comment_id or str(comment.id),
                reply_text,
                feed_id=monitor.platform_video_id
            )

            comment.reply_status = 'replied'
            comment.reply_content = reply_text
            comment.replied_at = datetime.now()
            if api_success:
                success_count += 1
            else:
                failed_count += 1

        db.session.commit()

        return jsonify({
            'message': f'批量回复完成，成功 {success_count} 条，失败 {failed_count} 条',
            'success_count': success_count,
            'failed_count': failed_count
        })
    except FileNotFoundError as e:
        return jsonify({'error': f'账号Cookie不存在，请重新登录: {str(e)}'}), 400
    except Exception as e:
        return handle_error(e)


@channels_bp.route('/monitors/<int:monitor_id>/auto-fetch', methods=['POST'])
def auto_fetch_and_reply(monitor_id):
    try:
        monitor = ChannelsVideoMonitor.query.get(monitor_id)

        if monitor.status != 'monitoring':
            return jsonify({'error': '监控任务已停止'}), 400

        if not monitor.platform_video_id:
            return jsonify({'error': '缺少视频ID，请先刷新发布记录获取视频ID'}), 400

        if not monitor.auto_reply_enabled or not monitor.auto_reply_text:
            return jsonify({'error': '自动回复未配置'}), 400

        cm = ChannelsCommentMonitor(str(monitor.account_id))
        comments = cm.fetch_comments(monitor.platform_video_id)

        new_count = 0
        high_intent_count = 0

        for comment_data in comments:
            existing = ChannelsComment.query.filter_by(
                monitor_id=monitor.id,
                content=comment_data['content']
            ).first()

            if not existing:
                comment = ChannelsComment(
                    monitor_id=monitor.id,
                    commenter_name=comment_data['commenter_name'],
                    content=comment_data['content'],
                    platform_comment_id=comment_data.get('platform_comment_id'),
                    is_high_intent=comment_data['is_high_intent'],
                    intent_keywords=comment_data.get('intent_keywords'),
                    is_new=True
                )
                db.session.add(comment)
                new_count += 1

                if comment_data['is_high_intent']:
                    high_intent_count += 1

        db.session.commit()

        replied_count = 0
        if monitor.auto_reply_enabled and monitor.auto_reply_text:
            if monitor.auto_reply_only_high_intent:
                pending_comments = ChannelsComment.query.filter_by(
                    monitor_id=monitor.id,
                    reply_status='pending',
                    is_high_intent=True
                ).all()
            else:
                pending_comments = ChannelsComment.query.filter_by(
                    monitor_id=monitor.id,
                    reply_status='pending'
                ).all()

            for comment in pending_comments:
                api_success = cm.reply_comment(
                    comment.platform_comment_id or str(comment.id),
                    monitor.auto_reply_text,
                    feed_id=monitor.platform_video_id
                )

                comment.reply_status = 'replied'
                comment.reply_content = monitor.auto_reply_text
                comment.replied_at = datetime.now()
                replied_count += 1

            db.session.commit()

        monitor.last_fetch_at = datetime.now()
        monitor.total_comments = ChannelsComment.query.filter_by(monitor_id=monitor.id).count()
        monitor.new_comments = ChannelsComment.query.filter_by(monitor_id=monitor.id, is_new=True).count()
        monitor.unreplied_comments = ChannelsComment.query.filter_by(
            monitor_id=monitor.id, reply_status='pending'
        ).count()
        monitor.high_intent_comments = ChannelsComment.query.filter_by(
            monitor_id=monitor.id, is_high_intent=True
        ).count()

        db.session.commit()

        return jsonify({
            'message': f'自动抓取完成，新增 {new_count} 条评论，自动回复 {replied_count} 条',
            'new_comments': new_count,
            'high_intent_count': high_intent_count,
            'replied_count': replied_count,
            'total_comments': monitor.total_comments
        })
    except FileNotFoundError as e:
        return jsonify({'error': f'账号Cookie不存在，请重新登录: {str(e)}'}), 400
    except Exception as e:
        return handle_error(e)
