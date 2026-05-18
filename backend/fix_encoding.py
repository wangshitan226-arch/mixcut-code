import re

with open('routes/digital_human.py', 'r', encoding='utf-8') as f:
    content = f.read()

fixes = [
    ("'请输入要合成的文本\"})", "'请输入要合成的文本'}),"),
    ("'已有生成任务进行中\",", "'已有生成任务进行中',"),
    ("'请输入声音名称\"}),", "'请输入声音名称'}),"),
    ("'声音不存在\"}),", "'声音不存在'}),"),
    ("'已重置生成状态\",", "'已重置生成状态',"),
    ("'请指定语音ID\"}", "'请指定语音ID'}"),
    ("'数字人不存在\"}", "'数字人不存在'}"),
    ("'数字人未设置模板视频\"}", "'数字人未设置模板视频'}"),
    ("'未指定声音\"}", "'未指定声音'}"),
    ("'缺少user_id或digital_human_id\"}", "'缺少user_id或digital_human_id'}"),
    ("'请输入文本或提供字幕数据\"}", "'请输入文本或提供字幕数据'}"),
    ("'缺少user_id\"}", "'缺少user_id'}"),
    ("'请输入声音名称\"}", "'请输入声音名称'}"),
    ("'缺少音频URL\"}", "'缺少音频URL'}"),
    ("'语音合成失败\"}", "'语音合成失败'}"),
    ("'数字人未设置声音\"}", "'数字人未设置声音'}"),
]

for old, new in fixes:
    content = content.replace(old, new)

content = re.sub(r"'([^']*)\"}\)", r"'\1'})", content)
content = re.sub(r"'([^']*)\"}\),", r"'\1'}),", content)

with open('routes/digital_human.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')
