# MixCut + 开拍式网感剪辑集成方案（修正版）

## 一、项目现状分析

### 1.1 现有架构（基于 app_new.py）

```
MixCut 项目结构
├── frontend/           # React + TypeScript 前端
│   └── src/
│       ├── components/
│       │   ├── HomeScreen.tsx      # 首页/素材上传
│       │   ├── EditScreen.tsx      # 分镜编辑
│       │   ├── ResultsScreen.tsx   # 混剪结果列表 ← 集成入口
│       │   └── ProfileScreen.tsx
│       └── App.tsx
├── backend/            # Flask 后端（模块化架构）
│   ├── app_new.py      # 主入口（当前使用）
│   ├── config.py       # 配置管理
│   ├── extensions.py   # Flask扩展(db, socketio等)
│   ├── models.py       # 数据模型
│   ├── routes/         # API路由(Blueprint)
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── shots.py
│   │   ├── materials.py
│   │   ├── upload.py
│   │   ├── generate.py
│   │   ├── renders.py              # 混剪结果API ← 需要扩展
│   │   └── static.py
│   ├── services/       # 业务逻辑层
│   │   ├── user_service.py
│   │   ├── shot_service.py
│   │   ├── material_service.py
│   │   └── render_service.py
│   └── utils/          # 工具函数
├── editor_v3.html      # 开拍式编辑器前端(独立HTML)
└── run_v3.py           # 开拍式编辑器后端(独立Flask)
```

### 1.2 当前V3实现功能

**前端(editor_v3.html)**
- 视频上传 → OSS URL输入 → 语音识别启动
- 文字快剪界面：字级分割、静音检测、语气词标记
- 视频预览 + 字幕同步显示
- 片段选择/删除/编辑功能

**后端(run_v3.py)**
- 本地视频上传存储
- 阿里云 DashScope FunASR 语音识别
- 字级时间戳分割(>100ms分割, >300ms标记静音)
- 语气词检测(嗯、啊、哦等)
- 任务状态轮询API

### 1.3 需要集成的功能

根据 `kaipai-integration-plan.md`，需要实现四大模块：

| 模块 | 当前状态 | 优先级 |
|------|----------|--------|
| 文字快剪 | ✅ 已实现 | P0 |
| 网感模板 | ❌ 未实现 | P1 |
| 字幕样式 | ⚠️ 基础字幕 | P1 |
| BGM替换 | ❌ 未实现 | P2 |

---

## 二、集成方案选型

### 2.1 方案对比

| 方案 | 描述 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| **A. 独立服务** | 保持V3独立运行，通过API通信 | 解耦、易维护 | 需要跨服务通信 | ⭐⭐⭐⭐⭐ |
| **B. 合并后端** | 将run_v3.py合并到backend/ | 统一服务 | 耦合度高、工作量大 | ⭐⭐⭐ |
| **C. 前端集成** | 将editor_v3.html转为React组件 | 用户体验一致 | 需要重构前端 | ⭐⭐⭐⭐ |

### 2.2 推荐方案：A + C 混合方案

**核心思路**：
1. **后端**：保持 `run_v3.py` 作为独立微服务（语音识别专用），通过主后端 `backend/` 做数据中转和持久化
2. **前端**：将 `editor_v3.html` 重构为 React 组件，集成到现有前端
3. **数据流**：主后端负责版本管理和渲染任务调度

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Main Backend   │────▶│   Kaipai        │
│   (React)       │◄────│   (app_new.py)   │◄────│   Service       │
│                 │     │                  │     │   (run_v3.py)   │
│ ResultsScreen   │     │ - 版本管理       │     │ - 语音识别      │
│ KaipaiEditor    │     │ - 渲染任务       │     │ - 片段处理      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │   Database       │
                        │   (SQLite/PG)    │
                        └──────────────────┘
