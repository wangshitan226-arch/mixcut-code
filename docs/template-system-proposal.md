# MixCut 模板系统方案设计文档

## 一、方案概述

### 1.1 背景
当前文字快剪功能已完成基础剪辑能力，用户需要进一步将剪辑后的视频套上各种视觉模板（字幕样式、动效、画中画等）以提升视频质量。本方案设计一套完整的**模板上传-编辑-应用**系统，基于阿里云ICE进行云端渲染。

### 1.2 核心目标
- 支持用户上传自定义模板或选择系统预设模板
- 模板可配置字幕样式、视频效果、背景音乐等参数
- 文字快剪后的视频可一键套用模板并提交ICE渲染
- 提供可视化的模板编辑界面

### 1.3 当前已有数据
基于文字快剪功能，系统已保留以下视频相关数据：

| 数据类型 | 来源 | 用途 |
|---------|------|------|
| `original_video_url` | 混剪结果视频 | 模板渲染的主视频源 |
| `asr_result.sentences` | 语音识别结果 | 字幕文案、时间戳 |
| `sentences[].text` | ASR文本 | 字幕内容 |
| `sentences[].beginTime` | ASR时间戳 | 字幕出现时间 |
| `sentences[].endTime` | ASR时间戳 | 字幕结束时间 |
| `sentences[].words` | 词级别识别 | 精确字幕同步 |
| `edit_params.removed_segments` | 用户删除记录 | 计算保留片段时长 |
| `output_video_url` | 快剪导出视频 | 可作为模板输入 |
| `duration` | 视频时长 | 模板时间线规划 |

---

## 二、用户交互流程设计

### 2.1 整体流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     文字快剪完成                                  │
│              (已有：剪辑后视频 + ASR字幕数据)                      │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 进入模板选择界面                                         │
│  - 展示"系统模板库"和"我的模板"两个Tab                            │
│  - 模板以卡片形式展示预览图                                       │
│  - 支持搜索、筛选（风格、场景、时长）                              │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: 选择模板                                                 │
│  - 点击模板卡片进入"模板预览+配置"界面                            │
│  - 可预览模板效果（使用示例视频）                                  │
│  - 点击"使用此模板"进入编辑界面                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: 模板内容编辑（核心界面）                                  │
│  - 左侧：视频预览区（实时预览字幕效果）                            │
│  - 右侧：模板参数配置面板                                          │
│    ├─ 字幕文案编辑（基于ASR结果，可修改）                          │
│    ├─ 字幕样式调整（字体、颜色、位置、动画）                        │
│    ├─ 视频效果配置（缩放、位置、画中画）                           │
│    └─ 背景音乐选择                                                │
│  - 底部：时间轴（显示字幕片段和模板效果节点）                       │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: 提交渲染                                                 │
│  - 点击"生成视频"按钮                                             │
│  - 系统生成ICE Timeline JSON                                      │
│  - 提交阿里云ICE渲染任务                                          │
│  - 显示渲染进度，完成后通知用户                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 界面详细设计

#### 2.2.1 模板选择界面（TemplateSelector）

