from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import uuid
import subprocess
import tempfile
import threading
from itertools import product
from PIL import Image
import cv2

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mixcut.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
RENDERS_FOLDER = os.path.join(os.getcwd(), 'renders')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(RENDERS_FOLDER, exist_ok=True)

# In-memory storage for combinations and render tasks
combinations_store = {}
render_tasks = {}


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
    type = db.Column(db.String(20), nullable=False)  # video, image
    original_name = db.Column(db.String(255))
    file_path = db.Column(db.String(500), nullable=False)
    thumbnail_path = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=db.func.now())


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
        frame = cv2.resize(frame, (300, 400))
        cv2.imwrite(thumbnail_path, frame)
    cap.release()
    return success


def get_video_duration(video_path):
    """Get video duration in seconds"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return duration


def format_duration(seconds):
    """Format duration to MM:SS"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def calculate_total_duration(material_paths):
    """Calculate total duration of materials"""
    total = 0
    for path in material_paths:
        ext = path.rsplit('.', 1)[1].lower()
        if ext in {'mp4', 'mov', 'avi', 'webm'}:
            total += get_video_duration(path)
        else:
            total += 3  # Images default to 3 seconds
    return total


# Project APIs
@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        data = request.json
        name = data.get('name', '未命名项目')
        
        project = Project(name=name)
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
    """Get project with shots and materials"""
    try:
        project = Project.query.get_or_404(project_id)
        
        shots_data = []
        for shot in sorted(project.shots, key=lambda x: x.sequence):
            materials_data = []
            for mat in shot.materials:
                materials_data.append({
                    'id': mat.id,
                    'type': mat.type,
                    'url': f'/uploads/{os.path.basename(mat.file_path)}',
                    'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                    'duration': mat.duration,
                    'name': mat.original_name
                })
            
            shots_data.append({
                'id': shot.id,
                'name': shot.name,
                'sequence': shot.sequence,
                'materials': materials_data
            })
        
        return jsonify({
            'id': project.id,
            'name': project.name,
            'shots': shots_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Shot APIs
@app.route('/api/projects/<int:project_id>/shots', methods=['POST'])
def create_shot(project_id):
    """Create a new shot in project"""
    try:
        project = Project.query.get_or_404(project_id)
        data = request.json
        
        # Get next sequence
        max_sequence = db.session.query(db.func.max(Shot.sequence)).filter_by(project_id=project_id).scalar() or 0
        
        shot = Shot(
            project_id=project_id,
            name=data.get('name', f'镜头{max_sequence + 1}'),
            sequence=max_sequence + 1
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
        return jsonify({'error': str(e)}), 500


@app.route('/api/shots/<int:shot_id>', methods=['DELETE'])
def delete_shot(shot_id):
    """Delete a shot and its materials"""
    try:
        shot = Shot.query.get_or_404(shot_id)
        
        # Delete material files
        for mat in shot.materials:
            if os.path.exists(mat.file_path):
                os.remove(mat.file_path)
            if os.path.exists(mat.thumbnail_path):
                os.remove(mat.thumbnail_path)
        
        db.session.delete(shot)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Material Upload API
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
        
        db.session.delete(material)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Combination Generation API
@app.route('/api/projects/<int:project_id>/combinations/generate', methods=['POST'])
def generate_combinations(project_id):
    """
    Generate combinations from project's shots materials.
    Generate all combinations info, render on-demand when user clicks.
    Clears previous renders when regenerating.
    """
    try:
        project = Project.query.get_or_404(project_id)
        data = request.json or {}
        
        # Clear previous renders for this project
        clear_project_renders(project_id)
        
        # Get all shots with materials
        shots = sorted(project.shots, key=lambda x: x.sequence)
        shots_with_materials = [s for s in shots if s.materials]
        
        if not shots_with_materials:
            return jsonify({'error': '没有镜头包含素材'}), 400
        
        # Extract material lists
        material_lists = []
        for shot in shots_with_materials:
            mat_dicts = [{
                'id': mat.id,
                'type': mat.type,
                'url': f'/uploads/{os.path.basename(mat.file_path)}',
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name
            } for mat in shot.materials]
            material_lists.append(mat_dicts)
        
        # Generate all combinations
        all_combos = list(product(*material_lists))
        total_possible = len(all_combos)
        limit = min(total_possible, 100)  # Max 100 combinations
        
        # Generate all combination info (no pre-rendering)
        combinations = []
        for combo_index, combo in enumerate(all_combos[:limit]):
            material_paths = [os.path.join(UPLOAD_FOLDER, f"{m['id']}.{m['type'] == 'video' and 'mp4' or 'jpg'}") for m in combo]
            total_duration = calculate_total_duration(material_paths)
            cover_thumbnail = combo[0]['thumbnail'] if combo else ''
            
            combo_data = {
                'id': f"combo_{project_id}_{combo_index}",
                'index': combo_index,
                'materials': list(combo),
                'thumbnail': cover_thumbnail,
                'duration': format_duration(total_duration),
                'duration_seconds': total_duration,
                'tag': calculate_uniqueness_tag(combo),
                'rendered': False  # Will be rendered on-demand
            }
            combinations.append(combo_data)
            combinations_store[combo_data['id']] = combo_data
        
        return jsonify({
            'total': len(combinations),
            'total_possible': total_possible,
            'combinations': combinations
        })
        
    except Exception as e:
        return jsonify({'error': f'生成组合失败: {str(e)}'}), 500


def clear_project_renders(project_id):
    """Clear all rendered videos for a project"""
    try:
        # Delete render files for this project
        for filename in os.listdir(RENDERS_FOLDER):
            if filename.startswith(f'render_task_') and filename.endswith('.mp4'):
                filepath = os.path.join(RENDERS_FOLDER, filename)
                try:
                    os.remove(filepath)
                except:
                    pass
        
        # Clear combinations store for this project
        keys_to_delete = [k for k in combinations_store.keys() if k.startswith(f'combo_{project_id}_')]
        for key in keys_to_delete:
            del combinations_store[key]
            
    except Exception as e:
        print(f"Error clearing renders: {e}")


def calculate_uniqueness_tag(materials):
    """Calculate uniqueness tag based on material types"""
    video_count = sum(1 for m in materials if m['type'] == 'video')
    
    if video_count == len(materials):
        return '完全不重复'
    elif video_count >= len(materials) // 2:
        return '极低重复率'
    else:
        return '普通'


# Video Rendering APIs
@app.route('/api/combinations/<combo_id>/render', methods=['POST'])
def render_combination(combo_id):
    """Render a combination video using FFmpeg"""
    try:
        # Parse combo_id: combo_{project_id}_{combo_index}
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        project_id = int(parts[1])
        combo_index = int(parts[2])
        
        # Get project and materials
        project = Project.query.get_or_404(project_id)
        shots = sorted([s for s in project.shots if s.materials], key=lambda x: x.sequence)
        
        if not shots:
            return jsonify({'error': '没有可用的镜头'}), 400
        
        # Reconstruct combination
        from itertools import product
        material_lists = []
        for shot in shots:
            mat_dicts = [{
                'id': mat.id,
                'type': mat.type,
                'url': f'/uploads/{os.path.basename(mat.file_path)}',
                'thumbnail': f'/uploads/thumbnails/{os.path.basename(mat.thumbnail_path)}',
                'duration': mat.duration,
                'name': mat.original_name
            } for mat in shot.materials]
            material_lists.append(mat_dicts)
        
        # Get specific combination by index
        all_combos = list(product(*material_lists))
        if combo_index >= len(all_combos):
            return jsonify({'error': '组合索引超出范围'}), 404
        
        combo = {
            'id': combo_id,
            'index': combo_index,
            'materials': list(all_combos[combo_index])
        }
        
        quality = request.json.get('quality', 'medium')
        
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        render_tasks[task_id] = {
            'id': task_id,
            'combo_id': combo_id,
            'status': 'pending',
            'progress': 0,
            'output_path': None,
            'quality': quality
        }
        
        thread = threading.Thread(
            target=render_video_task,
            args=(task_id, combo, quality)
        )
        thread.start()
        
        return jsonify({
            'task_id': task_id,
            'status': 'processing'
        })
        
    except Exception as e:
        return jsonify({'error': f'启动渲染失败: {str(e)}'}), 500


def render_video_task(task_id, combo, quality):
    """Background task to render video using FFmpeg"""
    task = render_tasks[task_id]
    task['status'] = 'processing'
    
    try:
        # Ultra high quality settings (9:16 portrait mode)
        quality_settings = {
            'low': {'scale': '720:1280', 'crf': '23', 'preset': 'veryfast'},
            'medium': {'scale': '1080:1920', 'crf': '20', 'preset': 'fast'},
            'high': {'scale': '1440:2560', 'crf': '18', 'preset': 'medium'},
            'ultra': {'scale': '2160:3840', 'crf': '15', 'preset': 'slow'}
        }
        settings = quality_settings.get(quality, quality_settings['medium'])
        
        materials = combo['materials']
        material_files = []
        
        for m in materials:
            # Check if file_path is directly provided (from download API)
            if 'file_path' in m and os.path.exists(m['file_path']):
                material_files.append(m['file_path'])
            else:
                # Find file by material id
                found = False
                for filename in os.listdir(UPLOAD_FOLDER):
                    if filename.startswith(m['id']) and not filename.endswith('_thumb.jpg'):
                        full_path = os.path.join(UPLOAD_FOLDER, filename)
                        material_files.append(full_path)
                        found = True
                        break
                if not found:
                    raise Exception(f'找不到素材文件: {m["id"]}')
        
        if not material_files:
            raise Exception('没有找到素材文件')
        
        task['progress'] = 10
        
        output_filename = f"render_{task_id}.mp4"
        output_path = os.path.join(RENDERS_FOLDER, output_filename)
        
        # Use concat filter for proper re-encoding (avoids codec mismatch issues)
        # This ensures all inputs are decoded and re-encoded with consistent parameters
        inputs = []
        filter_parts = []
        
        for i, filepath in enumerate(material_files):
            inputs.extend(['-i', filepath])
            ext = filepath.rsplit('.', 1)[1].lower()
            
            if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}:
                # For images: loop for 3 seconds at 30fps
                filter_parts.append(f'[{i}:v]loop=loop=90:size=1:start=0,scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
                filter_parts.append(f'[v{i}]anullsrc=channel_layout=stereo:sample_rate=44100[a{i}];')
            else:
                # For videos: scale and format
                filter_parts.append(f'[{i}:v]scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=30[v{i}];')
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
        
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        
        if result.returncode != 0:
            raise Exception(f'FFmpeg error: {result.stderr}')
        
        task['progress'] = 100
        task['status'] = 'completed'
        task['output_path'] = output_path
        task['output_url'] = f'/renders/{output_filename}'
        
    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)
        print(f"Render task {task_id} failed: {e}")


@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Get render task status"""
    if task_id not in render_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = render_tasks[task_id]
    response = {
        'task_id': task_id,
        'status': task['status'],
        'progress': task['progress']
    }
    
    if task['status'] == 'completed':
        response['video_url'] = task.get('output_url')
    elif task['status'] == 'failed':
        response['error'] = task.get('error')
    
    return jsonify(response)


# Download API - Real FFmpeg merge for download
@app.route('/api/combinations/<combo_id>/download', methods=['POST'])
def download_combination(combo_id):
    """Download a combination video using FFmpeg (real merge)"""
    try:
        # Parse combo_id: combo_{project_id}_{combo_index}
        parts = combo_id.split('_')
        if len(parts) < 3 or parts[0] != 'combo':
            return jsonify({'error': '无效的组合ID'}), 400
        
        project_id = int(parts[1])
        combo_index = int(parts[2])
        
        # Get project and materials
        project = Project.query.get_or_404(project_id)
        shots = sorted([s for s in project.shots if s.materials], key=lambda x: x.sequence)
        
        if not shots:
            return jsonify({'error': '没有可用的镜头'}), 400
        
        # Reconstruct combination
        from itertools import product
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
        
        # Get specific combination by index
        all_combos = list(product(*material_lists))
        if combo_index >= len(all_combos):
            return jsonify({'error': '组合索引超出范围'}), 404
        
        combo = {
            'id': combo_id,
            'index': combo_index,
            'materials': list(all_combos[combo_index])
        }
        
        quality = request.json.get('quality', 'medium')
        
        task_id = f"download_{uuid.uuid4().hex[:8]}"
        
        render_tasks[task_id] = {
            'id': task_id,
            'combo_id': combo_id,
            'status': 'pending',
            'progress': 0,
            'output_path': None,
            'quality': quality,
            'type': 'download'
        }
        
        thread = threading.Thread(
            target=render_video_task,
            args=(task_id, combo, quality)
        )
        thread.start()
        
        return jsonify({
            'task_id': task_id,
            'status': 'processing'
        })
        
    except Exception as e:
        return jsonify({'error': f'启动下载失败: {str(e)}'}), 500


# Static file serving
@app.route('/renders/<path:filename>')
def serve_render(filename):
    """Serve rendered video files"""
    return send_from_directory(RENDERS_FOLDER, filename)


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files"""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Serve thumbnail files"""
    return send_from_directory(THUMBNAIL_FOLDER, filename)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002, debug=True)