```

---

## 三、详细实现方案（适配 app_new.py 架构）

### 3.1 数据库模型扩展

在 `backend/models.py` 新增模型：

```python
class KaipaiEdit(db.Model):
    """开拍式剪辑版本记录"""
    __tablename__ = 'kaipai_edits'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    render_id = db.Column(db.String(100), db.ForeignKey('renders.id'), nullable=False)
    parent_id = db.Column(db.String(36), db.ForeignKey('kaipai_edits.id'), nullable=True)
    version = db.Column(db.Integer, default=1)
    
    # 编辑参数(JSON存储)
    edit_params = db.Column(db.JSON, default={})
    # 包含：removed_segments, subtitle_style, bgm, template
    
    # 文件路径
    original_video_url = db.Column(db.String(500))  # 原视频URL
    output_video_url = db.Column(db.String(500))    # 输出视频URL
    output_file_path = db.Column(db.String(500))    # 本地文件路径
    
    # 状态
    status = db.Column(db.String(20), default='draft')  # draft/processing/completed/failed
    
    # 元数据
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    # 关系
    render = db.relationship('Render', backref='kaipai_edits')
    
    def to_dict(self):
        return {
            'id': self.id,
            'render_id': self.render_id,
            'version': self.version,
            'status': self.status,
            'output_url': self.output_video_url,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

### 3.2 后端路由扩展

#### 3.2.1 创建新的 Blueprint (backend/routes/kaipai.py)

```python
"""
Kaipai (开拍式) editing routes
"""
from flask import Blueprint, request, jsonify
import uuid
import requests
from models import Render, KaipaiEdit
from extensions import db
from config import RENDERS_FOLDER

kaipai_bp = Blueprint('kaipai', __name__, url_prefix='/api')

# Kaipai 服务配置
KAIPAI_SERVICE_URL = 'http://localhost:5000'  # run_v3.py 服务地址

@kaipai_bp.route('/renders/<render_id>/kaipai/edit', methods=['POST'])
def create_kaipai_edit(render_id):
    """创建新的开拍式剪辑任务"""
    render = Render.query.get(render_id)
    if not render:
        return jsonify({'error': 'Render not found'}), 404
    
    data = request.json or {}
    parent_id = data.get('parent_id')
    
    # 计算版本号
    if parent_id:
        parent = KaipaiEdit.query.get(parent_id)
        version = parent.version + 1 if parent else 1
    else:
        # 查询该render已有多少个版本
        existing = KaipaiEdit.query.filter_by(render_id=render_id).count()
        version = existing + 1
    
    edit = KaipaiEdit(
        id=str(uuid.uuid4()),
        render_id=render_id,
        parent_id=parent_id,
        version=version,
        original_video_url=render.file_path,
        status='draft'
    )
    
    db.session.add(edit)
    db.session.commit()
    
    return jsonify({
        'edit_id': edit.id,
        'version': version,
        'status': 'draft',
        'video_url': f'/renders/{render.file_path.split("/")[-1]}' if render.file_path else None
    })

@kaipai_bp.route('/kaipai/<edit_id>/transcribe', methods=['POST'])
def start_transcription(edit_id):
    """启动语音识别（转发到Kaipai服务）"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.json or {}
    oss_url = data.get('oss_url')
    
    if not oss_url:
        return jsonify({'error': 'OSS URL required'}), 400
    
    # 转发到Kaipai服务
    try:
        response = requests.post(
            f'{KAIPAI_SERVICE_URL}/api/start-transcription',
            json={
                'taskId': edit_id,
                'ossUrl': oss_url,
                'videoDuration': 0
            },
            timeout=10
        )
        
        if response.ok:
            edit.status = 'transcribing'
            db.session.commit()
            return jsonify({
                'edit_id': edit_id,
                'status': 'transcribing'
            })
        else:
            return jsonify({'error': 'Failed to start transcription'}), 500
            
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Kaipai service not available'}), 503

@kaipai_bp.route('/kaipai/<edit_id>/transcribe/status', methods=['GET'])
def get_transcription_status(edit_id):
    """获取语音识别状态"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 查询Kaipai服务
    try:
        response = requests.get(
            f'{KAIPAI_SERVICE_URL}/api/task/{edit_id}',
            timeout=10
        )
        
        if response.ok:
            data = response.json()
            
            # 如果识别完成，更新状态
            if data.get('status') == 'completed' and edit.status == 'transcribing':
                edit.status = 'draft'
                db.session.commit()
            
            return jsonify({
                'edit_id': edit_id,
                'status': data.get('status'),
                'result': data.get('result'),
                'error': data.get('error')
            })
        else:
            return jsonify({'error': 'Failed to query transcription'}), 500
            
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Kaipai service not available'}), 503

@kaipai_bp.route('/kaipai/<edit_id>', methods=['PUT'])
def update_kaipai_edit(edit_id):
    """保存编辑参数"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.json or {}
    
    # 合并编辑参数
    current_params = edit.edit_params or {}
    current_params.update({
        'removed_segments': data.get('removed_segments', []),
        'subtitle_style': data.get('subtitle_style', {}),
        'bgm': data.get('bgm', {}),
        'template': data.get('template', {})
    })
    
    edit.edit_params = current_params
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'saved',
        'params': current_params
    })

@kaipai_bp.route('/kaipai/<edit_id>/render', methods=['POST'])
def start_render(edit_id):
    """启动视频渲染"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # TODO: 调用视频渲染服务（七牛云pfop或FFmpeg）
    # 这里需要根据 edit.edit_params 中的参数进行渲染
    
    edit.status = 'processing'
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'processing',
        'task_id': f'render_{edit_id}'
    })

@kaipai_bp.route('/renders/<render_id>/kaipai/versions', methods=['GET'])
def get_kaipai_versions(render_id):
    """获取某个render的所有剪辑版本"""
    render = Render.query.get(render_id)
    if not render:
        return jsonify({'error': 'Render not found'}), 404
    
    versions = KaipaiEdit.query.filter_by(render_id=render_id).order_by(KaipaiEdit.version).all()
    
    return jsonify({
        'render_id': render_id,
        'versions': [v.to_dict() for v in versions]
    })
```

#### 3.2.2 注册 Blueprint (backend/routes/__init__.py)

```python
"""
API Routes (Blueprints)
"""
from .auth import auth_bp
from .users import users_bp
from .shots import shots_bp
from .materials import materials_bp
from .upload import upload_bp
from .generate import generate_bp
from .renders import renders_bp
from .static import static_bp
from .kaipai import kaipai_bp  # 新增

__all__ = [
    'auth_bp', 'users_bp', 'shots_bp', 'materials_bp',
    'upload_bp', 'generate_bp', 'renders_bp', 'static_bp',
    'kaipai_bp'  # 新增
]
```

#### 3.2.3 更新 app_new.py

```python
# Import blueprints
from routes import ( 
    auth_bp,
    users_bp,
    shots_bp,
    materials_bp,
    upload_bp,
    generate_bp,
    renders_bp,
    static_bp,
    kaipai_bp  # 新增
)

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    CORS(app)
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    
    # Initialize extensions
    db.init_app(app)
    init_websocket(app)
    
    # Ensure directories exist
    ensure_directories()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(shots_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(generate_bp)
    app.register_blueprint(renders_bp)
    app.register_blueprint(static_bp)
    app.register_blueprint(kaipai_bp)  # 新增
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app
```

### 3.3 前端组件架构

#### 3.3.1 新增组件

```
frontend/src/components/kaipai/
├── KaipaiEditor.tsx           # 主编辑器容器
├── VideoPreview.tsx           # 视频预览区
├── TextEditor.tsx             # 文字快剪面板
├── TemplateSelector.tsx       # 网感模板选择
├── SubtitleEditor.tsx         # 字幕样式编辑
├── BGMSelector.tsx            # BGM选择
├── SegmentList.tsx            # 片段列表
├── SegmentItem.tsx            # 单个片段项
└── hooks/
    ├── useTranscription.ts    # 语音识别Hook
    ├── useVideoSegments.ts    # 片段管理Hook
    └── useKaipaiRender.ts     # 渲染任务Hook
```

#### 3.3.2 ResultsScreen 修改

在混剪结果卡片上添加【网感剪辑】入口按钮：

```tsx
// ResultsScreen.tsx 修改
<div className="absolute bottom-1 left-1 flex gap-1">
  {/* 现有下载按钮 */}
  <button onClick={(e) => handleDownload(item, e)}>...</button>
  
  {/* 新增：网感剪辑按钮 */}
  <button
    onClick={(e) => handleKaipaiEdit(item, e)}
    className="w-6 h-6 bg-purple-600 rounded-full flex items-center justify-center text-white hover:bg-purple-700"
    title="网感剪辑"
  >
    <Scissors size={12} />
  </button>
</div>

// 新增处理函数
const handleKaipaiEdit = async (item: ResultItem, e: React.MouseEvent) => {
  e.stopPropagation();
  
  try {
    // 创建剪辑任务
    const response = await fetch(`${API_BASE_URL}/api/renders/${item.id}/kaipai/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) throw new Error('创建剪辑任务失败');
    
    const data = await response.json();
    
    // 跳转到网感剪辑页面
    onEnterKaipaiEdit({
      editId: data.edit_id,
      renderId: item.id,
      videoUrl: data.video_url,
      version: data.version
    });
  } catch (error) {
    console.error('进入网感剪辑失败:', error);
    alert('进入网感剪辑失败，请重试');
  }
};
```

#### 3.3.3 App.tsx 路由扩展

```tsx
// App.tsx
const [currentScreen, setCurrentScreen] = useState<'home' | 'edit' | 'results' | 'kaipai'>('home');
const [kaipaiContext, setKaipaiContext] = useState<{
  editId: string;
  renderId: string;
  videoUrl: string;
  version: number;
}>();

