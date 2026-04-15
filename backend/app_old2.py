#!/usr/bin/env python3
"""
MixCut Backend - New Implementation
Focus: Fast preview generation with background rendering
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import uuid
import subprocess
import threading
from itertools import product
from PIL import Image
import cv2
import time

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mixcut.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
PREVIEW_FOLDER = os.path.join(os.getcwd(), 'previews')  # Low quality previews
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')  # High quality downloads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(PREVIEW_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Task management
preview_tasks = {}  # Preview generation tasks
download_tasks = {}  # High quality download tasks


# Database Models
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), default='未命名项目')
    created_at = db.Column(db.DateTime, default=db.func.now())
    shots = db.relationship('Shot', backref='project', lazy=True, cascade='all, delete-orphan')


class Shot(db.Model):
    __tablename__ = 'shots'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    materials = db.relationship('Material', backref='shot', lazy=True, cascade='all, delete-orphan')


class Material(db.Model):
    __tablename__ = 'materials'
    id = db.Column(db.String(36), primary_key=True)
    shot_id = db.Column(db.Integer, db.ForeignKey('shots.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    original_name = db.Column(db.String(255))
    file_path = db.Column(db.String(500), nullable=False)
    thumbnail_path = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=db.func.now())


class PreviewVideo(db.Model):
    """Stores preview video generation status"""
    __tablename__ = 'preview_videos'
    id = db.Column(db.String(100), primary_key=True)  # combo_id
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    combo_index = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    preview_path = db.Column(db.String(500))
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


# Create tables
with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_image_thumbnail(image_path, thumbnail_path):
    """Generate thumbnail for image"""
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
    """Generate thumbnail for video (first frame)"""
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


def get_video_duration(video_path):
    """Get video duration in seconds"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps > 0:
        return frame_count / fps
    return 0


