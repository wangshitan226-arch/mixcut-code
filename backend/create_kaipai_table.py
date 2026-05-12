import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'mixcut_refactored.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 创建 kaipai_edits 表
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
conn.close()
print('kaipai_edits table created successfully!')