// 进入网感剪辑
const handleEnterKaipai = (context: typeof kaipaiContext) => {
  setKaipaiContext(context);
  setCurrentScreen('kaipai');
};

// 渲染
return (
  <div className="app">
    {currentScreen === 'home' && <HomeScreen ... />}
    {currentScreen === 'edit' && <EditScreen ... />}
    {currentScreen === 'results' && (
      <ResultsScreen 
        onBack={() => setCurrentScreen('edit')}
        onEnterKaipaiEdit={handleEnterKaipai}
      />
    )}
    {currentScreen === 'kaipai' && kaipaiContext && (
      <KaipaiEditor
        editId={kaipaiContext.editId}
        renderId={kaipaiContext.renderId}
        videoUrl={kaipaiContext.videoUrl}
        version={kaipaiContext.version}
        onBack={() => setCurrentScreen('results')}
      />
    )}
  </div>
);
```

### 3.4 数据流设计

```
用户点击【网感剪辑】
    ↓
ResultsScreen 调用 POST /api/renders/<id>/kaipai/edit
    ↓
主后端创建 KaipaiEdit 记录，返回 edit_id
    ↓
前端路由切换到 KaipaiEditor
    ↓
用户输入OSS URL，点击开始识别
    ↓
主后端转发到 run_v3.py: POST /api/start-transcription
    ↓
