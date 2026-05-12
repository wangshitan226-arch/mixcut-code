#!/usr/bin/env python3
"""
MixCut Backend - Refactored with User-based Architecture
Focus: Upload-time transcoding + fast concat + Data Isolation + User Auth
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
import subprocess
import threading
from itertools import product
from PIL import Image
import cv2
import json
import time
import re
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mixcut_refactored.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
UNIFIED_FOLDER = os.path.join(os.getcwd(), 'unified')
RENDERS_FOLDER = os.path.join(os.getcwd(), 'renders')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(UNIFIED_FOLDER, exist_ok=True)
os.makedirs(RENDERS_FOLDER, exist_ok=True)

# Task management
render_tasks = {}
transcode_tasks = {}


# ==================== Database Models ====================

class User(db.Model):
    """User model supporting both anonymous and registered users"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = db.Column(db.String(20), default='anonymous', nullable=False)
    
    # Registration fields (nullable for anonymous users)
    username = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    
    # Profile fields
    nickname = db.Column(db.String(50), nullable=True)
    avatar = db.Column(db.String(500), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    last_login_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    shots = db.relationship('Shot', backref='user', lazy=True, cascade='all, delete-orphan')
    materials = db.relationship('Material', backref='user', lazy=True, cascade='all, delete-orphan')
    renders = db.relationship('Render', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'type': self.type,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'nickname': self.nickname,
            'avatar': self.avatar,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }
        return data


class Shot(db.Model):
    __tablename__ = 'shots'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    materials = db.relationship('Material', backref='shot', lazy=True, cascade='all, delete-orphan')


class Material(db.Model):
    __tablename__ = 'materials'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    shot_id = db.Column(db.Integer, db.ForeignKey('shots.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    original_name = db.Column(db.String(255))
    file_path = db.Column(db.String(500), nullable=False)
    unified_path = db.Column(db.String(500))
    thumbnail_path = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=db.func.now())


class Render(db.Model):
    __tablename__ = 'renders'
    id = db.Column(db.String(100), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    combo_index = db.Column(db.Integer, nullable=False)
    material_ids = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(50))
    duration = db.Column(db.String(10))
    duration_seconds = db.Column(db.Float)
    thumbnail = db.Column(db.String(500))
    file_path = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=db.func.now())


# Create tables
with app.app_context():
    db.create_all()


# ==================== Helper Functions ====================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_quality_settings(quality):
    settings = {
        'low': {'scale': '720:1280', 'crf': '23', 'preset': 'ultrafast'},
        'medium': {'scale': '1080:1920', 'crf': '23', 'preset': 'superfast'},
        'high': {'scale': '1440:2560', 'crf': '22', 'preset': 'veryfast'},
        'ultra': {'scale': '2160:3840', 'crf': '20', 'preset': 'faster'}
    }
    return settings.get(quality, settings['medium'])


def transcode_to_unified(input_path, output_path, quality='medium'):
    settings = get_quality_settings(quality)
    ext = input_path.rsplit('.', 1)[1].lower()
    
    if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', input_path,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30',
            '-c:v', 'libx264',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-t', '3',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_path
        ]
    else:
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30',
            '-c:v', 'libx264',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-ac', '2',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_path
        ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_image_thumbnail(image_path, thumbnail_path):
    with Image.open(image_path) as img:
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.thumbnail((300, 400), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (300, 400), (200, 200, 200))
        x = (300 - img.width) // 2
        y = (400 - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(thumbnail_path, 'JPEG', quality=80)


def generate_video_thumbnail(video_path, thumbnail_path):
    cap = cv2.VideoCapture(video_path)
    success, frame = cap.read()
    if success:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        img.thumbnail((300, 400), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (300, 400), (200, 200, 200))
        x = (300 - img.width) // 2
        y = (400 - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(thumbnail_path, 'JPEG', quality=80)
    cap.release()
    return success


def get_video_duration(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps > 0:
        return frame_count / fps
    return 0


def format_duration(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def fast_concat_videos(unified_files, output_path):
    if not unified_files:
        return False
    
    files_with_audio = []
    for filepath in unified_files:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a',
               '-show_entries', 'stream=codec_type', '-of',
               'default=noprint_wrappers=1:nokey=1', filepath]
        result = subprocess.run(cmd, capture_output=True, text=True)
        has_audio = 'audio' in result.stdout
        files_with_audio.append((filepath, has_audio))
    
    all_have_audio = all(has_audio for _, has_audio in files_with_audio)
    
    list_file = os.path.join(RENDERS_FOLDER, f"list_{uuid.uuid4().hex[:8]}.txt")
    with open(list_file, 'w') as f:
        for filepath, _ in files_with_audio:
            abs_path = os.path.abspath(filepath)
            f.write(f"file '{abs_path}'\n")
    
    try:
        if all_have_audio:
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                '-movflags', '+faststart',
                output_path
            ]
        else:
            processed_files = []
            temp_files = []
            
            try:
                for i, (filepath, has_audio) in enumerate(files_with_audio):
                    if has_audio:
                        processed_files.append(filepath)
                    else:
                        temp_output = os.path.join(RENDERS_FOLDER, f"temp_{uuid.uuid4().hex[:8]}_{i}.mp4")
                        temp_files.append(temp_output)
                        
                        cmd = [
                            'ffmpeg', '-y',
                            '-i', filepath,
                            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                            '-c:v', 'copy',
                            '-c:a', 'aac',
                            '-b:a', '128k',
                            '-ar', '44100',
                            '-ac', '2',
                            '-shortest',
                            '-movflags', '+faststart',
                            temp_output
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            processed_files.append(temp_output)
                        else:
                            processed_files.append(filepath)
                
                with open(list_file, 'w') as f:
                    for filepath in processed_files:
                        abs_path = os.path.abspath(filepath)
                        f.write(f"file '{abs_path}'\n")
                
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', list_file,
                    '-c', 'copy',
                    '-movflags', '+faststart',
                    output_path
                ]
            finally:
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg concat error: {result.stderr}")
        return result.returncode == 0
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


# ==================== Auth Helper Functions ====================

def validate_username(username):
    """Validate username: 3-20 chars, alphanumeric and underscore"""
    if not username:
        return False, "用户名不能为空"
    if len(username) < 3 or len(username) > 20:
        return False, "用户名长度需在3-20个字符之间"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "用户名只能包含字母、数字和下划线"
    return True, None


def validate_password(password):
    """Validate password: at least 6 chars"""
    if not password:
        return False, "密码不能为空"
    if len(password) < 6:
        return False, "密码长度至少为6个字符"
    return True, None


def validate_email(email):
    """Validate email format"""
    if not email:
        return False, "邮箱不能为空"
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "邮箱格式不正确"
    return True, None


def validate_phone(phone):
    """Validate phone number: Chinese mobile format"""
    if not phone:
        return False, "手机号不能为空"
    pattern = r'^1[3-9]\d{9}$'
    if not re.match(pattern, phone):
        return False, "手机号格式不正确"
    return True, None


# ==================== User Auth APIs ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json or {}
        
        # Get registration info
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        password = data.get('password', '')
        nickname = data.get('nickname', '').strip()
        
        # Validate at least one of username/email/phone is provided
        if not username and not email and not phone:
            return jsonify({'error': '请提供用户名、邮箱或手机号'}), 400
        
        # Validate inputs
        if username:
            valid, error = validate_username(username)
            if not valid:
                return jsonify({'error': error}), 400
            # Check if username exists
            if User.query.filter_by(username=username).first():
                return jsonify({'error': '用户名已被注册'}), 400
        
        if email:
            valid, error = validate_email(email)
            if not valid:
                return jsonify({'error': error}), 400
            # Check if email exists
            if User.query.filter_by(email=email).first():
                return jsonify({'error': '邮箱已被注册'}), 400
        
        if phone:
            valid, error = validate_phone(phone)
            if not valid:
                return jsonify({'error': error}), 400
            # Check if phone exists
            if User.query.filter_by(phone=phone).first():
                return jsonify({'error': '手机号已被注册'}), 400
        
        # Validate password
        valid, error = validate_password(password)
        if not valid:
            return jsonify({'error': error}), 400
        
        # Create new user
        user = User(
            type='registered',
            username=username or None,
            email=email or None,
            phone=phone or None,
            password_hash=generate_password_hash(password),
            nickname=nickname or username or '用户' + str(uuid.uuid4().hex[:6]),
            is_active=True
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': '注册成功',
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user with username/email/phone + password"""
    try:
        data = request.json or {}
        
        account = data.get('account', '').strip()  # username/email/phone
        password = data.get('password', '')
        
        if not account:
            return jsonify({'error': '请输入用户名、邮箱或手机号'}), 400
        if not password:
            return jsonify({'error': '请输入密码'}), 400
        
        # Find user by username, email, or phone
        user = None
        if '@' in account:
            user = User.query.filter_by(email=account).first()
        elif account.isdigit():
            user = User.query.filter_by(phone=account).first()
        
        if not user:
            user = User.query.filter_by(username=account).first()
        
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        if user.type != 'registered':
            return jsonify({'error': '该账户不支持密码登录'}), 400
        
        if not user.is_active:
            return jsonify({'error': '账户已被禁用'}), 403
        
        # Check password
        if not user.password_hash or not check_password_hash(user.password_hash, password):
            return jsonify({'error': '密码错误'}), 401
        
        # Update last login time
        user.last_login_at = datetime.now()
        db.session.commit()
        
        return jsonify({
            'message': '登录成功',
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user (client-side should clear localStorage)"""
    return jsonify({'message': '退出登录成功'})


@app.route('/api/auth/change-password', methods=['POST'])
def change_password():
    """Change user password"""
    try:
        data = request.json or {}
        user_id = data.get('user_id')
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not user_id:
            return jsonify({'error': '缺少用户ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        if user.type != 'registered':
            return jsonify({'error': '该账户不支持修改密码'}), 400
        
        # Verify old password
        if not user.password_hash or not check_password_hash(user.password_hash, old_password):
            return jsonify({'error': '原密码错误'}), 401
        
        # Validate new password
        valid, error = validate_password(new_password)
        if not valid:
            return jsonify({'error': error}), 400
        
        # Update password
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({'message': '密码修改成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/profile', methods=['GET'])
def get_profile():
    """Get user profile"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少用户ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        return jsonify({
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/profile', methods=['PUT'])
def update_profile():
    """Update user profile"""
    try:
        data = request.json or {}
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': '缺少用户ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # Update allowed fields
        if 'nickname' in data:
            nickname = data['nickname'].strip()
            if nickname:
                user.nickname = nickname[:50]
        
        if 'avatar' in data:
            user.avatar = data['avatar']
        
        db.session.commit()
        
        return jsonify({
            'message': '资料更新成功',
            'user': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== User APIs (Anonymous) ====================

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new anonymous user"""
    try:
        user = User(type='anonymous')
        db.session.add(user)
        db.session.commit()
        return jsonify({
            'id': user.id,
            'type': user.type,
            'created_at': user.created_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get user details with shots and materials"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        shots_data = []
        for shot in sorted(user.shots, key=lambda x: x.sequence):
            materials_data = [{
                'id': mat.id,
                'type': mat.type,
                'url': f'/uploads/{os.path.basename(mat.file_path)}',
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name,
                'transcode_status': 'completed' if mat.unified_path else 'pending'
            } for mat in shot.materials]
            
            shots_data.append({
                'id': shot.id,
                'name': shot.name,
                'sequence': shot.sequence,
                'materials': materials_data
            })
        
        return jsonify({
            'id': user.id,
            'type': user.type,
            'nickname': user.nickname,
            'created_at': user.created_at.isoformat(),
            'shots': shots_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== Shots APIs ====================

@app.route('/api/shots', methods=['GET'])
def get_shots():
    """Get all shots for a user"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': '缺少user_id参数'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        shots_data = []
        for shot in sorted(user.shots, key=lambda x: x.sequence):
            materials_data = [{
                'id': mat.id,
                'type': mat.type,
                'url': f'/uploads/{os.path.basename(mat.file_path)}',
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name,
                'transcode_status': 'completed' if mat.unified_path else 'pending'
            } for mat in shot.materials]
            
            shots_data.append({
                'id': shot.id,
                'name': shot.name,
                'sequence': shot.sequence,
                'materials': materials_data
            })
        
        return jsonify({'shots': shots_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/shots', methods=['POST'])
def create_shot():
    """Create a new shot for a user"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': '缺少user_id'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        shot_count = len(user.shots)
        shot = Shot(
            user_id=user_id,
            name=data.get('name', f'镜头{shot_count + 1}'),
            sequence=shot_count
        )
        db.session.add(shot)
        db.session.commit()
        
        return jsonify({
            'id': shot.id,
            'name': shot.name,
            'sequence': shot.sequence,
            'materials': []
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/shots/<int:shot_id>', methods=['DELETE'])
def delete_shot(shot_id):
    """Delete a shot and all its materials"""
    try:
        shot = Shot.query.get_or_404(shot_id)
        
        for material in shot.materials:
            for path in [material.file_path, material.unified_path, material.thumbnail_path]:
                if path and os.path.exists(path):
                    os.remove(path)
        
        db.session.delete(shot)
        db.session.commit()
        
        return jsonify({'message': '镜头已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== Upload API ====================

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload file and start async transcoding"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        user_id = request.form.get('user_id')
        shot_id = request.form.get('shotId')
        quality = request.form.get('quality', 'medium')
        
        if not user_id:
            return jsonify({'error': '没有指定用户ID'}), 400
        
        if not shot_id:
            return jsonify({'error': '没有指定镜头ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        try:
            shot_id = int(shot_id)
        except ValueError:
            return jsonify({'error': '无效的镜头ID'}), 400
        
        shot = Shot.query.get(shot_id)
        if not shot or shot.user_id != user_id:
            return jsonify({'error': '镜头不存在或无权限'}), 404
        
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400
        
        material_id = str(uuid.uuid4())
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{material_id}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        thumbnail_filename = f"{material_id}_thumb.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_filename)
        
        is_video = ext in {'mp4', 'mov', 'avi', 'webm'}
        
        if is_video:
            generate_video_thumbnail(filepath, thumbnail_path)
            duration = format_duration(get_video_duration(filepath))
        else:
            generate_image_thumbnail(filepath, thumbnail_path)
            duration = '0:03'
        
        unified_filename = f"{material_id}_unified.mp4"
        unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
        
        material = Material(
            id=material_id,
            user_id=user_id,
            shot_id=shot_id,
            type='video' if is_video else 'image',
            original_name=file.filename,
            file_path=filepath,
            unified_path=None,
            thumbnail_path=thumbnail_path,
            duration=duration
        )
        db.session.add(material)
        db.session.commit()
        
        task_id = f"transcode_{material_id}"
        thread = threading.Thread(
            target=async_transcode_task,
            args=(task_id, material_id, filepath, unified_path, quality)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'id': material_id,
            'type': 'video' if is_video else 'image',
            'url': f'/uploads/{filename}',
            'thumbnail': f'/uploads/thumbnails/{thumbnail_filename}',
            'duration': duration,
            'originalName': file.filename,
            'transcode_task_id': task_id,
            'transcode_status': 'processing'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def async_transcode_task(task_id, material_id, input_path, output_path, quality):
    """Background transcoding task"""
    transcode_tasks[task_id] = {
        'id': task_id,
        'material_id': material_id,
        'status': 'processing',
        'progress': 0
    }
    
    try:
        transcode_tasks[task_id]['progress'] = 50
        success = transcode_to_unified(input_path, output_path, quality)
        
        if success:
            with app.app_context():
                material = Material.query.get(material_id)
                if material:
                    material.unified_path = output_path
                    db.session.commit()
                    print(f"Transcode completed: {material_id}")
                else:
                    print(f"Material not found: {material_id}")
            transcode_tasks[task_id]['status'] = 'completed'
            transcode_tasks[task_id]['progress'] = 100
        else:
            transcode_tasks[task_id]['status'] = 'failed'
            print(f"Transcode failed: {material_id}")
    except Exception as e:
        transcode_tasks[task_id]['status'] = 'failed'
        transcode_tasks[task_id]['error'] = str(e)
        print(f"Transcode error: {material_id} - {str(e)}")


@app.route('/api/transcode/<task_id>/status', methods=['GET'])
def get_transcode_status(task_id):
    """Get transcoding task status"""
    if task_id not in transcode_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = transcode_tasks[task_id]
    return jsonify({
        'task_id': task_id,
        'status': task['status'],
        'progress': task.get('progress', 0)
    })


# ==================== Materials APIs ====================

@app.route('/api/materials/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete a material and cleanup related renders"""
    try:
        material = Material.query.get_or_404(material_id)
        user_id = material.user_id
        
        for path in [material.file_path, material.unified_path, material.thumbnail_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Failed to delete {path}: {e}")
        
        cleanup_renders_with_material(user_id, material_id)
        
        db.session.delete(material)
        db.session.commit()
        
        return jsonify({'message': '素材已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def cleanup_renders_with_material(user_id, material_id):
    """Delete all renders that contain a specific material"""
    try:
        renders = Render.query.filter_by(user_id=user_id).all()
        for render in renders:
            try:
                material_ids = json.loads(render.material_ids)
                if material_id in material_ids:
                    if render.file_path and os.path.exists(render.file_path):
                        try:
                            os.remove(render.file_path)
                        except:
                            pass
                    db.session.delete(render)
            except:
                continue
        db.session.commit()
    except Exception as e:
        print(f"Error cleaning up renders: {e}")


# ==================== Generate APIs ====================

@app.route('/api/generate', methods=['POST'])
def generate_combinations():
    """Generate combinations metadata for a user"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': '缺少user_id'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        clear_user_renders(user_id)
        
        shots = sorted([s for s in user.shots if s.materials], key=lambda x: x.sequence)
        
        if not shots:
            return jsonify({'error': '没有镜头包含素材'}), 400
        
        material_lists = []
        for shot in shots:
            mat_dicts = [{
                'id': mat.id,
                'type': mat.type,
                'unified_path': mat.unified_path,
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name
            } for mat in shot.materials if mat.unified_path and os.path.exists(mat.unified_path)]
            material_lists.append(mat_dicts)
        
        all_combos = list(product(*material_lists))
        total_possible = len(all_combos)
        limit = min(total_possible, 1000)
        
        combinations = []
        for combo_index, combo in enumerate(all_combos[:limit]):
            combo_id = f"combo_{user_id}_{combo_index}"
            
            total_duration = sum([
                3 if m['type'] == 'image' else
                get_video_duration(m['unified_path'])
                for m in combo
            ])
            
            material_ids = json.dumps([m['id'] for m in combo])
            render = Render(
                id=combo_id,
                user_id=user_id,
                combo_index=combo_index,
                material_ids=material_ids,
                tag=calculate_uniqueness_tag(combo),
                duration=format_duration(total_duration),
                duration_seconds=total_duration,
                thumbnail=combo[0]['thumbnail'] if combo else '',
                file_path=None,
                status='pending'
            )
            db.session.add(render)
            
            combo_data = {
                'id': combo_id,
                'index': combo_index,
                'materials': list(combo),
                'thumbnail': combo[0]['thumbnail'] if combo else '',
                'duration': format_duration(total_duration),
                'duration_seconds': total_duration,
                'tag': calculate_uniqueness_tag(combo),
                'preview_status': 'pending',
                'preview_url': None
            }
            combinations.append(combo_data)
        
        db.session.commit()
        
        return jsonify({
            'total': len(combinations),
            'total_possible': total_possible,
            'combinations': combinations
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def calculate_uniqueness_tag(materials):
    """Calculate uniqueness tag"""
    video_count = sum(1 for m in materials if m['type'] == 'video')
    if video_count == len(materials):
        return '完全不重复'
    elif video_count >= len(materials) // 2:
        return '极低重复率'
    else:
        return '普通'


def clear_user_renders(user_id):
    """Clear all renders for a user"""
    try:
        renders = Render.query.filter_by(user_id=user_id).all()
        for render in renders:
            if render.file_path and os.path.exists(render.file_path):
                try:
                    os.remove(render.file_path)
                except:
                    pass
        
        Render.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        print(f"Cleared all renders for user {user_id}")
    except Exception as e:
        print(f"Error clearing renders: {e}")


# ==================== Renders APIs ====================

@app.route('/api/renders', methods=['GET'])
def get_renders():
    """Get all renders for a user"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': '缺少user_id参数'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        renders = Render.query.filter_by(user_id=user_id).order_by(Render.combo_index).all()
        
        if not renders:
            return jsonify({'combinations': []})
        
        combinations = []
        for render in renders:
            file_exists = render.file_path and os.path.exists(render.file_path)
            
            try:
                material_ids = json.loads(render.material_ids)
            except:
                material_ids = []
            
            materials_data = []
            for mat_id in material_ids:
                material = Material.query.get(mat_id)
                if material and material.user_id == user_id:
                    materials_data.append({
                        'id': material.id,
                        'type': material.type,
                        'url': f'/uploads/{os.path.basename(material.file_path)}',
                        'thumbnail': f'/uploads/thumbnails/{os.path.basename(material.thumbnail_path)}',
                        'duration': material.duration,
                        'name': material.original_name
                    })
            
            combo_data = {
                'id': render.id,
                'index': render.combo_index,
                'materials': materials_data,
                'thumbnail': render.thumbnail,
                'duration': render.duration,
                'duration_seconds': render.duration_seconds,
                'tag': render.tag,
                'preview_status': 'completed' if file_exists else 'pending',
                'preview_url': f'/renders/{os.path.basename(render.file_path)}' if file_exists else None
            }
            combinations.append(combo_data)
        
        return jsonify({'combinations': combinations})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/combinations/<combo_id>/render', methods=['POST'])
def render_combination_video(combo_id):
    """On-demand render preview video for a combination"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        user_id = parts[1]
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        render = Render.query.get(combo_id)
        if not render or render.user_id != user_id:
            return jsonify({'error': '组合不存在'}), 404
        
        output_filename = f"render_{combo_id}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        if os.path.exists(output_path):
            render.file_path = output_path
            render.status = 'completed'
            db.session.commit()
            
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}'
            })
        
        for task_id, task in render_tasks.items():
            if task.get('combo_id') == combo_id and task['status'] == 'processing':
                return jsonify({
                    'status': 'processing',
                    'task_id': task_id,
                    'progress': task.get('progress', 0)
                })
        
        material_ids = json.loads(render.material_ids)
        material_files = []
        
        for mat_id in material_ids:
            material = Material.query.get(mat_id)
            if material and material.user_id == user_id and material.unified_path and os.path.exists(material.unified_path):
                material_files.append(material.unified_path)
        
        if not material_files:
            return jsonify({'error': '素材文件不存在'}), 404
        
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        thread = threading.Thread(
            target=fast_concat_task,
            args=(task_id, combo_id, material_files, output_path)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'processing',
            'task_id': task_id,
            'progress': 0
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def fast_concat_task(task_id, combo_id, unified_files, output_path):
    """Fast concat using -c copy"""
    render_tasks[task_id] = {
        'id': task_id,
        'combo_id': combo_id,
        'status': 'processing',
        'progress': 0,
        'output_path': output_path
    }
    
    try:
        render_tasks[task_id]['progress'] = 50
        success = fast_concat_videos(unified_files, output_path)
        
        if success and os.path.exists(output_path):
            render_tasks[task_id]['progress'] = 100
            render_tasks[task_id]['status'] = 'completed'
            render_tasks[task_id]['video_url'] = f'/renders/{os.path.basename(output_path)}'
        else:
            render_tasks[task_id]['status'] = 'failed'
            render_tasks[task_id]['error'] = 'Concat failed'
            
    except Exception as e:
        render_tasks[task_id]['status'] = 'failed'
        render_tasks[task_id]['error'] = str(e)


@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Get render task status"""
    if task_id not in render_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = render_tasks[task_id]
    response = {
        'task_id': task_id,
        'status': task['status'],
        'progress': task.get('progress', 0)
    }
    
    if task['status'] == 'completed':
        response['video_url'] = task.get('video_url')
    elif task['status'] == 'failed':
        response['error'] = task.get('error')
    
    return jsonify(response)


@app.route('/api/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """Download video"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        output_filename = f"render_{combo_id}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        if not os.path.exists(output_path):
            return jsonify({
                'status': 'failed',
                'error': '视频文件不存在，请重新生成'
            }), 404
        
        data = request.json or {}
        download_mode = data.get('mode', 'proxy')
        
        if download_mode == 'redirect':
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}',
                'download_url': f'/api/download/file?path={output_filename}&name=mixcut_{combo_id}.mp4',
                'mode': 'redirect'
            })
        else:
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}',
                'mode': 'proxy'
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/file', methods=['GET'])
def download_file():
    """Direct file download"""
    try:
        file_path = request.args.get('path')
        download_name = request.args.get('name', 'video.mp4')
        
        if not file_path:
            return jsonify({'error': '没有指定文件路径'}), 400
        
        full_path = os.path.join(RENDERS_FOLDER, os.path.basename(file_path))
        
        if not os.path.exists(full_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_from_directory(
            RENDERS_FOLDER,
            os.path.basename(file_path),
            as_attachment=True,
            download_name=download_name
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== Static Files ====================

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_FOLDER, filename)


@app.route('/renders/<path:filename>')
def serve_render(filename):
    return send_from_directory(RENDERS_FOLDER, filename)


# ==================== Cleanup ====================

def cleanup_old_renders(max_age_hours=24):
    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        cleaned_count = 0
        for filename in os.listdir(RENDERS_FOLDER):
            filepath = os.path.join(RENDERS_FOLDER, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        cleaned_count += 1
                    except:
                        pass
        
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} old render files")
    except Exception as e:
        print(f"Cleanup error: {e}")


def start_cleanup_scheduler():
    def cleanup_loop():
        while True:
            time.sleep(3600)
            cleanup_old_renders(max_age_hours=24)
    
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()


if __name__ == '__main__':
    start_cleanup_scheduler()
    app.run(host='0.0.0.0', port=3002, debug=True)
