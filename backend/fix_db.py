import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'mixcut_refactored.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kaipai_edits'")
if not cursor.fetchone():
    print("kaipai_edits table does not exist")
    conn.close()
    exit(0)

# 获取现有列
cursor.execute('PRAGMA table_info(kaipai_edits)')
columns = [c[1] for c in cursor.fetchall()]
print(f'Existing columns: {columns}')

# 添加缺少的列
required_columns = {
    'user_id': 'TEXT',
    'asr_result': 'TEXT',
    'edit_history': 'TEXT',
    'title': 'TEXT'
}

for col, type_ in required_columns.items():
    if col not in columns:
        try:
            cursor.execute(f'ALTER TABLE kaipai_edits ADD COLUMN {col} {type_}')
            print(f'Added column: {col}')
        except Exception as e:
            print(f'Error adding {col}: {e}')
    else:
        print(f'Column already exists: {col}')

conn.commit()
conn.close()
print('Done!')