```
┌─────────────────────────────────────────────────────────────────┐
│  ← 返回                                    模板中心      [搜索]   │
├─────────────────────────────────────────────────────────────────┤
│  [系统模板]  [我的模板]  [上传模板]                               │
├─────────────────────────────────────────────────────────────────┤
│  筛选: [全部 ▼] [电商 ▼] [知识 ▼] [时长 ▼]                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ [预览图] │  │ [预览图] │  │ [预览图] │  │ [预览图] │        │
│  │ 电商促销  │  │ 知识科普  │  │ 产品展示  │  │ 情感语录  │        │
│  │ 00:15    │  │ 00:30    │  │ 00:20    │  │ 00:25    │        │
│  │ 1080P    │  │ 1080P    │  │ 1080P    │  │ 1080P    │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │   +      │  │          │  │          │                      │
│  │ 上传新   │  │          │  │          │                      │
│  │ 模板     │  │          │  │          │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.2.2 模板编辑界面（TemplateEditor）

```
┌─────────────────────────────────────────────────────────────────┐
│  ← 返回      模板: 电商促销大字报           [预览]  [保存]  [渲染] │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┐  ┌─────────────────┐ │
│  │                                      │  │  📋 字幕文案      │ │
│  │         视频预览区                    │  │  ─────────────── │ │
│  │      (带字幕效果预览)                  │  │  □ 春季旅行穿搭   │ │
│  │                                      │  │    00:00-00:03   │ │
│  │      [播放/暂停] [进度条]             │  │  □ 3分钟解决...   │ │
│  │                                      │  │    00:03-00:06   │ │
│  │                                      │  │  □ 90%的人都...   │ │
│  │                                      │  │    00:06-00:09   │ │
│  └──────────────────────────────────────┘  │  [+ 添加字幕]     │ │
│                                            ├─────────────────┤ │
│                                            │  🎨 字幕样式      │ │
│                                            │  ─────────────── │ │
│                                            │  字体: [阿里巴巴..▼]│ │
│                                            │  大小: [━━80━━]   │ │
│                                            │  颜色: [🟡] [⚪] [🟢]│ │
│                                            │  描边: [━━4━━]    │ │
│                                            │  动画: [螺旋入场▼] │ │
│                                            ├─────────────────┤ │
│                                            │  🎬 视频效果      │ │
│                                            │  ─────────────── │ │
│                                            │  智能缩放: [开●]  │ │
│                                            │  缩放强度: [━━1.2━]│ │
│                                            │  转场效果: [淡入▼] │ │
│                                            ├─────────────────┤ │
│                                            │  🎵 背景音乐      │ │
│                                            │  ─────────────── │ │
│                                            │  [选择音乐文件...] │ │
│                                            │  音量: [━━30%━━]  │ │
│                                            └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  时间轴: │字幕1│  字幕2  │   字幕3   │ 字幕4 │ 字幕5 │          │
│          0s    3s      6s         9s    12s    15s    18s       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、前端架构设计

### 3.1 新增组件结构

```
frontend/src/components/
├── TemplateEditor/              # 模板编辑器（新）
│   ├── index.tsx               # 主组件
│   ├── TemplateSelector.tsx    # 模板选择界面
│   ├── TemplatePreview.tsx     # 模板预览组件
│   ├── SubtitleEditor.tsx      # 字幕文案编辑器
│   ├── StylePanel.tsx          # 样式配置面板
│   ├── EffectPanel.tsx         # 视频效果面板
│   ├── Timeline.tsx            # 时间轴组件
│   └── types.ts                # 类型定义
├── KaipaiEditor/               # 文字快剪（已有）
└── ...
```

### 3.2 核心类型定义

```typescript
// TemplateEditor/types.ts

// 模板定义
export interface Template {
  id: string;
  name: string;
  description: string;
  previewUrl: string;
  category: 'ecommerce' | 'knowledge' | 'emotion' | 'product';
  duration: number;
  resolution: { width: number; height: number };
  config: TemplateConfig;
  isSystem: boolean;  // 系统模板 or 用户上传
  userId?: string;
  createdAt: string;
}

// 模板配置
export interface TemplateConfig {
  // 字幕样式配置
  subtitleStyles: {
    title: SubtitleStyle;      // 主标题样式 (#)
    subtitle: SubtitleStyle;   // 副标题样式 (##)
    section: SubtitleStyle;    // 章节样式 (###)
    emphasis: SubtitleStyle;   // 强调样式 (!)
    data: SubtitleStyle;       // 数据样式 ($)
    quote: SubtitleStyle;      // 引用样式 (>)
    tip: SubtitleStyle;        // 提示样式 (@)
    question: SubtitleStyle;   // 问题样式 (?)
    body: SubtitleStyle;       // 正文样式
  };
  
  // 视频效果配置
  videoEffects: {
    enableSmartZoom: boolean;   // 智能缩放
    zoomIntensity: number;      // 缩放强度 1.0-2.0
    transitionType: string;     // 转场类型
    pipVideos?: PIPVideoConfig[]; // 画中画配置
  };
  
  // 背景音乐
  backgroundMusic?: {
    url: string;
    volume: number;  // 0-1
  };
}

// 字幕样式
export interface SubtitleStyle {
  font: string;
  fontSize: number;
  fontColor: string;
  outline: number;
  outlineColor: string;
  motionIn: string;
  motionOut: string;
  y: number;  // 垂直位置 0-1
  weight: number;  // 时长权重
  loop?: number;
  loopEffect?: string;
  hasBox?: boolean;
}

// 画中画配置
export interface PIPVideoConfig {
  url: string;
  x: number;
  y: number;
  width: number;
  height: number;
  startTime: number;
  duration: number;
  borderRadius?: number;
}

// 字幕片段（结合ASR数据）
export interface SubtitleSegment {
  id: string;
  type: 'title' | 'subtitle' | 'section' | 'emphasis' | 
        'data' | 'quote' | 'tip' | 'question' | 'body';
  content: string;
  startTime: number;  // 秒
  endTime: number;
  style?: SubtitleStyle;  // 可覆盖默认样式
}

// ICE渲染任务
export interface ICERenderTask {
  id: string;
  editId: string;
  templateId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  jobId?: string;  // 阿里云ICE Job ID
  outputUrl?: string;
  progress: number;
  createdAt: string;
}
```

