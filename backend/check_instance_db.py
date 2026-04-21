import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'mixcut_refactored.db')
print('Instance DB path:', db_path)
print('DB exists:', os.path.exists(db_path))

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print('Tables:', [t[0] for t in tables])

    if 'kaipai_edits' in [t[0] for t in tables]:
        cursor.execute('PRAGMA table_info(kaipai_edits)')
        columns = cursor.fetchall()
        print('kaipai_edits columns:', [c[1] for c in columns])
    else:
        print('kaipai_edits table NOT found in instance db!')
        # Create the table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS kaipai_edits (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            render_id VARCHAR(100) NOT NULL,
            parent_id VARCHAR(36),
            version INTEGER NOT NULL DEFAULT 1,
            original_video_url VARCHAR(500) NOT NULL,
            output_video_url VARCHAR(500),
            asr_result TEXT,
            edit_params TEXT,
            edit_history TEXT,
            status VARCHAR(20) DEFAULT 'draft',
            title VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
        print('kaipai_edits table created in instance db!')

    conn.close()
else:
    print('Instance DB does not exist!')
