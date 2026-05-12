"""
Shot service - Business logic for shot management
"""
from models import Shot
from extensions import db


class ShotService:
    """Shot related business logic"""
    
    @staticmethod
    def create_shot(user_id, name):
        """Create a new shot for user"""
        from models import User
        user = User.query.get(user_id)
        if not user:
            return None
        
        shot_count = len(user.shots)
        shot = Shot(
            user_id=user_id,
            name=name or f'镜头{shot_count + 1}',
            sequence=shot_count
        )
        db.session.add(shot)
        db.session.commit()
        return shot
    
    @staticmethod
    def get_shots_by_user(user_id):
        """Get all shots for a user"""
        return Shot.query.filter_by(user_id=user_id).order_by(Shot.sequence).all()
    
    @staticmethod
    def delete_shot(shot_id):
        """Delete a shot"""
        import os
        shot = Shot.query.get(shot_id)
        if not shot:
            return False
        
        # Cleanup material files
        for material in shot.materials:
            for path in [material.file_path, material.unified_path, material.thumbnail_path]:
                if path and os.path.exists(path):
                    os.remove(path)
        
        db.session.delete(shot)
        db.session.commit()
        return True