### 3.3 状态管理

```typescript
// TemplateEditor/index.tsx 核心状态

const [template, setTemplate] = useState<Template | null>(null);
const [subtitles, setSubtitles] = useState<SubtitleSegment[]>([]);
const [config, setConfig] = useState<TemplateConfig | null>(null);
const [currentTime, setCurrentTime] = useState(0);
const [isPlaying, setIsPlaying] = useState(false);
const [selectedSubtitleId, setSelectedSubtitleId] = useState<string | null>(null);
const [renderTask, setRenderTask] = useState<ICERenderTask | null>(null);
```

---

## 四、后端架构设计

### 4.1 新增数据库模型

```python
# backend/models.py 新增

class Template(db.Model):
    """视频模板表"""
    __tablename__ = 'templates'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)  # null为系统模板
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    preview_url = db.Column(db.String(500))  # 预览图OSS地址
    category = db.Column(db.String(50))  # ecommerce, knowledge, emotion, product
    duration = db.Column(db.Integer)  # 推荐时长（秒）
    width = db.Column(db.Integer, default=1080)
    height = db.Column(db.Integer, default=1920)
    
    # 模板配置（JSON存储）
    config = db.Column(db.Text, nullable=False)  # TemplateConfig JSON
    
    is_system = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'preview_url': self.preview_url,
            'category': self.category,
            'duration': self.duration,
            'resolution': {'width': self.width, 'height': self.height},
            'config': json.loads(self.config) if self.config else None,
            'is_system': self.is_system,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class TemplateRenderTask(db.Model):
    """模板渲染任务表"""
    __tablename__ = 'template_render_tasks'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    edit_id = db.Column(db.String(36), db.ForeignKey('kaipai_edits.id'), nullable=False)
    template_id = db.Column(db.String(36), db.ForeignKey('templates.id'), nullable=False)
    
    # 渲染配置（用户自定义后的配置）
    render_config = db.Column(db.Text)  # 完整的渲染配置JSON
    
    # ICE任务信息
    ice_job_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    output_url = db.Column(db.String(500))
    error_message = db.Column(db.Text)
    progress = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    completed_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'edit_id': self.edit_id,
            'template_id': self.template_id,
            'status': self.status,
            'output_url': self.output_url,
            'progress': self.progress,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
```

### 4.2 新增API路由

