"""
API Routes (Blueprints)
"""
from .auth import auth_bp
from .users import users_bp
from .shots import shots_bp
from .materials import materials_bp
from .upload import upload_bp
from .generate import generate_bp
from .renders import renders_bp
from .static import static_bp
from .kaipai import kaipai_bp

__all__ = [
    'auth_bp', 'users_bp', 'shots_bp', 'materials_bp',
    'upload_bp', 'generate_bp', 'renders_bp', 'static_bp',
    'kaipai_bp'
]
