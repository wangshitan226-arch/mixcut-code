import sqlite3
import os

# Check both possible database locations
db_paths = [
    'instance/mixcut_fast.db',
    'mixcut_fast.db'
]

for db_path in db_paths:
    if os.path.exists(db_path):
        print(f"\n=== Database: {db_path} ===")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {[t[0] for t in tables]}")
        
        # Check renders table
        if ('renders',) in tables:
            cursor.execute("SELECT COUNT(*) FROM renders;")
            count = cursor.fetchone()[0]
            print(f"Renders count: {count}")
            
            if count > 0:
                cursor.execute("SELECT id, project_id, status FROM renders LIMIT 5;")
                print("Sample renders:")
                for row in cursor.fetchall():
                    print(f"  {row}")
        
        # Check projects table
        if ('projects',) in tables:
            cursor.execute("SELECT COUNT(*) FROM projects;")
            count = cursor.fetchone()[0]
            print(f"Projects count: {count}")
        
        conn.close()
    else:
        print(f"Database not found: {db_path}")