```python
# backend/routes/templates.py

from flask import Blueprint, request, jsonify
from models import Template, TemplateRenderTask, KaipaiEdit
from extensions import db
from utils.ice_renderer import generate_ice_timeline, submit_ice_job
import uuid
import json

templates_bp = Blueprint('templates', __name__, url_prefix='/api')

# ========== 模板管理API ==========

@templates_bp.route('/templates', methods=['GET'])
def get_templates():
    """获取模板列表"""
    user_id = request.args.get('user_id')
    category = request.args.get('category')
    is_system = request.args.get('is_system', 'true').lower() == 'true'
    
    query = Template.query.filter_by(is_active=True)
    
    if is_system:
        query = query.filter_by(is_system=True)
    elif user_id:
        query = query.filter_by(user_id=user_id)
    
    if category:
        query = query.filter_by(category=category)
    
    templates = query.order_by(Template.created_at.desc()).all()
    return jsonify({'templates': [t.to_dict() for t in templates]})


@templates_bp.route('/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """获取单个模板详情"""
    template = Template.query.get_or_404(template_id)
    return jsonify(template.to_dict())


@templates_bp.route('/templates', methods=['POST'])
def create_template():
    """创建新模板（用户上传）"""
    data = request.json
    
    template = Template(
        id=str(uuid.uuid4()),
        user_id=data.get('user_id'),
        name=data['name'],
        description=data.get('description'),
        preview_url=data.get('preview_url'),
        category=data.get('category', 'custom'),
        duration=data.get('duration'),
        width=data.get('width', 1080),
        height=data.get('height', 1920),
        config=json.dumps(data['config']),
        is_system=False
    )
    
    db.session.add(template)
    db.session.commit()
    
    return jsonify(template.to_dict()), 201


@templates_bp.route('/templates/<template_id>', methods=['PUT'])
def update_template(template_id):
    """更新模板配置"""
    template = Template.query.get_or_404(template_id)
    data = request.json
    
    if 'name' in data:
        template.name = data['name']
    if 'config' in data:
        template.config = json.dumps(data['config'])
    if 'preview_url' in data:
        template.preview_url = data['preview_url']
    
    db.session.commit()
    return jsonify(template.to_dict())


# ========== 模板渲染API ==========

@templates_bp.route('/templates/render', methods=['POST'])
def render_with_template():
    """使用模板渲染视频"""
    data = request.json
    edit_id = data.get('edit_id')
    template_id = data.get('template_id')
    custom_config = data.get('config')  # 用户自定义配置
    
    # 获取编辑数据
    edit = KaipaiEdit.query.get_or_404(edit_id)
    template = Template.query.get_or_404(template_id)
    
    # 合并配置（模板默认 + 用户自定义）
    base_config = json.loads(template.config) if template.config else {}
    if custom_config:
        base_config.update(custom_config)
    
    # 生成ICE Timeline
    timeline = generate_ice_timeline(edit, base_config)
    
    # 提交ICE任务
    try:
        job_id, output_url = submit_ice_job(timeline, edit.user_id)
        
        # 创建任务记录
        task = TemplateRenderTask(
            id=str(uuid.uuid4()),
            user_id=edit.user_id,
            edit_id=edit_id,
            template_id=template_id,
            render_config=json.dumps(base_config),
            ice_job_id=job_id,
            status='processing',
            output_url=output_url
        )
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'task_id': task.id,
            'job_id': job_id,
            'status': 'processing',
            'output_url': output_url
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@templates_bp.route('/templates/render/<task_id>/status', methods=['GET'])
def get_render_status(task_id):
    """获取渲染任务状态"""
    task = TemplateRenderTask.query.get_or_404(task_id)
    
    # 如果还在处理中，查询ICE状态
    if task.status == 'processing' and task.ice_job_id:
        from utils.ice_renderer import get_job_status
        ice_status = get_job_status(task.ice_job_id)
        
        if ice_status == 'Success':
            task.status = 'completed'
            task.progress = 100
            task.completed_at = db.func.now()
            db.session.commit()
        elif ice_status == 'Failed':
            task.status = 'failed'
            db.session.commit()
        else:
            # 更新进度
            task.progress = min(95, task.progress + 5)
            db.session.commit()
    
    return jsonify(task.to_dict())


@templates_bp.route('/templates/render/<task_id>', methods=['DELETE'])
def cancel_render(task_id):
    """取消渲染任务"""
    task = TemplateRenderTask.query.get_or_404(task_id)
    
    if task.status == 'processing':
        # 调用ICE取消任务
        from utils.ice_renderer import cancel_job
        cancel_job(task.ice_job_id)
        task.status = 'cancelled'
        db.session.commit()
    
    return jsonify({'status': 'cancelled'})
```

### 4.3 ICE渲染工具模块

