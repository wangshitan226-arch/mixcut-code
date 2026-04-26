#!/usr/bin/env python3
"""
添加缺失的列到 kaipai_edits 表
"""
import sqlite3
import sys
sys.path.insert(0, 'd:\\project\\mixcut\\backend')

def add_missing_columns():
    try:
        conn = sqlite3.connect('instance/mixcut_refactored.db')
        c = conn.cursor()
        
        # 检查现有列
        c.execute('PRAGMA table_info(kaipai_edits)')
        columns = [col[1] for col in c.fetchall()]
        print(f"现有列: {columns}")
        
        # 添加 segment_urls 列
        if 'segment_urls' not in columns:
            c.execute('ALTER TABLE kaipai_edits ADD COLUMN segment_urls TEXT')
            print("已添加 segment_urls 列")
        else:
            print("segment_urls 列已存在")
        
        # 添加 segment_status 列
        if 'segment_status' not in columns:
            c.execute('ALTER TABLE kaipai_edits ADD COLUMN segment_status VARCHAR(20) DEFAULT "pending"')
            print("已添加 segment_status 列")
        else:
            print("segment_status 列已存在")
        
        conn.commit()
        conn.close()
        print("完成！")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    add_missing_columns()
