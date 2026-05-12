#!/usr/bin/env python3
"""
检查数据库表结构
"""
import sqlite3
import sys
sys.path.insert(0, 'd:\\project\\mixcut\\backend')

def check_tables():
    try:
        conn = sqlite3.connect('instance/mixcut_refactored.db')
        c = conn.cursor()
        
        # 获取所有表
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        
        print("数据库中的表:")
        for t in tables:
            print(f"  - {t[0]}")
        
        # 检查 kaipai_edits 表
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kaipai_edits'")
        if c.fetchone():
            print("\nkaipai_edits 表存在")
            c.execute('PRAGMA table_info(kaipai_edits)')
            columns = c.fetchall()
            print("列:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
        else:
            print("\nkaipai_edits 表不存在！")
        
        conn.close()
    except Exception as e:
        print(f"错误: {e}")

if __name__ == '__main__':
    check_tables()
