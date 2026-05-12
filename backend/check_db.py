import sqlite3
import os

db_path = 'instance/mixcut_refactored.db'
print(f'数据库文件存在: {os.path.exists(db_path)}')

if os.path.exists(db_path):
    print(f'数据库文件大小: {os.path.getsize(db_path)} bytes')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f'表: {[t[0] for t in tables]}')
    
    if 'renders' in [t[0] for t in tables]:
        cursor.execute('PRAGMA table_info(renders)')
        columns = cursor.fetchall()
        print(f'renders表列: {[c[1] for c in columns]}')
    
    conn.close()
else:
    print('数据库文件不存在')
