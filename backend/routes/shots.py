"""Shot routes"""
from flask import Blueprint, request, jsonify
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Project, Shot

shots_bp = Blueprint('shots', __name__, url_prefix='/api')


@shots_bp.route('/projects/<int:project_id>/shots', methods=['POST'])
def create_shot(project_id):
    """Create a new shot"""
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    try:
        data = request.json or {}
        max_sequence = max([s.sequence for s in project.shots] + [-1])
        
        shot = Shot(
            project_id=project_id,
            name=data.get('name', f'镜头{max_sequence + 2}'),
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


@shots_bp.route('/shots/<int:shot_id>', methods=['DELETE'])
def delete_shot(shot_id):
    """Delete a shot and all its materials"""
    from models import Material, Render
    import json
    
    try:
        shot = Shot.query.get_or_404(shot_id)
        project_id = shot.project_id
        
        # Delete all material files first
        for material in shot.materials:
            for path in [material.file_path, material.unified_path, material.thumbnail_path]:
                if path and os.path.exists(path):
                    os.remove(path)
            
            # Cleanup renders that contain this material
            for render in Render.query.filter_by(project_id=project_id).all():
                try:
                    material_ids = json.loads(render.material_ids)
                    if material.id in material_ids:
                        if render.file_path and os.path.exists(render.file_path):
                            os.remove(render.file_path)
                        db.session.delete(render)
                except:
                    continue
        
        db.session.delete(shot)
        db.session.commit()
        
        return jsonify({'message': '镜头已删除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
