# MixCut + 开拍式网感剪辑集成方案（完全集成版）

## 一、方案调整说明

根据您的反馈，调整架构设计：
- **不再单独开启端口**：`run_v3.py` 的功能直接集成到主后端
- **复用现有架构**：将语音识别功能放入 `utils/` 目录作为工具函数
- **统一服务**：所有API通过 `app_new.py` 的单一端口提供服务

## 二、集成后架构

```
MixCut 后端架构（集成后）
├── backend/
│   ├── app_new.py              # 主入口（单一服务，端口3002）
│   ├── config.py               # 配置管理
│   ├── extensions.py           # Flask扩展
│   ├── models.py               # 数据模型（新增 KaipaiEdit）
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── kaipai.py           # 网感剪辑API路由（新增）
│   │   └── ...                 # 其他路由
│   ├── services/               # 业务逻辑层
│   │   └── kaipai_service.py   # 网感剪辑业务逻辑（新增）
│   └── utils/
│       ├── __init__.py
│       ├── video.py            # 现有视频处理
│       ├── kaipai_asr.py       # 语音识别工具（从run_v3.py迁移）
│       └── kaipai_render.py    # 视频渲染工具（新增）
```

## 三、具体集成步骤

### 步骤1：创建语音识别工具模块

**文件**: `backend/utils/kaipai_asr.py`

将 `run_v3.py` 中的语音识别相关函数迁移到此文件：