run_v3.py 调用 DashScope ASR
    ↓
前端轮询 GET /api/kaipai/<edit_id>/transcribe/status
    ↓
识别完成，返回字级时间戳
    ↓
用户进行文字快剪/模板/字幕/BGM编辑
    ↓
点击保存：PUT /api/kaipai/<edit_id> 保存参数到主后端
    ↓
点击渲染：POST /api/kaipai/<edit_id>/render
    ↓
主后端调用视频渲染服务（七牛云pfop/FFmpeg）
    ↓
轮询渲染进度
    ↓
渲染完成，更新 KaipaiEdit.status = 'completed'
    ↓
返回 ResultsScreen，显示新版本视频
```

---

## 四、阶段实施计划

### 第一阶段：基础集成 (2-3天)

**目标**：实现从混剪结果进入文字快剪的基础流程

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 1. 数据库迁移，添加 KaipaiEdit 模型 | backend/models.py | 2h |
| 2. 创建 kaipai.py 路由模块 | backend/routes/kaipai.py | 4h |
| 3. 注册 Blueprint | backend/routes/__init__.py, app_new.py | 1h |
| 4. ResultsScreen 添加网感剪辑入口 | frontend/src/components/ResultsScreen.tsx | 2h |
| 5. 创建 KaipaiEditor 基础组件 | frontend/src/components/kaipai/KaipaiEditor.tsx | 6h |
| 6. 集成文字快剪功能 | 迁移 editor_v3.html 逻辑 | 8h |
| 7. 联调测试 | - | 4h |

**第一阶段完成后可用功能**：
- 从混剪结果进入文字快剪
- 语音识别 → 字级分割 → 删除片段
- 保存编辑参数（仅保存，不渲染）

### 第二阶段：视频渲染 (2-3天)

**目标**：实现删除片段后的视频渲染导出

| 任务 | 说明 | 工作量 |
|------|------|--------|
| 1. 接入七牛云/腾讯云视频处理 | 调研并接入云服务商API | 4h |
| 2. 实现 /api/kaipai/<edit_id>/render 接口 | backend/routes/kaipai.py | 4h |
| 3. 前端渲染进度展示 | KaipaiEditor 添加渲染状态UI | 4h |
| 4. 版本管理功能 | ResultsScreen 显示多个版本 | 4h |
| 5. 联调测试 | - | 4h |

**第二阶段完成后可用功能**：
- 完整文字快剪流程（识别 → 编辑 → 渲染 → 导出）
- 版本管理（原始版本 + 剪辑版本）

### 第三阶段：增强功能 (3-5天)

**目标**：实现网感模板、字幕样式、BGM功能

| 任务 | 说明 | 工作量 |
|------|------|--------|
| 1. 字幕样式编辑器 | 字体、颜色、位置、动画 | 6h |
| 2. BGM音乐库 | 音乐列表、音量调节、淡入淡出 | 6h |
| 3. 网感模板系统 | 模板选择、参数应用 | 8h |
| 4. 实时预览优化 | 字幕同步、效果预览 | 6h |
| 5. 联调测试 | - | 4h |

---

## 五、技术选型建议

### 5.1 语音识别

| 方案 | 推荐度 | 说明 |
|------|--------|------|
| **阿里云 FunASR** | ⭐⭐⭐⭐⭐ | 当前已接入，中文准确率高，支持字级时间戳 |
| OpenAI Whisper | ⭐⭐⭐⭐ | API简单易用，但英文优化更好 |
| 科大讯飞 | ⭐⭐⭐ | 中文识别率高，但成本较高 |

**建议**：继续使用阿里云 FunASR（已在 run_v3.py 中实现）

### 5.2 视频渲染

| 方案 | 推荐度 | 成本 | 说明 |
|------|--------|------|------|
| **七牛云 pfop** | ⭐⭐⭐⭐⭐ | ¥0.1-0.5/次 | 稳定，支持视频裁剪拼接 |
| 腾讯云 云剪辑 | ⭐⭐⭐⭐ | 按量计费 | 功能完善，支持复杂操作 |
| FFmpeg 自建 | ⭐⭐⭐ | 服务器成本 | 灵活可控，需要自行部署 |

**建议**：第一阶段使用七牛云 pfop，后期可考虑自建 FFmpeg 集群降低成本

### 5.3 字幕渲染

| 方案 | 推荐度 | 说明 |
|------|--------|------|
| **FFmpeg burnsubtitle** | ⭐⭐⭐⭐⭐ | 使用 ASS/SRT 字幕文件叠加 |
| 七牛云 字幕叠加 | ⭐⭐⭐⭐ | 云服务商功能 |

**建议**：使用 FFmpeg 字幕叠加，样式灵活可控

### 5.4 BGM音乐库

| 方案 | 推荐度 | 说明 |
|------|--------|------|
| **自建音乐库** | ⭐⭐⭐⭐⭐ | 购买商用版权音乐，存储在OSS |
| YouTube Audio Library | ⭐⭐⭐ | 免费但选择有限 |

**建议**：初期使用免版权音乐库，后期购买商用版权

---

## 六、成本估算

以月处理 1000 小时视频为例：

| 环节 | 服务商 | 单价 | 月费用 |
|------|--------|------|--------|
| 语音识别 | 阿里云 FunASR | ¥5/小时 | ¥5,000 |
| 视频渲染 | 七牛云 pfop | ¥0.3/次 | ¥300 |
| 存储流量 | 七牛云 OSS | - | ¥500 |
| **总计** | | | **约 ¥5,800/月** |

---

## 七、风险评估与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 语音识别准确率低 | 高 | 提供人工校对功能，允许用户编辑识别结果 |
| 视频渲染失败 | 中 | 实现重试机制，失败时通知用户 |
| 渲染耗时过长 | 中 | 异步处理 + 进度通知，支持后台渲染 |
| 多版本存储成本高 | 中 | 定期清理草稿版本，仅保留最终版本 |
| 浏览器兼容性 | 低 | 使用标准Web API，测试主流浏览器 |

---

## 八、总结

### 推荐方案要点

1. **架构**：
   - 保持 `run_v3.py` 作为独立微服务（语音识别专用）
   - 主后端 `app_new.py` 通过 Blueprint 扩展 `kaipai.py` 模块
   - 主后端负责数据持久化和版本管理

2. **前端**：
   - 将 `editor_v3.html` 重构为 React 组件
   - 在 `ResultsScreen` 添加【网感剪辑】入口
   - 新增 `KaipaiEditor` 组件

3. **数据**：
   - 新增 `KaipaiEdit` 模型管理剪辑版本
   - 与原 `Render` 模型建立外键关系

4. **分阶段实施**：
   - 第一阶段：文字快剪基础功能
   - 第二阶段：视频渲染导出
   - 第三阶段：模板/字幕/BGM增强功能

### 关键修改点（适配 app_new.py 架构）

1. **backend/models.py**: 添加 `KaipaiEdit` 模型
2. **backend/routes/kaipai.py**: 新建 Blueprint，实现版本管理和API转发
3. **backend/routes/__init__.py**: 导出 `kaipai_bp`
4. **backend/app_new.py**: 注册 `kaipai_bp`
5. **frontend/src/components/ResultsScreen.tsx**: 添加网感剪辑入口
6. **frontend/src/components/kaipai/**: 新建网感剪辑组件目录

### 下一步行动

1. 确认方案后，开始第一阶段实施
2. 准备七牛云/腾讯云账号和API密钥
3. 准备商用版权音乐库（或先使用免版权音乐）
