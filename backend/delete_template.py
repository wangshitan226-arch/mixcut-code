"""
删除模板脚本
通过模板名称删除数据库中的模板

使用方法: python delete_template.py
"""
import sqlite3
import sys
import os

# 确保在 backend 目录下运行
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ==================== 修改这里 ====================
# 输入要删除的模板名称
TEMPLATE_NAME = "粉白蓝"  # 修改为您要删除的模板名称
# =================================================


def delete_template():
    """通过名称删除模板"""
    db_path = 'instance/mixcut_refactored.db'
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 先查询模板是否存在
    c.execute('SELECT id, name, description FROM templates WHERE name = ?', (TEMPLATE_NAME,))
    template = c.fetchone()
    
    if not template:
        print(f"模板 '{TEMPLATE_NAME}' 不存在")
        
        # 显示所有模板供参考
        print("\n当前所有模板:")
        c.execute('SELECT name, category FROM templates ORDER BY sort_order')
        templates = c.fetchall()
        for i, (name, category) in enumerate(templates, 1):
            print(f"  {i}. {name} ({category})")
        
        conn.close()
        return
    
    # 显示要删除的模板信息
    print(f"找到模板:")
    print(f"  ID: {template[0]}")
    print(f"  名称: {template[1]}")
    print(f"  描述: {template[2]}")
    
    # 删除模板
    c.execute('DELETE FROM templates WHERE name = ?', (TEMPLATE_NAME,))
    deleted_count = c.rowcount
    
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        print(f"\n✓ 成功删除模板 '{TEMPLATE_NAME}'")
    else:
        print(f"\n✗ 删除失败")


if __name__ == '__main__':
    delete_template()
