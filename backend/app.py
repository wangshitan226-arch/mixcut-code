#!/usr/bin/env python3
"""
MixCut Backend - Fast Implementation
Focus: Upload-time transcoding + fast concat
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
import json
import time

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mixcut_fast.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
UNIFIED_FOLDER = os.path.join(os.getcwd(), 'unified')  # Transcoded files
RENDERS_FOLDER = os.path.join(os.getcwd(), 'renders')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(UNIFIED_FOLDER, exist_ok=True)
os.makedirs(RENDERS_FOLDER, exist_ok=True)

# Task management
render_tasks = {}


# Database Models
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), default='未命名项目')
    quality = db.Column(db.String(20), default='medium')  # User selected quality
    created_at = db.Column(db.DateTime, default=db.func.now())
    shots = db.relationship('Shot', backref='project', lazy=True, cascade='all, delete-orphan')
    materials = db.relationship('Material', secondary='shots', viewonly=True, lazy='dynamic')


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
    file_path = db.Column(db.String(500), nullable=False)  # Original file
    unified_path = db.Column(db.String(500))  # Transcoded unified format
    thumbnail_path = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=db.func.now())


class Render(db.Model):
    """Stores rendered video records for persistence"""
    __tablename__ = 'renders'
    id = db.Column(db.String(100), primary_key=True)  # combo_id
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    combo_index = db.Column(db.Integer, nullable=False)
    material_ids = db.Column(db.Text, nullable=False)  # JSON array of material IDs
    tag = db.Column(db.String(50))
    duration = db.Column(db.String(10))
    duration_seconds = db.Column(db.Float)
    thumbnail = db.Column(db.String(500))
    file_path = db.Column(db.String(500))  # Path to rendered video
    status = db.Column(db.String(20), default='completed')  # completed, failed
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    project = db.relationship('Project', backref='renders', lazy=True)


# Create tables
with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_quality_settings(quality):
    """Get quality settings for transcoding - optimized for speed"""
    settings = {
        'low': {'scale': '720:1280', 'crf': '23', 'preset': 'ultrafast'},    # Fastest
        'medium': {'scale': '1080:1920', 'crf': '23', 'preset': 'superfast'}, # Fast, good quality
        'high': {'scale': '1440:2560', 'crf': '22', 'preset': 'veryfast'},    # Balanced
        'ultra': {'scale': '2160:3840', 'crf': '20', 'preset': 'faster'}     # High quality
    }
    return settings.get(quality, settings['medium'])


def transcode_to_unified(input_path, output_path, quality='medium'):
    """Transcode video/image to unified format (H.264, same resolution)"""
    settings = get_quality_settings(quality)
    ext = input_path.rsplit('.', 1)[1].lower()
    
    if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
        # For images: create 3-second video
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', input_path,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30',
            '-c:v', 'libx264',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-t', '3',  # 3 seconds
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_path
        ]
    else:
        # For videos: transcode to unified format
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
    return success


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


def fast_concat_videos(unified_files, output_path):
    """Fast concat using -c copy (no re-encoding)"""
    if not unified_files:
        return False
    
    # Check if all files have audio
    files_with_audio = []
    for filepath in unified_files:
        # Check if file has audio stream
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', 
               '-show_entries', 'stream=codec_type', '-of', 
               'default=noprint_wrappers=1:nokey=1', filepath]
        result = subprocess.run(cmd, capture_output=True, text=True)
        has_audio = 'audio' in result.stdout
        files_with_audio.append((filepath, has_audio))
    
    # If any file lacks audio, we need to add silent audio or re-encode
    all_have_audio = all(has_audio for _, has_audio in files_with_audio)
    
    # Create concat file list
    list_file = os.path.join(RENDERS_FOLDER, f"list_{uuid.uuid4().hex[:8]}.txt")
    with open(list_file, 'w') as f:
        for filepath, _ in files_with_audio:
            # Use absolute path and escape properly
            abs_path = os.path.abspath(filepath)
            f.write(f"file '{abs_path}'\n")
    
    try:
        if all_have_audio:
            # All files have audio, can use -c copy
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
            # Some files lack audio, need to handle it
            # Use anear=0 to add silent audio to files without audio, then concat with -c copy
            
            # First, process files to ensure all have audio
            processed_files = []
            temp_files = []
            
            try:
                for i, (filepath, has_audio) in enumerate(files_with_audio):
                    if has_audio:
                        processed_files.append(filepath)
                    else:
                        # Add silent audio to files without audio
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
                            processed_files.append(filepath)  # Fallback to original
                
                # Create new concat list with processed files
                with open(list_file, 'w') as f:
                    for filepath in processed_files:
                        abs_path = os.path.abspath(filepath)
                        f.write(f"file '{abs_path}'\n")
                
                # Now all files have audio, can use -c copy
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
                # Clean up temp files
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


# APIs
@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        data = request.json or {}
        project = Project(
            name=data.get('name', '未命名项目'),
            quality=data.get('quality', 'medium')
        )
        db.session.add(project)
        db.session.commit()
        return jsonify({
            'id': project.id,
            'name': project.name,
            'quality': project.quality,
            'created_at': project.created_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details"""
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    try:
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
            'quality': project.quality,
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


