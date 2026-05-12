"""
删除"明快黄"模板
运行: python delete_mingkuaihuang_template.py
"""
import sqlite3

def delete_template():
    conn = sqlite3.connect('instance/mixcut_refactored.db')
    c = conn.cursor()
    
    # 检查模板是否存在
    c.execute("SELECT id, name FROM templates WHERE name = '明快黄'")
    row = c.fetchone()
    
    if row:
        template_id, name = row
        # 删除模板
        c.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        conn.commit()
        print(f"模板删除成功!")
        print(f"  ID: {template_id}")
        print(f"  名称: {name}")
    else:
        print("未找到'明快黄'模板")
    
    # 显示剩余模板
    print("\n当前所有模板:")
    c.execute('SELECT name FROM templates WHERE is_active = 1 ORDER BY sort_order')
    templates = c.fetchall()
    for i, (name,) in enumerate(templates, 1):
        print(f"  {i}. {name}")
    
    conn.close()

if __name__ == '__main__':
    delete_template()
