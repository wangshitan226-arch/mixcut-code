"""
WebSocket extension for real-time transcode status updates
"""
from flask_socketio import SocketIO, emit
from flask import request
import os
import time

# Initialize SocketIO - 使用简单配置避免兼容性问题
socketio = SocketIO(cors_allowed_origins="*")

# Track connected users
connected_users = {}


def init_websocket(app):
    """Initialize WebSocket with Flask app"""
    socketio.init_app(app, cors_allowed_origins="*")
    return socketio


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    try:
        sid = request.sid if request else 'unknown'
        print(f'[WebSocket] Client connected: {sid}')
        emit('connected', {'message': 'Connected to MixCut WebSocket', 'sid': sid})
    except Exception as e:
        print(f'[WebSocket] Connect error: {e}')


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    try:
        sid = request.sid if request else 'unknown'
        print(f'[WebSocket] Client disconnected: {sid}')
        # Remove user from tracking
        for user_id, user_sid in list(connected_users.items()):
            if user_sid == sid:
                del connected_users[user_id]
                print(f'[WebSocket] Removed user {user_id} from tracking')
                break
    except Exception as e:
        print(f'[WebSocket] Disconnect error: {e}')


@socketio.on('register')
def handle_register(data):
    """Register user for transcode notifications"""
    try:
        user_id = data.get('user_id')
        sid = request.sid if request else 'unknown'
        if user_id:
            connected_users[user_id] = sid
            print(f'[WebSocket] User registered: {user_id} with sid {sid}')
            emit('registered', {'user_id': user_id, 'status': 'success', 'sid': sid})
        else:
            emit('registered', {'status': 'error', 'message': 'No user_id provided'})
    except Exception as e:
        print(f'[WebSocket] Register error: {e}')
        emit('registered', {'status': 'error', 'message': str(e)})


def emit_transcode_complete(user_id, material_id, task_id):
    """Emit transcode complete event to specific user"""
    try:
        if user_id in connected_users:
            sid = connected_users[user_id]
            socketio.emit('transcode_complete', {
                'material_id': material_id,
                'task_id': task_id,
                'status': 'completed',
                'timestamp': int(time.time())
            }, room=sid)
            print(f'[WebSocket] Emitted transcode_complete to user {user_id}, material {material_id}')
            return True
        else:
            print(f'[WebSocket] User {user_id} not connected, cannot emit transcode_complete')
            return False
    except Exception as e:
        print(f'[WebSocket] Error emitting transcode_complete: {e}')
        return False


def emit_transcode_progress(user_id, material_id, task_id, progress):
    """Emit transcode progress event to specific user"""
    try:
        if user_id in connected_users:
            sid = connected_users[user_id]
            socketio.emit('transcode_progress', {
                'material_id': material_id,
                'task_id': task_id,
                'progress': progress,
                'timestamp': int(time.time())
            }, room=sid)
            return True
        return False
    except Exception as e:
        print(f'[WebSocket] Error emitting transcode_progress: {e}')
        return False