# Transcoding task management
transcode_tasks = {}


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
            # Update database
            material = Material.query.get(material_id)
            if material:
                material.unified_path = output_path
                db.session.commit()
            transcode_tasks[task_id]['status'] = 'completed'
            transcode_tasks[task_id]['progress'] = 100
        else:
            transcode_tasks[task_id]['status'] = 'failed'
    except Exception as e:
        transcode_tasks[task_id]['status'] = 'failed'
        transcode_tasks[task_id]['error'] = str(e)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload file and start async transcoding"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        shot_id = request.form.get('shotId')
        quality = request.form.get('quality', 'medium')
        
        if not shot_id:
            return jsonify({'error': '没有指定镜头ID'}), 400
        
        try:
            shot_id = int(shot_id)
        except ValueError:
            return jsonify({'error': '无效的镜头ID'}), 400
        
        shot = Shot.query.get(shot_id)
        if not shot:
            return jsonify({'error': '镜头不存在'}), 404
        
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # Save original file
        material_id = str(uuid.uuid4())
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{material_id}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Generate thumbnail (fast operation)
        thumbnail_filename = f"{material_id}_thumb.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_filename)
        
        is_video = ext in {'mp4', 'mov', 'avi', 'webm'}
        
        if is_video:
            generate_video_thumbnail(filepath, thumbnail_path)
            duration = format_duration(get_video_duration(filepath))
        else:
            generate_image_thumbnail(filepath, thumbnail_path)
            duration = '0:03'
        
        # Prepare unified path
        unified_filename = f"{material_id}_unified.mp4"
        unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
        
        # Save to database (without unified_path initially)
        material = Material(
            id=material_id,
            shot_id=shot_id,
            type='video' if is_video else 'image',
            original_name=file.filename,
            file_path=filepath,
            unified_path=None,  # Will be set after transcoding
            thumbnail_path=thumbnail_path,
            duration=duration
        )
        db.session.add(material)
        db.session.commit()
        
        # Start async transcoding
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
        return jsonify({'error': str(e)}), 500


def cleanup_renders_with_material(project_id, material_id):
    """Delete all renders that contain a specific material"""
    try:
        renders = Render.query.filter_by(project_id=project_id).all()
        for render in renders:
            try:
                material_ids = json.loads(render.material_ids)
                if material_id in material_ids:
                    # Delete render file
                    if render.file_path and os.path.exists(render.file_path):
                        try:
                            os.remove(render.file_path)
                        except:
                            pass
                    # Delete DB record
                    db.session.delete(render)
            except:
                continue
        db.session.commit()
    except Exception as e:
        print(f"Error cleaning up renders: {e}")


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


