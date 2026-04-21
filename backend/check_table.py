import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mixcut_refactored.db')
print('DB path:', db_path)
print('DB exists:', os.path.exists(db_path))

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
    print('kaipai_edits table NOT found!')

conn.close()
