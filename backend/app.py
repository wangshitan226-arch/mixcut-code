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


# Create tables
with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_quality_settings(quality):
    """Get transcoding settings based on quality"""
    settings = {
        'low': {'scale': '720:1280', 'crf': '23', 'preset': 'fast'},
        'medium': {'scale': '1080:1920', 'crf': '20', 'preset': 'medium'},
        'high': {'scale': '1440:2560', 'crf': '18', 'preset': 'medium'},
        'ultra': {'scale': '2160:3840', 'crf': '15', 'preset': 'slow'}
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


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and transcode to unified format"""
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
        
        # Generate thumbnail
        thumbnail_filename = f"{material_id}_thumb.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_filename)
        
        is_video = ext in {'mp4', 'mov', 'avi', 'webm'}
        
        if is_video:
            generate_video_thumbnail(filepath, thumbnail_path)
            duration = format_duration(get_video_duration(filepath))
        else:
            generate_image_thumbnail(filepath, thumbnail_path)
            duration = '0:03'
        
        # Transcode to unified format
        unified_filename = f"{material_id}_unified.mp4"
        unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
        
        transcode_success = transcode_to_unified(filepath, unified_path, quality)
        
        if not transcode_success:
            print(f"Transcode failed for {material_id}")
        else:
            print(f"Transcode success for {material_id}: {unified_path}")
        
        # Save to database
        material = Material(
            id=material_id,
            shot_id=shot_id,
            type='video' if is_video else 'image',
            original_name=file.filename,
            file_path=filepath,
            unified_path=unified_path if transcode_success else None,
            thumbnail_path=thumbnail_path,
            duration=duration
        )
        db.session.add(material)
        db.session.commit()
        
        return jsonify({
            'id': material_id,
            'type': 'video' if is_video else 'image',
            'url': f'/uploads/{filename}',
            'thumbnail': f'/uploads/thumbnails/{thumbnail_filename}',
            'duration': duration,
            'originalName': file.filename
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/materials/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete a material"""
    try:
        material = Material.query.get_or_404(material_id)
        
        # Delete files
        for path in [material.file_path, material.unified_path, material.thumbnail_path]:
            if path and os.path.exists(path):
                os.remove(path)
        
        db.session.delete(material)
        db.session.commit()
        
        return jsonify({'message': '素材已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<int:project_id>/generate', methods=['POST'])
def generate_combinations(project_id):
    """Generate combinations and fast render using concat -c copy"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Get shots with materials that have unified files
        shots = sorted([s for s in project.shots if s.materials], key=lambda x: x.sequence)
        
        if not shots:
            return jsonify({'error': '没有镜头包含素材'}), 400
        
        # Check if all materials have unified files
        for shot in shots:
            for mat in shot.materials:
                if not mat.unified_path or not os.path.exists(mat.unified_path):
                    # Transcode now if missing
                    if mat.file_path and os.path.exists(mat.file_path):
                        unified_filename = f"{mat.id}_unified.mp4"
                        unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
                        if transcode_to_unified(mat.file_path, unified_path, project.quality):
                            mat.unified_path = unified_path
                            db.session.commit()
        
        # Generate combinations
        material_lists = []
        for shot in shots:
            mat_dicts = [{
                'id': mat.id,
                'type': mat.type,
                'unified_path': mat.unified_path,
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name
            } for mat in shot.materials if mat.unified_path]
            material_lists.append(mat_dicts)
        
        all_combos = list(product(*material_lists))
        total_possible = len(all_combos)
        limit = min(total_possible, 100)
        
        combinations = []
        for combo_index, combo in enumerate(all_combos[:limit]):
            combo_id = f"combo_{project_id}_{combo_index}"
            
            # Fast render using concat -c copy (synchronous for instant completion)
            unified_files = [m['unified_path'] for m in combo]
            output_filename = f"render_{combo_id}.mp4"
            output_path = os.path.join(RENDERS_FOLDER, output_filename)
            
            # Check if already rendered
            output_exists = os.path.exists(output_path)
            
            if not output_exists:
                # Render synchronously - should be instant with -c copy
                fast_concat_videos(unified_files, output_path)
                output_exists = os.path.exists(output_path)
            
            total_duration = sum([
                3 if m['type'] == 'image' else 
                get_video_duration(m['unified_path']) 
                for m in combo
            ])
            
            combo_data = {
                'id': combo_id,
                'index': combo_index,
                'materials': list(combo),
                'thumbnail': combo[0]['thumbnail'] if combo else '',
                'duration': format_duration(total_duration),
                'duration_seconds': total_duration,
                'tag': calculate_uniqueness_tag(combo),
                'preview_status': 'completed' if output_exists else 'failed',
                'preview_url': f'/renders/{output_filename}' if output_exists else None
            }
            combinations.append(combo_data)
        
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


@app.route('/api/projects/<int:project_id>/previews/status', methods=['GET'])
def get_preview_status(project_id):
    """Get preview generation status for all combinations"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Get all combinations and check if rendered
        shots = sorted([s for s in project.shots if s.materials], key=lambda x: x.sequence)
        material_lists = []
        for shot in shots:
            mat_dicts = [{
                'id': mat.id,
                'unified_path': mat.unified_path
            } for mat in shot.materials if mat.unified_path]
            material_lists.append(mat_dicts)
        
        all_combos = list(product(*material_lists))
        limit = min(len(all_combos), 100)
        
        statuses = []
        for combo_index in range(limit):
            combo_id = f"combo_{project_id}_{combo_index}"
            output_filename = f"render_{combo_id}.mp4"
            output_path = os.path.join(RENDERS_FOLDER, output_filename)
            output_exists = os.path.exists(output_path)
            
            statuses.append({
                'combo_id': combo_id,
                'status': 'completed' if output_exists else 'processing',
                'preview_url': f'/renders/{output_filename}' if output_exists else None
            })
        
        return jsonify({
            'total': len(statuses),
            'completed': sum(1 for s in statuses if s['status'] == 'completed'),
            'statuses': statuses
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """Download already rendered video"""
    try:
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        output_filename = f"render_{combo_id}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        # Wait for file to exist (check a few times)
        for _ in range(30):  # Wait up to 30 seconds
            if os.path.exists(output_path):
                return jsonify({
                    'status': 'completed',
                    'video_url': f'/renders/{output_filename}'
                })
            import time
            time.sleep(1)
        
        return jsonify({'status': 'processing'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002, debug=True)
