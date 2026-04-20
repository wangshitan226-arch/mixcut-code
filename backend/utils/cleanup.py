"""
Cleanup utilities for user data
"""
import os
import glob
from config import RENDERS_FOLDER
from extensions import db
from models import Render


def clear_user_render_files(user_id):
    """Clear all render files for a user"""
    deleted_count = 0
    try:
        print(f"[CLEANUP] ====== START clear_user_render_files ======")
        print(f"[CLEANUP] Looking for render files in: {RENDERS_FOLDER}")
        print(f"[CLEANUP] User ID: '{user_id}' (type: {type(user_id)})")
        
        # Check if directory exists
        if not os.path.exists(RENDERS_FOLDER):
            print(f"[CLEANUP] ERROR: RENDERS_FOLDER does not exist: {RENDERS_FOLDER}")
            return 0
        
        # List all files in directory for debugging
        try:
            all_files = os.listdir(RENDERS_FOLDER)
            print(f"[CLEANUP] All files in renders folder ({len(all_files)} files): {all_files}")
        except Exception as e:
            print(f"[CLEANUP] ERROR listing directory: {e}")
            all_files = []
        
        # Delete files matching pattern: render_combo_{user_id}_*.mp4
        pattern = os.path.join(RENDERS_FOLDER, f'render_combo_{user_id}_*.mp4')
        print(f"[CLEANUP] Search pattern: '{pattern}'")
        
        try:
            files = glob.glob(pattern)
            print(f"[CLEANUP] Found {len(files)} files matching pattern: {files}")
        except Exception as e:
            print(f"[CLEANUP] ERROR in glob: {e}")
            files = []
        
        # Also try to manually match files for debugging
        print(f"[CLEANUP] Manual matching check:")
        for filename in all_files:
            expected_prefix = f'render_combo_{user_id}_'
            if filename.startswith(expected_prefix) and filename.endswith('.mp4'):
                print(f"[CLEANUP]   - Manual match: {filename}")
            else:
                print(f"[CLEANUP]   - No match: {filename} (expected prefix: '{expected_prefix}')")
        
        for filepath in files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"[CLEANUP] DELETED: {filepath}")
                else:
                    print(f"[CLEANUP] File already gone: {filepath}")
            except Exception as e:
                print(f"[CLEANUP] FAILED to delete {filepath}: {e}")
        
        print(f"[CLEANUP] Total deleted: {deleted_count} files for user {user_id}")
        print(f"[CLEANUP] ====== END clear_user_render_files ======")
    except Exception as e:
        print(f"[CLEANUP] ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    return deleted_count


def clear_user_renders_db(user_id):
    """Clear all render records from database for a user"""
    try:
        print(f"[CLEANUP] Clearing render records from DB for user: {user_id}")
        
        # Count before delete
        count_before = Render.query.filter_by(user_id=user_id).count()
        print(f"[CLEANUP] Found {count_before} render records in DB")
        
        # Delete render records
        result = Render.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        
        print(f"[CLEANUP] Deleted {result} render records from DB for user {user_id}")
    except Exception as e:
        print(f"[CLEANUP] ERROR clearing DB records: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()


def clear_all_user_renders(user_id):
    """Clear all renders (files + database) for a user - call this when materials change"""
    print(f"\n{'='*60}")
    print(f"[CLEANUP] START: Clearing all renders for user {user_id}")
    print(f"{'='*60}")
    
    # Clear files first
    file_count = clear_user_render_files(user_id)
    
    # Then clear DB
    clear_user_renders_db(user_id)
    
    print(f"[CLEANUP] COMPLETE: Deleted {file_count} files for user {user_id}")
    print(f"{'='*60}\n")
