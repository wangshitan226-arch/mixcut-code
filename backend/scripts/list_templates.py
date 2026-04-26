#!/usr/bin/env python3
"""
查看数据库中的模板列表
运行: python scripts/list_templates.py
"""
import sqlite3
import json
import sys
sys.path.insert(0, 'd:\\project\\mixcut\\backend')

def list_templates():
    """列出所有模板"""
    try:
        conn = sqlite3.connect('mixcut_refactored.db')
        c = conn.cursor()
        
        # 检查表是否存在
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templates'")
        if not c.fetchone():
            print("错误: templates 表不存在")
            conn.close()
            return
        
        # 获取所有模板
        c.execute('''
            SELECT id, name, description, category, preview_url, is_active, sort_order, created_at 
            FROM templates 
            ORDER BY sort_order
        ''')
        
        templates = c.fetchall()
        
        if not templates:
            print("数据库中没有模板数据")
            conn.close()
            return
        
        print("=" * 80)
        print(f"模板列表 (共 {len(templates)} 个)")
        print("=" * 80)
        
        for i, row in enumerate(templates, 1):
            template_id, name, desc, category, preview_url, is_active, sort_order, created_at = row
            status = "✓ 启用" if is_active else "✗ 禁用"
            print(f"\n{i}. {name}")
            print(f"   ID: {template_id}")
            print(f"   分类: {category}")
            print(f"   状态: {status}")
            print(f"   排序: {sort_order}")
            print(f"   预览图: {preview_url}")
            print(f"   描述: {desc[:50]}..." if desc and len(desc) > 50 else f"   描述: {desc}")
            print(f"   创建时间: {created_at}")
        
        print("\n" + "=" * 80)
        
        # 统计信息
        c.execute('SELECT COUNT(*) FROM templates WHERE is_active = 1')
        active_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM templates WHERE is_active = 0')
        inactive_count = c.fetchone()[0]
        
        print(f"统计: 启用 {active_count} 个, 禁用 {inactive_count} 个")
        print("=" * 80)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == '__main__':
    list_templates()
