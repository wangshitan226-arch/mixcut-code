import sqlite3
import os

db_path = 'instance/mixcut_fast.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check project 6 (from the logs)
project_id = 6

print(f"=== Project {project_id} ===")

# Get shots
cursor.execute("SELECT id, name FROM shots WHERE project_id = ?", (project_id,))
shots = cursor.fetchall()
print(f"Shots: {len(shots)}")

for shot_id, shot_name in shots:
    print(f"\n  Shot: {shot_name} (ID: {shot_id})")
    
    # Get materials
    cursor.execute("SELECT id, type, unified_path, file_path FROM materials WHERE shot_id = ?", (shot_id,))
    materials = cursor.fetchall()
    print(f"  Materials: {len(materials)}")
    
    for mat_id, mat_type, unified_path, file_path in materials:
        unified_exists = os.path.exists(unified_path) if unified_path else False
        file_exists = os.path.exists(file_path) if file_path else False
        print(f"    - {mat_id}: type={mat_type}")
        print(f"      unified_path: {unified_path}")
        print(f"      unified_exists: {unified_exists}")
        print(f"      file_exists: {file_exists}")

conn.close()