```python
# backend/utils/ice_renderer.py

import json
from alibabacloud_ice20201109.client import Client as ICEClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_ice20201109 import models as ice_models
from config import ICE_CONFIG, OSS_CONFIG

def create_ice_client():
    """创建ICE客户端"""
    config = open_api_models.Config(
        access_key_id=ICE_CONFIG['access_key_id'],
        access_key_secret=ICE_CONFIG['access_key_secret']
    )
    config.endpoint = f"ice.{ICE_CONFIG['region']}.aliyuncs.com"
    return ICEClient(config)


def generate_ice_timeline(edit, config):
    """
    根据编辑数据和模板配置生成ICE Timeline
    
    Args:
        edit: KaipaiEdit对象
        config: 模板配置
    
    Returns:
        dict: ICE Timeline JSON
    """
    # 获取ASR结果
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    sentences = asr_result.get('sentences', [])
    
    # 获取保留的片段（去除被删除的）
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    removed_ids = {s['id'] for s in removed_segments}
    
    # 过滤保留的句子
    kept_sentences = [s for s in sentences if s['id'] not in removed_ids]
    
    # 计算总时长
    video_duration = calculate_video_duration(kept_sentences)
    
    # 生成字幕clips
    subtitle_clips = generate_subtitle_clips(kept_sentences, config['subtitleStyles'])
    
    # 生成视频clips（带效果）
    video_clips = generate_video_clips(edit.original_video_url, video_duration, config['videoEffects'])
    
    # 生成音频clips
    audio_clips = generate_audio_clips(edit.original_video_url, config.get('backgroundMusic'), video_duration)
    
    # 组装Timeline
    timeline = {
        "VideoTracks": [{"VideoTrackClips": video_clips}],
        "SubtitleTracks": [{"SubtitleTrackClips": subtitle_clips}],
        "AudioTracks": [{"AudioTrackClips": audio_clips}]
    }
    
    return timeline


def generate_subtitle_clips(sentences, styles_config):
    """生成字幕clips"""
    clips = []
    
    for sent in sentences:
        # 根据内容类型选择样式
        style = determine_subtitle_style(sent, styles_config)
        
        clip = {
            "Type": "Text",
            "Content": sent['text'],
            "TimelineIn": sent['beginTime'] / 1000,
            "TimelineOut": sent['endTime'] / 1000,
            "X": 0.5,
            "Y": style['y'],
            "Alignment": "Center",
            "Font": style['font'],
            "FontSize": style['fontSize'],
            "FontColor": style['fontColor'],
            "Outline": style['outline'],
            "OutlineColour": style['outlineColor'],
            "AaiMotionIn": 0.8,
            "AaiMotionOut": 0.5,
            "AaiMotionInEffect": style['motionIn'],
            "AaiMotionOutEffect": style['motionOut']
        }
        
        if style.get('loop'):
            clip['AaiMotionLoop'] = style['loop']
            clip['AaiMotionLoopEffect'] = style.get('loopEffect', 'bounce')
        
        clips.append(clip)
    
    return clips


def generate_video_clips(video_url, duration, effects_config):
    """生成视频clips（带智能缩放等效果）"""
    clips = []
    
    if not effects_config.get('enableSmartZoom'):
        # 无效果，直接播放
        clips.append({
            "Type": "Video",
            "MediaURL": video_url,
            "TimelineIn": 0,
            "TimelineOut": duration
        })
    else:
        # 智能缩放效果
        zoom_intensity = effects_config.get('zoomIntensity', 1.2)
        segment_duration = 3  # 每3秒一个片段
        num_segments = int(duration / segment_duration) + 1
        
        for i in range(num_segments):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, duration)
            
            # 奇数片段放大
            if i % 2 == 1:
                scale = zoom_intensity
                offset_x = 0.05 if i % 4 == 1 else -0.05
                offset_y = 0.05 if i % 4 == 3 else -0.05
            else:
                scale = 1.0
                offset_x = 0
                offset_y = 0
            
            clip = {
                "Type": "Video",
                "MediaURL": video_url,
                "TimelineIn": start,
                "TimelineOut": end,
                "In": start,
                "Out": end,
                "X": 0.5 + offset_x,
                "Y": 0.5 + offset_y,
                "Scale": scale
            }
            clips.append(clip)
    
    return clips


def generate_audio_clips(video_url, bgm_config, duration):
    """生成音频clips"""
    clips = []
    
    # 主视频音频
    clips.append({
        "Type": "Audio",
        "MediaURL": video_url,
        "TimelineIn": 0,
        "TimelineOut": duration
    })
    
    # 背景音乐
    if bgm_config:
        clips.append({
            "Type": "Audio",
            "MediaURL": bgm_config['url'],
            "TimelineIn": 0,
            "TimelineOut": duration,
            "Effects": [{
                "Type": "Volume",
                "Gain": bgm_config.get('volume', 0.3)
            }]
        })
    
    return clips


def submit_ice_job(timeline, user_id):
    """提交ICE渲染任务"""
    client = create_ice_client()
    
    # 生成输出地址
    import time
    timestamp = int(time.time())
    output_url = f"https://{OSS_CONFIG['bucket']}.oss-cn-{OSS_CONFIG['region']}.aliyuncs.com/renders/{user_id}/{timestamp}_template.mp4"
    
    output_config = {
        "MediaURL": output_url,
        "Width": 1080,
        "Height": 1920,
        "Fps": 30,
        "VideoCodec": "H264",
        "VideoBitrate": 4000,
        "AudioCodec": "AAC",
        "AudioBitrate": 128
    }
    
    request = ice_models.SubmitMediaProducingJobRequest(
        timeline=json.dumps(timeline, ensure_ascii=False),
        output_media_config=json.dumps(output_config)
    )
    
    response = client.submit_media_producing_job(request)
    job_id = response.body.job_id
    
    return job_id, output_url


def get_job_status(job_id):
    """查询ICE任务状态"""
    client = create_ice_client()
    
    request = ice_models.GetMediaProducingJobRequest(job_id=job_id)
    response = client.get_media_producing_job(request)
    
    return response.body.job.status  # Success, Failed, Processing
```

