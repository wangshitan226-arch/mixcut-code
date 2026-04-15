# MixCut - 智能视频混剪系统

一个基于 FFmpeg 的智能视频混剪系统，支持上传多镜头素材，自动生成所有排列组合视频。

## 功能特性

- **多镜头管理**: 支持创建多个镜头，每个镜头可上传多个视频/图片素材
- **自动排列组合**: 按照镜头顺序自动生成所有可能的素材组合
- **快速拼接**: 使用 FFmpeg `-c copy` 实现秒级视频拼接（无需重新编码）
- **统一格式**: 上传时自动转码为统一格式，确保拼接兼容性
- **实时预览**: 生成预览视频，支持在线播放
- **清晰度选择**: 支持多种清晰度下载（720P/1080P/2K/4K）

## 技术栈

### 后端
- Python 3.11+
- Flask 3.0.3
- Flask-SQLAlchemy (数据库)
- Flask-CORS (跨域)
- FFmpeg (视频处理)

### 前端
- React 18
- TypeScript
- Vite
- Tailwind CSS

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

### 3. 启动后端

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
python app.py
```

后端服务将在 http://localhost:3002 启动

### 4. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:5173 启动

## 使用流程

1. **创建项目**: 进入首页，点击"新建项目"
2. **添加镜头**: 在编辑页面添加多个镜头（如：镜头1、镜头2、镜头3）
3. **上传素材**: 为每个镜头上传视频或图片素材
4. **开始合成**: 点击"开始合成视频"按钮
5. **查看结果**: 系统自动跳转到结果页，显示所有生成的视频组合
6. **预览/下载**: 点击视频缩略图预览，选择清晰度下载

## 项目结构

```
mixcut/
├── backend/              # 后端代码
│   ├── app.py           # 主应用
│   ├── requirements.txt # Python依赖
│   ├── uploads/         # 上传的素材
│   ├── unified/         # 统一格式转码后的素材
│   ├── renders/         # 生成的视频
│   └── instance/        # 数据库
├── frontend/            # 前端代码
│   ├── src/
│   │   ├── components/  # React组件
│   │   ├── App.tsx      # 主应用
│   │   └── main.tsx     # 入口
│   ├── package.json
│   └── vite.config.ts
└── docs/                # 文档
    └── architecture.md  # 架构设计
```

## 核心实现

### 快速拼接原理

1. **上传时转码**: 所有素材上传后自动转码为统一格式（H.264, 1080P, 30fps）
2. **格式统一**: 确保所有视频编码、分辨率、帧率完全一致
3. **快速拼接**: 使用 `ffmpeg -c copy` 直接复制流，无需重新编码
4. **秒级生成**: 拼接100个视频只需几秒钟

### 排列组合算法

```python
# 笛卡尔积生成所有组合
combinations = list(itertools.product(*shot_materials))
```

## 注意事项

- 确保 FFmpeg 已正确安装并添加到系统 PATH
- 上传的视频会被转码为统一格式，可能需要一些时间
- 生成的视频保存在 `backend/renders/` 目录
- 数据库使用 SQLite，保存在 `backend/instance/mixcut.db`

## License

MIT
