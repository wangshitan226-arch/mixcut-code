"""Project routes"""
from flask import Blueprint, request, jsonify
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Project, Shot, Material

projects_bp = Blueprint('projects', __name__, url_prefix='/api')


@projects_bp.route('/projects', methods=['POST'])
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


@projects_bp.route('/projects/<int:project_id>', methods=['GET'])
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
                'name': mat.original_name,
                'transcode_status': 'completed' if mat.unified_path else 'pending',
                'transcode_task_id': None
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


@projects_bp.route('/projects/<int:project_id>/renders', methods=['GET'])
def get_project_renders(project_id):
    """Get all rendered videos for a project"""
    from models import Render
    import json
    
    try:
        project = Project.query.get_or_404(project_id)
        renders = Render.query.filter_by(project_id=project_id).order_by(Render.combo_index).all()
        
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
        
        return jsonify({'combinations': combinations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
