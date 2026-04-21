# MixCut - 智能视频混剪系统

一个基于 FFmpeg 的智能视频混剪系统，支持上传多镜头素材，自动生成所有排列组合视频，并提供文字快剪功能。

## 功能特性

### 核心功能
- **多镜头管理**: 支持创建多个镜头，每个镜头可上传多个视频/图片素材
- **自动排列组合**: 按照镜头顺序自动生成所有可能的素材组合
- **快速拼接**: 使用 FFmpeg `-c copy` 实现秒级视频拼接（无需重新编码）
- **统一格式**: 上传时自动转码为统一格式，确保拼接兼容性
- **实时预览**: 生成预览视频，支持在线播放
- **清晰度选择**: 支持多种清晰度下载（720P/1080P/2K/4K）

### 文字快剪功能（新增）
- **语音识别**: 自动识别视频语音并生成字幕
- **片段选择**: 支持选择删除静音片段、语气词片段
- **字幕编辑**: 长按字幕片段可编辑文字内容
- **实时预览**: 删除片段后实时预览效果（时间戳跳转）
- **一键导出**: 导出最终剪辑视频

## 技术栈

### 后端
- Python 3.11+
- Flask 3.0.3
- Flask-SQLAlchemy (数据库)
- Flask-CORS (跨域)
- FFmpeg (视频处理)
- 阿里云 OSS (可选，用于云存储)

### 前端
- React 18
- TypeScript
- Vite
- Tailwind CSS
- Framer Motion (动画)

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/wangshitan226-arch/mixcut.git
cd mixcut
```

### 2. 安装 FFmpeg

确保系统已安装 FFmpeg 并添加到环境变量：

```bash
# Windows
ffmpeg -version

# macOS
brew install ffmpeg

# Ubuntu
sudo apt update
sudo apt install ffmpeg
```

### 3. 配置阿里云 OSS（可选）

如需使用 OSS 存储，在 `backend/config.py` 中配置：

```python
OSS_CONFIG = {
    'access_key_id': 'your-access-key',
    'access_key_secret': 'your-secret',
    'bucket_name': 'your-bucket',
    'endpoint': 'oss-cn-beijing.aliyuncs.com',
    'enabled': True
}
```

### 4. 启动后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python run.py
```

后端服务将在 http://localhost:3002 启动

### 5. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:3000 启动

## 使用流程

### 基础混剪流程
1. **创建项目**: 进入首页，点击"新建项目"
2. **添加镜头**: 在编辑页面添加多个镜头（如：镜头1、镜头2、镜头3）
3. **上传素材**: 为每个镜头上传视频或图片素材
4. **等待转码**: 素材上传后自动转码（前端会显示进度）
5. **开始合成**: 点击"开始合成视频"按钮
6. **查看结果**: 系统自动跳转到结果页，显示所有生成的视频组合
7. **预览/下载**: 点击视频缩略图预览，选择清晰度下载

### 文字快剪流程
1. **选择视频**: 在结果页选择一个已合成的视频
2. **进入快剪**: 点击"文字快剪"按钮
3. **等待识别**: 系统自动进行语音识别（约30-60秒）
4. **编辑字幕**:
   - **短按/点击**: 跳转到对应时间点播放
   - **长按（500ms）**: 弹出编辑框修改字幕文字
   - **选择删除**: 勾选片段后点击"删除"按钮删除
   - **智能选择**: 可一键选择所有静音片段或含语气词片段
5. **实时预览**: 删除片段后，播放时会自动跳过被删除的部分
6. **导出视频**: 点击"导出视频"按钮生成最终剪辑

## 项目结构

```
mixcut/
├── backend/                    # 后端代码
│   ├── app_new.py             # 主应用入口（当前使用）
│   ├── config.py              # 配置文件
│   ├── models.py              # 数据库模型
│   ├── extensions.py          # Flask扩展初始化
│   ├── websocket.py           # WebSocket处理
│   ├── utils/                 # 工具函数包
│   │   ├── __init__.py
│   │   ├── video.py           # 视频处理（转码、合成）
│   │   ├── oss.py             # 阿里云OSS操作
│   │   └── kaipai_asr.py      # 语音识别（开拍ASR）
│   ├── routes/                # 路由蓝图
│   │   ├── __init__.py
│   │   ├── projects.py        # 项目管理
│   │   ├── shots.py           # 镜头管理
│   │   ├── materials.py       # 素材管理
│   │   ├── upload.py          # 文件上传
│   │   ├── renders.py         # 视频合成
│   │   ├── kaipai.py          # 文字快剪API
│   │   └── download.py        # 视频下载
│   ├── requirements.txt       # Python依赖
│   ├── uploads/               # 上传的原始素材
│   ├── unified/               # 统一格式转码后的素材（10-bit）
│   ├── renders/               # 生成的视频
│   └── instance/              # 数据库
├── frontend/                   # 前端代码
│   ├── src/
│   │   ├── components/        # React组件
│   │   │   ├── KaipaiEditor/  # 文字快剪组件
│   │   │   │   ├── index.tsx
│   │   │   │   ├── SegmentItem.tsx
│   │   │   │   ├── EditModal.tsx
│   │   │   │   ├── VideoPlayer.tsx
│   │   │   │   └── types.ts
│   │   │   ├── HomeScreen.tsx
│   │   │   ├── EditScreen.tsx
│   │   │   ├── ResultsScreen.tsx
│   │   │   └── ProfileScreen.tsx
│   │   ├── App.tsx            # 主应用
│   │   └── main.tsx           # 入口
│   ├── package.json
│   └── vite.config.ts
└── docs/                       # 文档
    └── architecture.md        # 架构设计
```

## 核心实现

### 视频转码统一格式

所有素材上传后自动转码为统一格式：
- **视频编码**: H.264 (libx264)
- **像素格式**: yuv420p10le (10-bit，保护高色深素材)
- **分辨率**: 1080x1920 (9:16 竖屏)
- **帧率**: 30fps
- **音频编码**: AAC, 128kbps, 44100Hz

### 快速拼接原理

1. **格式统一**: 所有素材转码为完全相同的编码参数
2. **快速拼接**: 使用 `ffmpeg -c copy` 直接复制流，无需重新编码
3. **秒级生成**: 拼接100个视频只需几秒钟

### 文字快剪实现

1. **语音识别**: 使用阿里云 Paraformer 语音识别服务
2. **时间戳控制**: 不分割视频，通过时间戳跳转实现"删除"效果
3. **实时预览**: 播放时自动跳过被删除片段的时间范围
4. **字幕编辑**: 支持修改字幕文字并保存到数据库

### 排列组合算法

```python
# 笛卡尔积生成所有组合
combinations = list(itertools.product(*shot_materials))
```

## 注意事项

- 确保 FFmpeg 已正确安装并添加到系统 PATH
- 上传的视频会被转码为统一格式，需要等待转码完成才能合成
- 文字快剪功能需要配置阿里云 ASR 服务（AccessKey ID/Secret）
- 生成的视频保存在 `backend/renders/` 目录
- 数据库使用 SQLite，保存在 `backend/instance/mixcut_refactored.db`

## 最近更新

### 2026-04-21
- ✅ 新增文字快剪功能（开拍式编辑）
- ✅ 支持语音识别和字幕编辑
- ✅ 优化视频转码为 10-bit 格式（yuv420p10le）
- ✅ 修复多素材合成时的格式兼容性问题
- ✅ 重构前端组件结构，模块化 KaipaiEditor

## License

MIT
