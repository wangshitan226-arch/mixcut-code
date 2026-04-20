"""
Material service - Business logic for material management
"""
from models import Material
from extensions import db
from utils import cleanup_renders_with_material


class MaterialService:
    """Material related business logic"""
    
    @staticmethod
    def get_material_by_id(material_id):
        """Get material by ID"""
        return Material.query.get(material_id)
    
    @staticmethod
    def delete_material(material_id):
        """Delete a material and cleanup"""
        import os
        material = Material.query.get(material_id)
        if not material:
            return False
        
        user_id = material.user_id
        
        # Cleanup files
        for path in [material.file_path, material.unified_path, material.thumbnail_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Failed to delete {path}: {e}")
        
        # Cleanup related renders
        cleanup_renders_with_material(user_id, material_id)
        
        db.session.delete(material)
        db.session.commit()
        return True
