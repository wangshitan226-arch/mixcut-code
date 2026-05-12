"""
添加template_id列到kaipai_edits表
SQLite不支持直接添加外键列，需要使用临时表方式
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = 'instance/mixcut_refactored.db'

def migrate():
    print("添加template_id列到kaipai_edits表...")
    
    # 检查数据库文件路径
    if not os.path.exists(DB_PATH):
        # 尝试其他路径
        alt_path = 'mixcut_refactored.db'
        if os.path.exists(alt_path):
            db_path = alt_path
        else:
            print(f"[X] 找不到数据库文件: {DB_PATH}")
            return
    else:
        db_path = DB_PATH
    
    print(f"数据库路径: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查列是否已存在
        cursor.execute("PRAGMA table_info(kaipai_edits)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'template_id' in columns:
            print("[OK] template_id列已存在")
            conn.close()
            return
        
        print("添加template_id列...")
        
        # SQLite添加列（外键约束会在后面添加）
        cursor.execute("ALTER TABLE kaipai_edits ADD COLUMN template_id VARCHAR(36)")
        
        conn.commit()
        print("[OK] 列添加成功")
        
        # 验证
        cursor.execute("PRAGMA table_info(kaipai_edits)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'template_id' in columns:
            print("[OK] 验证通过")
        
    except Exception as e:
        print(f"[X] 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