```python
"""
Kaipai ASR (Automatic Speech Recognition) utilities
从 run_v3.py 迁移的语音识别功能
"""
import os
import uuid
import requests
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 阿里云 DashScope 配置（从环境变量或config读取）
DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', 'sk-a555a4e29a474a6989cb872de3a3070a')
DASHSCOPE_API_URL = 'https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription'
DASHSCOPE_TASK_URL = 'https://dashscope.aliyuncs.com/api/v1/tasks'

# 语气词列表
FILLER_WORDS = {'嗯', '啊', '哦', '呃', '唉', '哎', '哟', '哈', '嘿', '哼', '呢', '吧', '吗'}


def is_filler_word(text: str) -> bool:
    """判断是否为语气词"""
    return text.strip() in FILLER_WORDS


def format_time(ms: int) -> str:
    """毫秒转时间字符串 mm:ss"""
    seconds = ms // 1000
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"


def split_words_by_silence(words: List[Dict], min_split_gap: int = 100, silence_threshold: int = 300) -> List[Dict]:
    """
    按字间静音分割words列表
    - >100ms 分割成新短句
    - >300ms 设为静音段
    """
    if not words:
        return []
    
    logger.info(f"[分割开始] 共 {len(words)} 个词, 分割阈值: {min_split_gap}ms, 静音阈值: {silence_threshold}ms")
    
    # 计算所有词间间隔
    word_gaps = []
    for i in range(1, len(words)):
        prev_word = words[i-1]
        curr_word = words[i]
        prev_end = prev_word.get('end_time', 0)
        curr_begin = curr_word.get('begin_time', 0)
        gap = curr_begin - prev_end
        
        prev_text = prev_word.get('text', '') + prev_word.get('punctuation', '')
        curr_text = curr_word.get('text', '') + curr_word.get('punctuation', '')
        
        word_gaps.append({
            'index': i,
            'prev_text': prev_text,
            'curr_text': curr_text,
            'gap': gap,
            'should_split': gap >= min_split_gap,
            'is_silence': gap >= silence_threshold
        })
    
    # 按间隔分割
    groups = []
    current_group = [words[0]]
    current_silence_before = 0
    
    for i in range(1, len(words)):
        gap_info = word_gaps[i-1]
        
        if gap_info['should_split']:
            groups.append({
                'words': current_group,
                'silence_before': current_silence_before,
                'is_silence': current_silence_before >= silence_threshold
            })
            current_group = [words[i]]
            current_silence_before = gap_info['gap']
        else:
            current_group.append(words[i])
    
    if current_group:
        groups.append({
            'words': current_group,
            'silence_before': current_silence_before,
            'is_silence': current_silence_before >= silence_threshold
        })
    
    logger.info(f"[分割完成] 分成 {len(groups)} 个片段")
    return groups


def convert_to_kaipai_format(asr_result: Dict, video_duration_ms: int) -> Dict:
    """
    将ASR结果转换为开拍格式
    """
    transcripts = asr_result.get('transcripts', [])
    all_words = []
    
    for transcript in transcripts:
        for sent in transcript.get('sentences', []):
            all_words.extend(sent.get('words', []))
    
    if not all_words:
        return {'sentences': [], 'videoInfo': {'duration': video_duration_ms // 1000}}
    
    all_words.sort(key=lambda w: w.get('begin_time', 0))
    
    segments = []
    segment_id = 1
    
    # 1. 检测视频开头静音
    first_word_begin = all_words[0].get('begin_time', 0)
    if first_word_begin >= 300:
        segments.append({
            'id': str(segment_id),
            'time': format_time(0),
            'beginTime': 0,
            'endTime': first_word_begin,
            'text': f'[无声 {first_word_begin/1000:.2f}s]',
            'words': [],
            'type': 'silence',
            'silenceDuration': first_word_begin,
            'selected': False,
            'expanded': False
        })
        segment_id += 1
    
    # 2. 按词间静音分割
    word_groups = split_words_by_silence(all_words, min_split_gap=100, silence_threshold=300)
    
    for i, group in enumerate(word_groups):
        words = group['words']
        silence_before = group['silence_before']
        is_silence = group['is_silence']
        
        # 添加静音段
        if is_silence and i > 0:
            prev_end = words[0].get('begin_time', 0) - silence_before
            curr_begin = words[0].get('begin_time', 0)
            segments.append({
                'id': str(segment_id),
                'time': format_time(prev_end),
                'beginTime': prev_end,
                'endTime': curr_begin,
                'text': f'[无声 {silence_before/1000:.2f}s]',
                'words': [],
                'type': 'silence',
                'silenceDuration': silence_before,
                'selected': False,
                'expanded': False
            })
            segment_id += 1
        
        # 添加语音段
        text = ''.join([w.get('text', '') + w.get('punctuation', '') for w in words])
        begin_time = words[0].get('begin_time', 0)
        end_time = words[-1].get('end_time', 0)
        
        word_list = []
        has_filler = False
        for w in words:
            word_text = w.get('text', '').strip()
            word_info = {
                'text': word_text + w.get('punctuation', ''),
                'beginTime': w.get('begin_time', 0),
                'endTime': w.get('end_time', 0),
                'isFiller': is_filler_word(word_text)
            }
            word_list.append(word_info)
            if word_info['isFiller']:
                has_filler = True
        
        segments.append({
            'id': str(segment_id),
            'time': format_time(begin_time),
            'beginTime': begin_time,
            'endTime': end_time,
            'text': text,
            'words': word_list,
            'type': 'speech',
            'hasFiller': has_filler,
            'selected': False,
            'expanded': False
        })
        segment_id += 1
    
    # 3. 检测视频结尾静音
    last_word_end = all_words[-1].get('end_time', 0)
    ending_silence = video_duration_ms - last_word_end
    if ending_silence >= 300:
        segments.append({
            'id': str(segment_id),
            'time': format_time(last_word_end),
            'beginTime': last_word_end,
            'endTime': video_duration_ms,
            'text': f'[无声 {ending_silence/1000:.2f}s]',
            'words': [],
            'type': 'silence',
            'silenceDuration': ending_silence,
            'selected': False,
            'expanded': False
        })
    
    return {
        'sentences': segments,
        'videoInfo': {
            'duration': video_duration_ms // 1000,
            'format': asr_result.get('properties', {}).get('audio_format', 'unknown')
        }
    }


# ==================== DashScope API 调用 ====================

def submit_asr_task(file_url: str) -> Dict:
    """提交语音识别任务到 DashScope"""
    headers = {
        'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
        'Content-Type': 'application/json',
        'X-DashScope-Async': 'enable'
    }
    
    data = {
        'model': 'fun-asr',
        'input': {
            'file_urls': [file_url]
        },
        'parameters': {
            'channel_id': [0],
            'diarization_enabled': False
        }
    }
    
    response = requests.post(DASHSCOPE_API_URL, headers=headers, json=data, timeout=30)
    return response.json()


def query_asr_task(task_id: str) -> Dict:
    """查询ASR任务状态"""
    headers = {
        'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(f'{DASHSCOPE_TASK_URL}/{task_id}', headers=headers, timeout=30)
    return response.json()


def fetch_transcription_result(transcription_url: str) -> Dict:
    """获取识别结果"""
    response = requests.get(transcription_url, timeout=30)
    return response.json()


# ==================== 任务管理（内存存储） ====================

# 全局任务存储（生产环境建议使用Redis）
asr_tasks = {}


def create_asr_task(task_id: str, file_url: str) -> Dict:
    """创建新的ASR任务"""
    asr_tasks[task_id] = {
        'id': task_id,
        'status': 'pending',
        'file_url': file_url,
        'created_at': datetime.now().isoformat(),
        'result': None,
        'error': None
    }
    return asr_tasks[task_id]


def get_asr_task(task_id: str) -> Optional[Dict]:
    """获取任务状态"""
    return asr_tasks.get(task_id)


def process_asr_task(task_id: str, file_url: str):
    """异步处理ASR任务（在线程中执行）"""
    import threading
    import time
    
    def _process():
        try:
            asr_tasks[task_id]['status'] = 'transcribing'
            
            # 提交任务
            submit_result = submit_asr_task(file_url)
            asr_task_id = submit_result.get('output', {}).get('task_id')
            
            if not asr_task_id:
                raise Exception('未能获取ASR任务ID')
            
            asr_tasks[task_id]['asr_task_id'] = asr_task_id
            
            # 轮询等待
            max_attempts = 300
            for i in range(max_attempts):
                result = query_asr_task(asr_task_id)
                status = result.get('output', {}).get('task_status')
                
                if status == 'SUCCEEDED':
                    transcription_url = result.get('output', {}).get('results', [{}])[0].get('transcription_url')
                    if not transcription_url:
                        raise Exception('未能获取识别结果URL')
                    
                    raw_result = fetch_transcription_result(transcription_url)
                    video_duration = raw_result.get('properties', {}).get('original_duration_in_milliseconds', 0)
                    frontend_data = convert_to_kaipai_format(raw_result, video_duration)
                    
                    asr_tasks[task_id]['status'] = 'completed'
                    asr_tasks[task_id]['result'] = frontend_data
                    logger.info(f"ASR任务 {task_id} 完成")
                    return
                    
                elif status == 'FAILED':
                    results = result.get('output', {}).get('results', [])
                    error_info = results[0] if results else {}
                    raise Exception(f"[{error_info.get('code', '未知错误')}] {error_info.get('message', '无详细信息')}")
                
                time.sleep(1)
            
            raise Exception('等待语音识别结果超时')
            
        except Exception as e:
            logger.error(f"ASR任务 {task_id} 失败: {e}")
            asr_tasks[task_id]['status'] = 'failed'
            asr_tasks[task_id]['error'] = str(e)
    
    thread = threading.Thread(target=_process)
    thread.daemon = True
    thread.start()
```