def format_duration(seconds):
    """Format duration as MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def calculate_total_duration(material_paths):
    """Calculate total duration for a combination"""
    total = 0
    for path in material_paths:
        if os.path.exists(path):
            ext = path.rsplit('.', 1)[1].lower()
            if ext in {'mp4', 'mov', 'avi', 'webm'}:
                total += get_video_duration(path)
            else:
                total += 3  # Images show for 3 seconds
    return total


def calculate_uniqueness_tag(materials):
    """Calculate uniqueness tag"""
    video_count = sum(1 for m in materials if m['type'] == 'video')
    if video_count == len(materials):
        return '完全不重复'
    elif video_count >= len(materials) // 2:
        return '极低重复率'
    else:
        return '普通'


def render_preview_video(combo_id, project_id, combo_index, materials):
    """Render low quality preview video in background"""
    try:
        # Update status to processing
        preview = PreviewVideo.query.get(combo_id)
        if preview:
            preview.status = 'processing'
            db.session.commit()

        # Get material files
        material_files = []
        for m in materials:
            for filename in os.listdir(UPLOAD_FOLDER):
                if filename.startswith(m['id']) and not filename.endswith('_thumb.jpg'):
                    material_files.append(os.path.join(UPLOAD_FOLDER, filename))
                    break

        if not material_files:
            raise Exception('No material files found')

        # Output path for preview
        output_filename = f"preview_{combo_id}.mp4"
        output_path = os.path.join(PREVIEW_FOLDER, output_filename)

        # Low quality settings for fast rendering
        # Use faster preset and lower quality for preview
        inputs = []
        filter_parts = []

        for i, filepath in enumerate(material_files):
            inputs.extend(['-i', filepath])
            ext = filepath.rsplit('.', 1)[1].lower()

            if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
                # For images: loop for 3 seconds at 30fps
                filter_parts.append(f'[{i}:v]loop=loop=90:size=1:start=0,scale=480:-2:force_original_aspect_ratio=decrease,pad=480:854:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
                filter_parts.append(f'[v{i}]anullsrc=channel_layout=stereo:sample_rate=44100[a{i}];')
            else:
                # For videos: scale to 480p for fast preview
                filter_parts.append(f'[{i}:v]scale=480:-2:force_original_aspect_ratio=decrease,pad=480:854:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
                filter_parts.append(f'[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];')

        # Build concat filter
        concat_v = ''.join([f'[v{i}]' for i in range(len(material_files))])
        concat_a = ''.join([f'[a{i}]' for i in range(len(material_files))])
        filter_complex = ''.join(filter_parts)
        filter_complex += f'{concat_v}concat=n={len(material_files)}:v=1:a=0[outv];'
        filter_complex += f'{concat_a}concat=n={len(material_files)}:v=0:a=1[outa]'

        cmd = [
            'ffmpeg',
            '-y',
            *inputs,
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-crf', '28',  # Lower quality for speed
            '-preset', 'ultrafast',  # Fastest preset
            '-c:a', 'aac',
            '-b:a', '96k',
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(output_path):
            # Update status to completed
            preview = PreviewVideo.query.get(combo_id)
            if preview:
                preview.status = 'completed'
                preview.preview_path = output_path
                db.session.commit()
        else:
            raise Exception(f'FFmpeg failed: {result.stderr}')

    except Exception as e:
        print(f"Preview render error for {combo_id}: {e}")
        preview = PreviewVideo.query.get(combo_id)
        if preview:
            preview.status = 'failed'
            preview.error_message = str(e)
            db.session.commit()


@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        project = Project(name='未命名项目')
        db.session.add(project)
        db.session.commit()
        return jsonify({
            'id': project.id,
            'name': project.name,
            'created_at': project.created_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details with shots and materials"""
    try:
        project = Project.query.get_or_404(project_id)
        
        shots_data = []
        for shot in sorted(project.shots, key=lambda x: x.sequence):
            materials_data = [{
                'id': mat.id,
                'type': mat.type,
                'url': f'/uploads/{os.path.basename(mat.file_path)}',
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name
            } for mat in shot.materials]
            
            shots_data.append({
                'id': shot.id,
                'name': shot.name,
                'sequence': shot.sequence,
                'materials': materials_data
            })
        
        return jsonify({
            'id': project.id,
            'name': project.name,
            'created_at': project.created_at.isoformat(),
            'shots': shots_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<int:project_id>/shots', methods=['POST'])
def create_shot(project_id):
    """Create a new shot"""
    try:
        project = Project.query.get_or_404(project_id)
        data = request.json
        
        shot = Shot(
            project_id=project_id,
            name=data.get('name', f'镜头{len(project.shots) + 1}'),
            sequence=len(project.shots)
        )
        db.session.add(shot)
        db.session.commit()
        
        return jsonify({
            'id': shot.id,
            'name': shot.name,
            'sequence': shot.sequence
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/shots/<int:shot_id>/materials', methods=['POST'])
def upload_material(shot_id):
    """Upload material to a shot"""
    try:
        shot = Shot.query.get_or_404(shot_id)
        
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # Generate unique ID and save file
        material_id = str(uuid.uuid4())
        ext = file.filename.rsplit('.', 1)[1].lower()
        
        if ext in {'mp4', 'mov', 'avi', 'webm'}:
            file_type = 'video'
            filename = f"{material_id}.mp4"
        else:
            file_type = 'image'
            filename = f"{material_id}.jpg"
        
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Generate thumbnail
        thumbnail_filename = f"{material_id}_thumb.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_filename)
        
        if file_type == 'video':
            generate_video_thumbnail(file_path, thumbnail_path)
            duration = format_duration(get_video_duration(file_path))
        else:
            generate_image_thumbnail(file_path, thumbnail_path)
            duration = '3:00'
        
        # Save to database
        material = Material(
            id=material_id,
            shot_id=shot_id,
            type=file_type,
            original_name=file.filename,
            file_path=file_path,
            thumbnail_path=thumbnail_path,
            duration=duration
        )
        db.session.add(material)
        db.session.commit()
        
        return jsonify({
            'id': material_id,
            'type': file_type,
            'url': f'/uploads/{filename}',
            'thumbnail': f'/uploads/thumbnails/{thumbnail_filename}',
            'duration': duration,
            'name': file.filename
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload and save to database"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件被上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    # Get shot_id from form data
    shot_id = request.form.get('shotId')
    if not shot_id:
        return jsonify({'error': '没有指定镜头ID'}), 400
    
    shot = Shot.query.get(shot_id)
    if not shot:
        return jsonify({'error': '镜头不存在'}), 404
    
    if file and allowed_file(file.filename):
        file_id = str(uuid.uuid4())
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{file_id}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        file.save(filepath)
        
        try:
            is_video = ext in {'mp4', 'mov', 'avi', 'webm'}
            is_image = ext in {'png', 'jpg', 'jpeg', 'gif'}
            
            thumbnail_filename = f"{file_id}_thumb.jpg"
            thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_filename)
            
            duration = None
            
            if is_image:
                generate_image_thumbnail(filepath, thumbnail_path)
            elif is_video:
                success = generate_video_thumbnail(filepath, thumbnail_path)
                if not success:
                    img = Image.new('RGB', (300, 400), (100, 100, 100))
                    img.save(thumbnail_path, 'JPEG')
                duration_seconds = get_video_duration(filepath)
                duration = format_duration(duration_seconds)
            
            # Save to database
            material = Material(
                id=file_id,
                shot_id=shot_id,
                type='video' if is_video else 'image',
                original_name=file.filename,
                file_path=filepath,
                thumbnail_path=thumbnail_path,
                duration=duration
            )
            db.session.add(material)
            db.session.commit()
            
            return jsonify({
                'id': file_id,
                'type': 'video' if is_video else 'image',
                'url': f'/uploads/{filename}',
                'thumbnail': f'/uploads/thumbnails/{thumbnail_filename}',
                'duration': duration,
                'originalName': file.filename
            })
            
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'文件处理失败: {str(e)}'}), 500
    
    return jsonify({'error': '不支持的文件类型'}), 400


@app.route('/api/materials/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete a material"""
    try:
        material = Material.query.get_or_404(material_id)
        
        # Delete files
        if os.path.exists(material.file_path):
            os.remove(material.file_path)
        if os.path.exists(material.thumbnail_path):
            os.remove(material.thumbnail_path)
        
        # Delete from database
        db.session.delete(material)
        db.session.commit()
        
        return jsonify({'message': '素材已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<int:project_id>/generate', methods=['POST'])
def generate_combinations(project_id):
    """Generate all combinations and start background preview rendering"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Clear old previews for this project
        PreviewVideo.query.filter_by(project_id=project_id).delete()
        db.session.commit()
        
        # Get all shots with materials
        shots = sorted([s for s in project.shots if s.materials], key=lambda x: x.sequence)
        
        if not shots:
            return jsonify({'error': '没有镜头包含素材'}), 400
        
        # Extract material lists
        material_lists = []
        for shot in shots:
            mat_dicts = [{
                'id': mat.id,
                'type': mat.type,
                'url': f'/uploads/{os.path.basename(mat.file_path)}',
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name,
                'file_path': mat.file_path
            } for mat in shot.materials]
            material_lists.append(mat_dicts)
        
        # Generate all combinations
        all_combos = list(product(*material_lists))
        total_possible = len(all_combos)
        limit = min(total_possible, 100)
        
        combinations = []
        for combo_index, combo in enumerate(all_combos[:limit]):
            combo_id = f"combo_{project_id}_{combo_index}"
            
            material_paths = [m['file_path'] for m in combo]
            total_duration = calculate_total_duration(material_paths)
            cover_thumbnail = combo[0]['thumbnail'] if combo else ''
            
            combo_data = {
                'id': combo_id,
                'index': combo_index,
                'materials': list(combo),
                'thumbnail': cover_thumbnail,
                'duration': format_duration(total_duration),
                'duration_seconds': total_duration,
                'tag': calculate_uniqueness_tag(combo),
                'preview_status': 'pending',
                'preview_url': None
            }
            combinations.append(combo_data)
            
            # Create preview video record
            preview = PreviewVideo(
                id=combo_id,
                project_id=project_id,
                combo_index=combo_index,
                status='pending'
            )
            db.session.add(preview)
        
        db.session.commit()
        
        # Start background rendering for all previews
        for combo in combinations:
            thread = threading.Thread(
                target=render_preview_video,
                args=(combo['id'], project_id, combo['index'], combo['materials'])
            )
            thread.daemon = True
            thread.start()
        
        return jsonify({
            'total': len(combinations),
            'total_possible': total_possible,
            'combinations': combinations
        })
        
    except Exception as e:
        return jsonify({'error': f'生成组合失败: {str(e)}'}), 500


@app.route('/api/projects/<int:project_id>/previews/status', methods=['GET'])
def get_preview_status(project_id):
    """Get preview generation status for all combinations in a project"""
    try:
        previews = PreviewVideo.query.filter_by(project_id=project_id).all()
        
        status_list = []
        for preview in previews:
            status_list.append({
                'combo_id': preview.id,
                'status': preview.status,
                'preview_url': f'/previews/{os.path.basename(preview.preview_path)}' if preview.preview_path and preview.status == 'completed' else None
            })
        
        return jsonify({
            'total': len(status_list),
            'completed': sum(1 for s in status_list if s['status'] == 'completed'),
            'statuses': status_list
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """Generate high quality video for download"""
    try:
        # Parse combo_id
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        project_id = int(parts[1])
        combo_index = int(parts[2])
        
        # Get materials from database
        project = Project.query.get_or_404(project_id)
        shots = sorted([s for s in project.shots if s.materials], key=lambda x: x.sequence)
        
        material_lists = []
        for shot in shots:
            mat_dicts = [{
                'id': mat.id,
                'type': mat.type,
                'file_path': mat.file_path
            } for mat in shot.materials]
            material_lists.append(mat_dicts)
        
        all_combos = list(product(*material_lists))
        if combo_index >= len(all_combos):
            return jsonify({'error': '组合索引超出范围'}), 404
        
        materials = all_combos[combo_index]
        
        # Get quality settings
        quality = request.json.get('quality', 'medium')
        quality_settings = {
            'low': {'scale': '720:1280', 'crf': '23', 'preset': 'veryfast'},
            'medium': {'scale': '1080:1920', 'crf': '20', 'preset': 'fast'},
            'high': {'scale': '1440:2560', 'crf': '18', 'preset': 'medium'},
            'ultra': {'scale': '2160:3840', 'crf': '15', 'preset': 'slow'}
        }
        settings = quality_settings.get(quality, quality_settings['medium'])
        
        # Create download task
        task_id = f"download_{uuid.uuid4().hex[:8]}"
        download_tasks[task_id] = {
            'id': task_id,
            'combo_id': combo_id,
            'status': 'processing',
            'progress': 0
        }
        
        # Start rendering in background
        def render_download():
            try:
                material_files = [m['file_path'] for m in materials]
                output_filename = f"download_{combo_id}_{quality}.mp4"
                output_path = os.path.join(DOWNLOAD_FOLDER, output_filename)
                
                inputs = []
                filter_parts = []
                
                for i, filepath in enumerate(material_files):
                    inputs.extend(['-i', filepath])
                    ext = filepath.rsplit('.', 1)[1].lower()
                    
                    if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
                        filter_parts.append(f'[{i}:v]loop=loop=90:size=1:start=0,scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
                        filter_parts.append(f'[v{i}]anullsrc=channel_layout=stereo:sample_rate=44100[a{i}];')
                    else:
                        filter_parts.append(f'[{i}:v]scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
                        filter_parts.append(f'[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];')
                
                concat_v = ''.join([f'[v{i}]' for i in range(len(material_files))])
                concat_a = ''.join([f'[a{i}]' for i in range(len(material_files))])
                filter_complex = ''.join(filter_parts)
                filter_complex += f'{concat_v}concat=n={len(material_files)}:v=1:a=0[outv];'
                filter_complex += f'{concat_a}concat=n={len(material_files)}:v=0:a=1[outa]'
                
                cmd = [
                    'ffmpeg',
                    '-y',
                    *inputs,
                    '-filter_complex', filter_complex,
                    '-map', '[outv]',
                    '-map', '[outa]',
                    '-c:v', 'libx264',
                    '-crf', settings['crf'],
                    '-preset', settings['preset'],
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-pix_fmt', 'yuv420p',
                    '-r', '30',
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    download_tasks[task_id]['status'] = 'completed'
                    download_tasks[task_id]['video_url'] = f'/downloads/{output_filename}'
                else:
                    download_tasks[task_id]['status'] = 'failed'
                    download_tasks[task_id]['error'] = result.stderr
                    
            except Exception as e:
                download_tasks[task_id]['status'] = 'failed'
                download_tasks[task_id]['error'] = str(e)
        
        thread = threading.Thread(target=render_download)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'task_id': task_id,
            'status': 'processing'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Get download task status"""
    if task_id not in download_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = download_tasks[task_id]
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


# Static file serving
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_FOLDER, filename)


@app.route('/previews/<path:filename>')
def serve_preview(filename):
    return send_from_directory(PREVIEW_FOLDER, filename)


@app.route('/downloads/<path:filename>')
def serve_download(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002, debug=True)
