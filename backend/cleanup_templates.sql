-- 清理模板表，只保留3个模板
-- 先查看当前模板
SELECT id, name, category FROM templates;

-- 删除所有模板（谨慎操作）
DELETE FROM templates;

-- 重新插入3个模板
-- 注意：实际插入请使用 Python 脚本或手动执行 INSERT