### 步骤2：更新 utils/__init__.py

```python
"""
Utility functions for MixCut backend
"""
from .validators import validate_username, validate_password, validate_email, validate_phone
from .video import (
    allowed_file, get_quality_settings, transcode_to_unified,
    generate_image_thumbnail, generate_video_thumbnail,
    get_video_duration, format_duration, fast_concat_videos
)
from .helpers import cleanup_renders_with_material, clear_user_renders, calculate_uniqueness_tag
from .cleanup import clear_all_user_renders, clear_user_render_files, clear_user_renders_db
# 新增：导入ASR工具
from .kaipai_asr import (
    create_asr_task, get_asr_task, process_asr_task,
    convert_to_kaipai_format, is_filler_word
)

__all__ = [
    'validate_username', 'validate_password', 'validate_email', 'validate_phone',
    'allowed_file', 'get_quality_settings', 'transcode_to_unified',
    'generate_image_thumbnail', 'generate_video_thumbnail',
    'get_video_duration', 'format_duration', 'fast_concat_videos',
    'cleanup_renders_with_material', 'clear_user_renders', 'calculate_uniqueness_tag',
    'clear_all_user_renders', 'clear_user_render_files', 'clear_user_renders_db',
    # 新增导出
    'create_asr_task', 'get_asr_task', 'process_asr_task',
    'convert_to_kaipai_format', 'is_filler_word'
]
```

