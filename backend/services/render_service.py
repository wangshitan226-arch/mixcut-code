"""
Render service - Business logic for render management
"""
from models import Render
from extensions import db


class RenderService:
    """Render related business logic"""
    
    @staticmethod
    def get_renders_by_user(user_id):
        """Get all renders for a user"""
        return Render.query.filter_by(user_id=user_id).order_by(Render.combo_index).all()
    
    @staticmethod
    def clear_user_renders(user_id):
        """Clear all renders for a user"""
        import os
        renders = Render.query.filter_by(user_id=user_id).all()
        for render in renders:
            if render.file_path and os.path.exists(render.file_path):
                try:
                    os.remove(render.file_path)
                except:
                    pass
        
        Render.query.filter_by(user_id=user_id).delete()
        db.session.commit()
    
    @staticmethod
    def create_render(combo_id, user_id, combo_index, material_ids, tag, duration, duration_seconds, thumbnail):
        """Create a new render record"""
        render = Render(
            id=combo_id,
            user_id=user_id,
            combo_index=combo_index,
            material_ids=material_ids,
            tag=tag,
            duration=duration,
            duration_seconds=duration_seconds,
            thumbnail=thumbnail,
            status='pending'
        )
        db.session.add(render)
        return render
