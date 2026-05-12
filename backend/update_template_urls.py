import sqlite3
import json

conn = sqlite3.connect('instance/mixcut_refactored.db')
c = conn.cursor()

# 获取明快黄模板的当前配置
c.execute("SELECT id, config FROM templates WHERE name = '明快黄'")
row = c.fetchone()
if row:
    template_id, config_json = row
    config = json.loads(config_json)
    
    # 更新配置
    config['preview_url'] = 'https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/img/%E5%BE%AE%E4%BF%A1%E5%9B%BE%E7%89%87_20260422180717_478_2.jpg'
    config['backgroundMusic'] = {
        'url': 'https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/bgm/the_mountain-festive-festive-music-508015.mp3',
        'volume': 0.4
    }
    config['soundEffects'] = [
        {
            'name': 'wow',
            'url': 'https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/dragon-studio-wow-423653.mp3',
            'trigger': 'emphasis'
        },
        {
            'name': 'bell',
            'url': 'https://fengma-materials.oss-cn-beijing.aliyuncs.com/materials/sound-effact/u_7xr5ffk4oq-opening-bell-421471.mp3',
            'trigger': 'title'
        }
    ]
    
    # 更新数据库
    c.execute('UPDATE templates SET preview_url = ?, config = ? WHERE id = ?',
              (config['preview_url'], json.dumps(config), template_id))
    conn.commit()
    print('模板配置已更新')
    print(f'预览图: {config["preview_url"] }')
    print(f'BGM: {config["backgroundMusic"]["url"] }')
    print(f'音效1: {config["soundEffects"][0]["url"] }')
    print(f'音效2: {config["soundEffects"][1]["url"] }')
else:
    print('未找到明快黄模板')

conn.close()