@app.route('/api/materials/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete a material and cleanup related renders"""
    try:
        material = Material.query.get_or_404(material_id)
        shot_id = material.shot_id
        shot = Shot.query.get(shot_id)
        project_id = shot.project_id if shot else None
        
        # Delete files
        for path in [material.file_path, material.unified_path, material.thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)
        
        # Cleanup renders that contain this material
        if project_id:
            cleanup_renders_with_material(project_id, material_id)
        
        db.session.delete(material)
        db.session.commit()
        
        return jsonify({'message': '素材已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/shots/<int:shot_id>', methods=['DELETE'])
def delete_shot(shot_id):
    """Delete a shot and all its materials"""
    try:
        shot = Shot.query.get_or_404(shot_id)
        
        # Delete all material files first
        for material in shot.materials:
            for path in [material.file_path, material.unified_path, material.thumbnail_path]:
                if path and os.path.exists(path):
                    os.remove(path)
        
        db.session.delete(shot)
        db.session.commit()
        
        return jsonify({'message': '镜头已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def clear_project_renders(project_id):
    """Clear all renders for a project - delete files and DB records"""
    try:
        # Delete all render files for this project (combo_{project_id}_*.mp4)
        prefix = f"combo_{project_id}_"
        for filename in os.listdir(RENDERS_FOLDER):
            if filename.startswith(prefix) or filename.startswith(f"render_{prefix}"):
                filepath = os.path.join(RENDERS_FOLDER, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        print(f"Deleted old render: {filename}")
                except Exception as e:
                    print(f"Failed to delete {filename}: {e}")
        
        # Delete DB records
        Render.query.filter_by(project_id=project_id).delete()
        db.session.commit()
        print(f"Cleared all renders for project {project_id}")
    except Exception as e:
        print(f"Error clearing renders: {e}")


# Task management for on-demand fast concat
render_tasks = {}


def fast_concat_task(task_id, combo_id, unified_files, output_path):
    """Fast concat using -c copy (no re-encoding) - seconds level"""
    render_tasks[task_id] = {
        'id': task_id,
        'combo_id': combo_id,
        'status': 'processing',
        'progress': 0,
        'output_path': output_path
    }
    
    try:
        render_tasks[task_id]['progress'] = 50
        
        # Use existing fast_concat_videos function
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


@app.route('/api/projects/<int:project_id>/generate', methods=['POST'])
def generate_combinations(project_id):
    """Generate combinations metadata only - no pre-rendering (on-demand strategy)"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Clear old renders first (both DB and files)
        clear_project_renders(project_id)
        
        # Get shots with materials that have unified files
        shots = sorted([s for s in project.shots if s.materials], key=lambda x: x.sequence)
        
        if not shots:
            return jsonify({'error': '没有镜头包含素材'}), 400
        
        # Generate combinations metadata only (use only transcoded materials)
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
        limit = min(total_possible, 1000)  # Increased limit since we don't pre-render
        
        combinations = []
        for combo_index, combo in enumerate(all_combos[:limit]):
            combo_id = f"combo_{project_id}_{combo_index}"
            
            total_duration = sum([
                3 if m['type'] == 'image' else 
                get_video_duration(m['unified_path']) 
                for m in combo
            ])
            
            # Save metadata to database (no video file yet)
            material_ids = json.dumps([m['id'] for m in combo])
            render = Render(
                id=combo_id,
                project_id=project_id,
                combo_index=combo_index,
                material_ids=material_ids,
                tag=calculate_uniqueness_tag(combo),
                duration=format_duration(total_duration),
                duration_seconds=total_duration,
                thumbnail=combo[0]['thumbnail'] if combo else '',
                file_path=None,  # Not rendered yet
                status='pending'  # Mark as pending
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
                'preview_status': 'pending',  # Not rendered yet
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


@app.route('/api/projects/<int:project_id>/renders', methods=['GET'])
def get_project_renders(project_id):
    """Get all rendered videos for a project (persistent storage)"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Get all renders from database
        renders = Render.query.filter_by(project_id=project_id).order_by(Render.combo_index).all()
        
        if not renders:
            return jsonify({'combinations': []})
        
        # Build response
        combinations = []
        for render in renders:
            # Check if file still exists
            file_exists = render.file_path and os.path.exists(render.file_path)
            
            # Parse material IDs
            try:
                material_ids = json.loads(render.material_ids)
            except:
                material_ids = []
            
            # Get material details from current project state
            materials_data = []
            for mat_id in material_ids:
                # Find material in current project
                for shot in project.shots:
                    for mat in shot.materials:
                        if mat.id == mat_id:
                            materials_data.append({
                                'id': mat.id,
                                'type': mat.type,
                                'url': f'/uploads/{os.path.basename(mat.file_path)}',
                                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                                'duration': mat.duration,
                                'name': mat.original_name
                            })
                            break
            
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
        
        return jsonify({
            'combinations': combinations
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/combinations/<combo_id>/render', methods=['POST'])
def render_combination_video(combo_id):
    """On-demand render preview video for a combination"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        project_id = int(parts[1])
        project = Project.query.get_or_404(project_id)
        
        # Get render record
        render = Render.query.get(combo_id)
        if not render:
            return jsonify({'error': '组合不存在'}), 404
        
        # Check if already rendered
        output_filename = f"render_{combo_id}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        if os.path.exists(output_path):
            # Update DB record
            render.file_path = output_path
            render.status = 'completed'
            db.session.commit()
            
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}'
            })
        
        # Check if already processing
        for task_id, task in render_tasks.items():
            if task.get('combo_id') == combo_id and task['status'] == 'processing':
                return jsonify({
                    'status': 'processing',
                    'task_id': task_id,
                    'progress': task.get('progress', 0)
                })
        
        # Get material files
        material_ids = json.loads(render.material_ids)
        material_files = []
        
        for mat_id in material_ids:
            material = Material.query.get(mat_id)
            if material and material.unified_path and os.path.exists(material.unified_path):
                material_files.append(material.unified_path)
        
        if not material_files:
            return jsonify({'error': '素材文件不存在'}), 404
        
        # Start background fast concat (seconds level with -c copy)
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


@app.route('/api/projects/<int:project_id>/previews/status', methods=['GET'])
def get_preview_status(project_id):
    """Get preview generation status for all combinations"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Get all renders from database
        renders = Render.query.filter_by(project_id=project_id).order_by(Render.combo_index).all()
        
        statuses = []
        for render in renders:
            # Check if file exists
            file_exists = render.file_path and os.path.exists(render.file_path)
            
            # Check if processing
            task_status = None
            for task_id, task in render_tasks.items():
                if task.get('combo_id') == render.id:
                    task_status = task
                    break
            
            if task_status and task_status['status'] == 'processing':
                status = 'processing'
            elif file_exists:
                status = 'completed'
            else:
                status = 'pending'
            
            statuses.append({
                'combo_id': render.id,
                'status': status,
                'progress': task_status.get('progress', 0) if task_status else (100 if file_exists else 0),
                'preview_url': f'/renders/{os.path.basename(render.file_path)}' if file_exists else None
            })
        
        return jsonify({
            'total': len(statuses),
            'completed': sum(1 for s in statuses if s['status'] == 'completed'),
            'processing': sum(1 for s in statuses if s['status'] == 'processing'),
            'statuses': statuses
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """Download video - supports both redirect and proxy modes"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        # Check if preview video already exists
        output_filename = f"render_{combo_id}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        if not os.path.exists(output_path):
            return jsonify({
                'status': 'failed',
                'error': '视频文件不存在，请重新生成'
            }), 404
        
        # Check download mode from request
        data = request.json or {}
        download_mode = data.get('mode', 'proxy')  # 'proxy' or 'redirect'
        
        if download_mode == 'redirect':
            # Production mode: return URL for direct download
            # Client will handle the download (suitable for OSS/CDN)
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}',
                'download_url': f'/api/download/file?path={output_filename}&name=mixcut_{combo_id}.mp4',
                'mode': 'redirect'
            })
        else:
            # Development mode: return URL for proxy download (Blob)
            return jsonify({
                'status': 'completed',
                'video_url': f'/renders/{output_filename}',
                'mode': 'proxy'
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/file', methods=['GET'])
def download_file():
    """Direct file download with proper headers (production mode)"""
    try:
        file_path = request.args.get('path')
        download_name = request.args.get('name', 'video.mp4')
        
        if not file_path:
            return jsonify({'error': '没有指定文件路径'}), 400
        
        # Security: ensure path is within renders folder
        full_path = os.path.join(RENDERS_FOLDER, os.path.basename(file_path))
        
        if not os.path.exists(full_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # Send file with download headers
        return send_from_directory(
            RENDERS_FOLDER,
            os.path.basename(file_path),
            as_attachment=True,
            download_name=download_name
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def render_download_task(task_id, combo, quality):
    """Background task to render high quality download video"""
    task = render_tasks[task_id]
    
    try:
        # Quality settings
        quality_settings = {
            'low': {'scale': '720:1280', 'crf': '23', 'preset': 'veryfast'},
            'medium': {'scale': '1080:1920', 'crf': '20', 'preset': 'fast'},
            'high': {'scale': '1440:2560', 'crf': '18', 'preset': 'medium'},
            'ultra': {'scale': '2160:3840', 'crf': '15', 'preset': 'slow'}
        }
        settings = quality_settings.get(quality, quality_settings['medium'])
        
        # Get material files
        material_files = []
        for m in combo:
            if m['unified_path'] and os.path.exists(m['unified_path']):
                material_files.append(m['unified_path'])
            elif m['file_path'] and os.path.exists(m['file_path']):
                material_files.append(m['file_path'])
        
        if not material_files:
            raise Exception('没有找到素材文件')
        
        task['progress'] = 10
        
        # Output path
        output_filename = f"download_{task_id}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        # Build FFmpeg command
        inputs = []
        filter_parts = []
        
        for i, filepath in enumerate(material_files):
            inputs.extend(['-i', filepath])
            ext = filepath.rsplit('.', 1)[1].lower()
            
            if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
                # Images: loop for 3 seconds
                filter_parts.append(f'[{i}:v]loop=loop=90:size=1:start=0,scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
                filter_parts.append(f'[v{i}]anullsrc=channel_layout=stereo:sample_rate=44100[a{i}];')
            else:
                # Videos
                filter_parts.append(f'[{i}:v]scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
                filter_parts.append(f'[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];')
        
        # Concat filter
        concat_v = ''.join([f'[v{i}]' for i in range(len(material_files))])
        concat_a = ''.join([f'[a{i}]' for i in range(len(material_files))])
        filter_complex = ''.join(filter_parts)
        filter_complex += f'{concat_v}concat=n={len(material_files)}:v=1:a=0[outv];'
        filter_complex += f'{concat_a}concat=n={len(material_files)}:v=0:a=1[outa]'
        
        cmd = [
            'ffmpeg', '-y',
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
        
        task['progress'] = 30
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            task['progress'] = 100
            task['status'] = 'completed'
            task['output_path'] = output_path
            task['video_url'] = f'/renders/{output_filename}'
        else:
            raise Exception(f'FFmpeg error: {result.stderr}')
            
    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)


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


# Static file serving
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_FOLDER, filename)


@app.route('/renders/<path:filename>')
def serve_render(filename):
    return send_from_directory(RENDERS_FOLDER, filename)


def cleanup_old_renders(max_age_hours=24):
    """Cleanup render files older than specified hours"""
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
    """Start background thread to cleanup old renders periodically"""
    def cleanup_loop():
        while True:
            time.sleep(3600)  # Run every hour
            cleanup_old_renders(max_age_hours=24)
    
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()


if __name__ == '__main__':
    # Start cleanup scheduler
    start_cleanup_scheduler()
    app.run(host='0.0.0.0', port=3002, debug=True)
