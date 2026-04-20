"""File handling utilities"""
import os
from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER, THUMBNAIL_FOLDER, UNIFIED_FOLDER, RENDERS_FOLDER

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_folders():
    """Ensure all required folders exist"""
    for folder in [UPLOAD_FOLDER, THUMBNAIL_FOLDER, UNIFIED_FOLDER, RENDERS_FOLDER]:
        os.makedirs(folder, exist_ok=True)

def clear_project_renders(project_id):
    """Clear all renders for a project"""
    from models import Render, db
    try:
        prefix = f"combo_{project_id}_"
        for filename in os.listdir(RENDERS_FOLDER):
            if filename.startswith(prefix) or filename.startswith(f"render_{prefix}"):
                filepath = os.path.join(RENDERS_FOLDER, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                except Exception as e:
                    print(f"Failed to delete {filename}: {e}")
        
        Render.query.filter_by(project_id=project_id).delete()
        db.session.commit()
    except Exception as e:
        print(f"Error clearing renders: {e}")

def cleanup_old_renders(max_age_hours=24):
    """Cleanup render files older than specified hours"""
    import time
    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filename in os.listdir(RENDERS_FOLDER):
            filepath = os.path.join(RENDERS_FOLDER, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                    except:
                        pass
    except Exception as e:
        print(f"Cleanup error: {e}")