---

## 五、系统集成流程

### 5.1 与文字快剪的集成

```
KaipaiEditor (文字快剪完成)
    │
    ▼
┌─────────────────────────────────────┐
│  用户点击"下一步：套用模板"           │
│  或保存草稿后从首页进入              │
└─────────────────────────────────────┘
    │
    ▼
TemplateSelector (模板选择)
    │
    ├── 用户选择系统模板
    │   └── 加载模板默认配置
    │
    └── 用户选择"我的模板"
        └── 加载用户自定义模板
    │
    ▼
TemplateEditor (模板编辑)
    │
    ├── 自动导入ASR字幕数据
    │   └── sentences[] → subtitleSegments[]
    │
    ├── 应用模板默认样式
    │   └── 根据内容类型匹配样式
    │
    ├── 用户可编辑：
    │   ├── 修改字幕文案
    │   ├── 调整字幕时间
    │   ├── 修改样式参数
    │   └── 配置视频效果
    │
    ▼
提交渲染
    │
    ├── 生成ICE Timeline JSON
    ├── 提交阿里云ICE
    └── 创建渲染任务记录
    │
    ▼
渲染完成
    │
    ├── 通知用户
    └── 在"我的作品"中展示
```

### 5.2 数据流图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  KaipaiEdit │────▶│  Template   │────▶│ ICE Timeline│
│   (数据)     │     │   (配置)     │     │   (渲染)     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ original_   │     │ subtitle    │     │ submit_     │
│ video_url   │     │ styles      │     │ ice_job()   │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ asr_result  │     │ video       │     │ job_id      │
│ .sentences  │     │ effects     │     │ output_url  │
├─────────────┤     ├─────────────┤     └─────────────┘
│ edit_params │     │ background  │
│ .removed_   │     │ music       │
│ segments    │     └─────────────┘
└─────────────┘
```

---

## 六、技术实现要点

### 6.1 字幕样式智能匹配

```python
def determine_subtitle_style(sentence, styles_config):
    """
    根据句子内容特征自动匹配样式
    
    规则：
    - 包含数字+%/倍 → data样式
    - 以"为什么/如何/怎么"开头 → question样式
    - 包含引号 → quote样式
    - 长度<10字 → title样式
    - 包含"!" → emphasis样式
    - 其他 → body样式
    """
    text = sentence['text']
    
    if re.search(r'\d+[%倍]', text):
        return styles_config['data']
    elif re.match(r'^(为什么|如何|怎么|什么)', text):
        return styles_config['question']
    elif '"' in text or '"' in text:
        return styles_config['quote']
    elif len(text) < 10:
        return styles_config['title']
    elif '!' in text or '！' in text:
        return styles_config['emphasis']
    else:
        return styles_config['body']
