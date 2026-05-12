"""
清理数据库中的模板（保留指定模板）
使用方法: python cleanup_templates.py
"""
import sys

# 要保留的模板名称列表
KEEP_TEMPLATES = ['无模板', '宋体大字模板']

def cleanup_templates():
    """删除数据库中的模板，但保留指定模板"""
    try:
        # 尝试导入 sqlite3
        try:
            import sqlite3
        except ImportError:
            print('❌ 错误: 当前Python环境缺少sqlite3模块')
            print('尝试使用pysqlite3替代...')
            try:
                import pysqlite3 as sqlite3
                print('✅ 使用pysqlite3替代成功')
            except ImportError:
                print('❌ pysqlite3也未安装')
                print('\n解决方案:')
                print('1. 安装pysqlite3: pip install pysqlite3')
                print('2. 或使用完整版Python（非精简版）')
                print('3. 或使用其他SQLite客户端手动清理')
                sys.exit(1)
        
        # 连接数据库
        try:
            conn = sqlite3.connect('instance/mixcut_refactored.db')
            cursor = conn.cursor()
        except Exception as e:
            print(f'❌ 数据库连接失败: {e}')
            print('请确认:')
            print('1. 当前目录是backend目录')
            print('2. instance/mixcut_refactored.db 文件存在')
            sys.exit(1)
        
        # 查看当前模板数量
        cursor.execute('SELECT COUNT(*) FROM templates')
        count = cursor.fetchone()[0]
        print(f'当前数据库中有 {count} 个模板')
        
        if count == 0:
            print('数据库中没有模板，无需清理')
            conn.close()
            return
        
        # 获取所有模板
        cursor.execute('SELECT id, name, category FROM templates ORDER BY sort_order')
        templates = cursor.fetchall()
        
        # 分类模板
        to_delete = []
        to_keep = []
        
        for tid, name, category in templates:
            if name in KEEP_TEMPLATES:
                to_keep.append((tid, name, category))
            else:
                to_delete.append((tid, name, category))
        
        # 显示保留的模板
        if to_keep:
            print(f'\n将保留以下 {len(to_keep)} 个模板:')
            for i, (tid, name, category) in enumerate(to_keep, 1):
                print(f'  {i}. {name} (ID: {tid[:8]}..., 分类: {category})')
        
        # 显示即将删除的模板
        if to_delete:
            print(f'\n即将删除以下 {len(to_delete)} 个模板:')
            for i, (tid, name, category) in enumerate(to_delete, 1):
                print(f'  {i}. {name} (ID: {tid[:8]}..., 分类: {category})')
        else:
            print('\n没有需要删除的模板')
            conn.close()
            return
        
        # 确认删除
        confirm = input('\n确认删除上述模板? (输入 yes 确认): ').strip().lower()
        
        if confirm == 'yes':
            # 删除不在保留列表中的模板
            for tid, name, category in to_delete:
                cursor.execute('DELETE FROM templates WHERE id = ?', (tid,))
                print(f'  已删除: {name}')
            
            conn.commit()
            
            # 验证删除结果
            cursor.execute('SELECT COUNT(*) FROM templates')
            remaining = cursor.fetchone()[0]
            
            print(f'\n✅ 清理完成！')
            print(f'已删除 {len(to_delete)} 个模板')
            print(f'保留 {len(to_keep)} 个模板')
            print(f'剩余模板数量: {remaining}')
        else:
            print('\n❌ 操作已取消')
        
        conn.close()
        
    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    cleanup_targets = ', '.join([f"'{name}'" for name in KEEP_TEMPLATES])
    print(f'保留模板: {cleanup_targets}')
    print(f'Python版本: {sys.version}')
    print('-' * 50)
    cleanup_templates()
