"""
User management routes
"""
from flask import Blueprint, jsonify
from models import User

users_bp = Blueprint('users', __name__, url_prefix='/api')


@users_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new anonymous user"""
    try:
        user = User(type='anonymous')
        from extensions import db
        db.session.add(user)
        db.session.commit()
        return jsonify({
            'id': user.id,
            'type': user.type,
            'created_at': user.created_at.isoformat()
        })
    except Exception as e:
        from extensions import db
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@users_bp.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get user details with shots"""
    import os
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