```

### 6.2 实时预览方案

由于ICE渲染需要时间，前端预览采用**模拟方案**：

```typescript
// 使用CSS动画模拟字幕效果
const SubtitlePreview = ({ segment, currentTime }: Props) => {
  const isActive = currentTime >= segment.startTime && currentTime < segment.endTime;
  
  return (
    <div 
      className={`subtitle ${isActive ? 'animate-' + segment.style.motionIn : 'hidden'}`}
      style={{
        fontFamily: segment.style.font,
        fontSize: segment.style.fontSize,
        color: segment.style.fontColor,
        top: `${segment.style.y * 100}%`,
        textShadow: `-2px -2px 0 ${segment.style.outlineColor}, ...`
      }}
    >
      {segment.content}
    </div>
  );
};
```

### 6.3 模板预设方案

系统预设模板存储在数据库中，初始化时自动创建：

```python
def init_system_templates():
    """初始化系统预设模板"""
    templates = [
        {
            'name': '电商促销大字报',
            'category': 'ecommerce',
            'config': {
                'subtitleStyles': {
                    'title': {
                        'font': 'AlibabaPuHuiTi-Heavy',
                        'fontSize': 90,
                        'fontColor': '#FFD700',
                        'outline': 5,
                        'outlineColor': '#8B4513',
                        'motionIn': 'rotateup_in',
                        'motionOut': 'close_out',
                        'y': 0.35
                    },
                    # ... 其他样式
                },
                'videoEffects': {
                    'enableSmartZoom': True,
                    'zoomIntensity': 1.2,
                    'transitionType': 'fade'
                }
            }
        },
        # ... 更多模板
    ]
    
    for tmpl in templates:
        if not Template.query.filter_by(name=tmpl['name'], is_system=True).first():
            db.session.add(Template(
                id=str(uuid.uuid4()),
                name=tmpl['name'],
                category=tmpl['category'],
                config=json.dumps(tmpl['config']),
                is_system=True
            ))
    
    db.session.commit()
```

---

## 七、开发计划

### Phase 1: 基础架构（1周）
- [ ] 数据库模型创建（Template, TemplateRenderTask）
- [ ] ICE渲染工具模块开发
- [ ] 后端API开发（模板CRUD + 渲染接口）

### Phase 2: 前端界面（1周）
- [ ] TemplateSelector组件开发
- [ ] TemplateEditor核心组件开发
- [ ] 字幕编辑面板开发
- [ ] 样式配置面板开发

### Phase 3: 集成联调（1周）
- [ ] 与KaipaiEditor集成
- [ ] 实时预览功能实现
- [ ] ICE渲染流程联调
- [ ] 系统预设模板制作

### Phase 4: 优化迭代（1周）
- [ ] 用户上传模板功能
- [ ] 模板预览图生成
- [ ] 性能优化
- [ ] Bug修复

---

## 八、附录

### 8.1 阿里云ICE配置

```python
# backend/config.py

ICE_CONFIG = {
    'access_key_id': 'your-access-key',
    'access_key_secret': 'your-secret',
    'region': 'cn-beijing'
}
```

### 8.2 系统预设模板清单

| 模板名称 | 类别 | 特点 | 适用场景 |
|---------|------|------|---------|
| 电商促销大字报 | 电商 | 金色大字、强调动画 | 商品促销、活动推广 |
| 知识科普简洁风 | 知识 | 清晰排版、适中字号 | 知识分享、教程讲解 |
| 情感语录文艺风 | 情感 | 楷体引用、淡入淡出 | 情感语录、鸡汤文案 |
| 产品展示专业风 | 产品 | 画中画、数据展示 | 产品介绍、功能展示 |
| 搞笑段子活泼风 | 娱乐 | 多彩配色、弹跳动画 | 搞笑视频、段子分享 |

---

**文档版本**: v1.0  
**创建日期**: 2026-04-22  
**作者**: AI Assistant
