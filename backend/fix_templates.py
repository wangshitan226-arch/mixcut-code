import sqlite3
import json
import uuid

conn = sqlite3.connect('instance/mixcut_refactored.db')
c = conn.cursor()

# 删除所有旧模板
c.execute('DELETE FROM templates')
print('已删除旧模板')

# 插入3个新模板
new_templates = [
    ('大字报风格', 'promotion', {'subtitleStyles': {'title': {'font': 'AlibabaPuHuiTi-Heavy', 'font_size': 90, 'font_color': '#FFD700', 'outline': 5, 'outline_color': '#8B4513', 'motion_in': 'rotateup_in', 'motion_out': 'close_out', 'y': 0.35}, 'body': {'font': 'AlibabaPuHuiTi-Regular', 'font_size': 42, 'font_color': '#FFFFFF', 'outline': 2, 'outline_color': '#000000', 'motion_in': 'scroll_right_in', 'motion_out': 'scroll_right_out', 'y': 0.72}}, 'videoEffects': {'enableSmartZoom': True, 'zoomIntensity': 1.2}}),
    ('简洁知识风', 'knowledge', {'subtitleStyles': {'title': {'font': 'AlibabaPuHuiTi-Regular', 'font_size': 50, 'font_color': '#FFFFFF', 'outline': 3, 'outline_color': '#333333', 'motion_in': 'fade_in', 'motion_out': 'fade_out', 'y': 0.52}, 'body': {'font': 'AlibabaPuHuiTi-Regular', 'font_size': 42, 'font_color': '#FFFFFF', 'outline': 2, 'outline_color': '#000000', 'motion_in': 'scroll_right_in', 'motion_out': 'scroll_right_out', 'y': 0.72}}, 'videoEffects': {'enableSmartZoom': False}}),
    ('活力动感风', 'entertainment', {'subtitleStyles': {'title': {'font': 'AlibabaPuHuiTi-Bold', 'font_size': 60, 'font_color': '#FFDD00', 'outline': 4, 'outline_color': '#FF6600', 'motion_in': 'slingshot_in', 'motion_out': 'slingshot_out', 'y': 0.5, 'loop': 2, 'loop_effect': 'bounce'}, 'body': {'font': 'AlibabaPuHuiTi-Regular', 'font_size': 42, 'font_color': '#FFFFFF', 'outline': 2, 'outline_color': '#000000', 'motion_in': 'scroll_right_in', 'motion_out': 'scroll_right_out', 'y': 0.72}}, 'videoEffects': {'enableSmartZoom': True, 'zoomIntensity': 1.25}})
]

for i, (name, category, config) in enumerate(new_templates):
    c.execute('INSERT INTO templates (id, name, description, category, config, is_active, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime("now"), datetime("now"))',
              (str(uuid.uuid4()), name, '', category, json.dumps(config), 1, i))
    print(f'插入: {name}')

conn.commit()

# 验证
c.execute('SELECT name FROM templates')
print('当前模板:', [r[0] for r in c.fetchall()])

conn.close()