### 步骤3：创建网感剪辑路由

**文件**: `backend/routes/kaipai.py`

```python
"""
Kaipai (开拍式) editing routes
完全集成到主后端，不依赖外部服务
"""
from flask import Blueprint, request, jsonify
import uuid
from models import Render, KaipaiEdit
from extensions import db
from utils import create_asr_task, get_asr_task, process_asr_task

kaipai_bp = Blueprint('kaipai', __name__, url_prefix='/api')


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
    """启动语音识别（直接调用工具函数）"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.json or {}
    oss_url = data.get('oss_url')
    
    if not oss_url:
        return jsonify({'error': 'OSS URL required'}), 400
    
    # 创建并启动ASR任务（使用内存存储）
    create_asr_task(edit_id, oss_url)
    process_asr_task(edit_id, oss_url)
    
    edit.status = 'transcribing'
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'transcribing'
    })


@kaipai_bp.route('/kaipai/<edit_id>/transcribe/status', methods=['GET'])
def get_transcription_status(edit_id):
    """获取语音识别状态"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 从内存中获取ASR任务状态
    task = get_asr_task(edit_id)
    if not task:
        return jsonify({'error': 'ASR task not found'}), 404
    
    # 如果识别完成，更新数据库状态
    if task['status'] == 'completed' and edit.status == 'transcribing':
        edit.status = 'draft'
        db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': task['status'],
        'result': task.get('result'),
        'error': task.get('error')
    })


@kaipai_bp.route('/kaipai/<edit_id>', methods=['PUT'])
def update_kaipai_edit(edit_id):
    """保存编辑参数"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    data = request.json or {}
    
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
    
    # TODO: 实现视频渲染逻辑
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

### 步骤4：注册 Blueprint

**修改** `backend/routes/__init__.py`:

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

**修改** `backend/app_new.py`:

```python
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
    app = Flask(__name__)
    CORS(app)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    
    db.init_app(app)
    init_websocket(app)
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
    
    with app.app_context():
        db.create_all()
    
    return app
```

### 步骤5：数据库模型扩展

**修改** `backend/models.py`，添加 `KaipaiEdit` 模型：

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
    
    # 文件路径
    original_video_url = db.Column(db.String(500))
    output_video_url = db.Column(db.String(500))
    output_file_path = db.Column(db.String(500))
    
    # 状态: draft/transcribing/processing/completed/failed
    status = db.Column(db.String(20), default='draft')
    
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

## 四、方案对比

| 方面 | 原方案（独立服务） | 新方案（完全集成） |
|------|-------------------|-------------------|
| **端口占用** | 2个（3002 + 5000） | 1个（3002） |
| **服务管理** | 需要同时启动两个服务 | 只需启动主服务 |
| **代码维护** | 分散在两个文件 | 统一在backend目录 |
| **部署复杂度** | 需要配置多服务 | 单服务部署 |
| **任务状态存储** | 内存（run_v3.py） | 内存（utils/kaipai_asr.py） |
| **扩展性** | 可独立扩展ASR服务 | 需要整体扩展 |

## 五、实施计划

### 第一阶段：迁移ASR功能（1天）

1. 创建 `backend/utils/kaipai_asr.py`（从 `run_v3.py` 迁移）
2. 更新 `backend/utils/__init__.py`
3. 创建 `backend/routes/kaipai.py`
4. 注册 Blueprint
5. 添加 `KaipaiEdit` 模型
6. 测试语音识别API

### 第二阶段：前端集成（1-2天）

1. ResultsScreen 添加【网感剪辑】入口
2. 创建 KaipaiEditor 组件
3. 联调测试

### 第三阶段：视频渲染（2-3天）

1. 实现视频裁剪渲染功能
2. 接入七牛云/FFmpeg
3. 版本管理功能

## 六、总结

这个完全集成方案的优势：

1. **单一服务**：只需启动 `app_new.py`，端口3002
2. **代码集中**：所有功能在 `backend/` 目录下管理
3. **工具化**：ASR功能作为工具函数，可被多处复用
4. **简化部署**：不需要额外配置 `run_v3.py`

您觉得这个方案如何？如果需要，我可以立即开始实施第一阶段的代码迁移。
