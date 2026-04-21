"""
数据库迁移脚本 - 添加缺失的列
"""
import sqlite3
import os

# 找到数据库文件 - 检查多个可能的位置
db_paths = [
    'instance/mixcut_refactored.db',
    'mixcut_refactored.db',
    'instance/mixcut.db',
    'mixcut.db',
    'app.db'
]

db_path = None
for path in db_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    print('找不到数据库文件')
    exit(1)

print(f'使用数据库: {db_path}')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 添加缺失的列
try:
    cursor.execute('ALTER TABLE kaipai_edits ADD COLUMN segment_urls TEXT')
    print('添加 segment_urls 列成功')
except Exception as e:
    print(f'segment_urls: {e}')

try:
    cursor.execute("ALTER TABLE kaipai_edits ADD COLUMN segment_status VARCHAR(20) DEFAULT 'pending'")
    print('添加 segment_status 列成功')
except Exception as e:
    print(f'segment_status: {e}')

conn.commit()

# 验证
cursor.execute('PRAGMA table_info(kaipai_edits)')
columns = cursor.fetchall()
print('\n更新后的表结构:')
for col in columns:
    print(f'  {col[1]}: {col[2]}')

conn.close()
print('\n数据库迁移完成！')
