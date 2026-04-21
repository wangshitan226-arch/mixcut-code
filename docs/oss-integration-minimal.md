# MixCut OSS最小化集成方案

## 一、当前流程分析

```
当前混剪流程
============
1. 用户上传素材 → backend/uploads/（本地）
2. 转码统一格式 → backend/unified/（本地）
3. 生成排列组合 → 数据库存储组合规则
4. 用户点击"播放/下载" → 实时合成 → backend/renders/（本地）
5. 用户下载 → 从本地文件读取
```

### 当前痛点
- 视频合成后只有本地路径，没有公网URL
- 文字快剪（开拍功能）需要公网URL进行语音识别
- 服务器磁盘空间有限
- 多台服务器无法共享文件

## 二、优化后的流程

```
优化后流程
==========
1. 用户上传素材 → backend/uploads/（本地，保持不变）
2. 转码统一格式 → backend/unified/（本地，保持不变）
3. 生成排列组合 → 数据库存储组合规则（保持不变）
4. 用户点击"播放/下载"
   → 实时合成 → backend/renders/（本地临时）
   → 上传到OSS → 获取OSS URL
   → 更新数据库：file_path改为OSS URL
   → 删除本地临时文件
5. 用户下载/文字快剪 → 直接使用OSS URL
```

## 三、关键改动点

### 3.1 改动范围

| 步骤 | 改动内容 | 文件路径 |
|------|----------|----------|
| 1 | 添加OSS工具类 | `backend/utils/oss.py`（新增） |
| 2 | 修改合成任务 | `backend/routes/renders.py`（修改） |
| 3 | 添加配置项 | `backend/config.py`（修改） |
| 4 | 更新requirements | `backend/requirements.txt`（修改） |

### 3.2 详细改动

#### 3.2.1 新增：OSS工具类

**文件**: `backend/utils/oss.py`

```python
"""
阿里云OSS工具类
用于视频合成后上传到OSS，获取公网URL
"""
import oss2
import os
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class OSSClient:
    """阿里云OSS客户端"""
    
    def __init__(self):
        # 从环境变量读取配置（生产环境推荐）
        # 或从config.py读取（开发环境）
        from config import OSS_CONFIG
        
        self.access_key_id = OSS_CONFIG.get('access_key_id')
        self.access_key_secret = OSS_CONFIG.get('access_key_secret')
        self.endpoint = OSS_CONFIG.get('endpoint')
        self.bucket_name = OSS_CONFIG.get('bucket_name')
        self.cdn_domain = OSS_CONFIG.get('cdn_domain')  # 可选CDN加速域名
        
        if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
            logger.warning("OSS配置不完整，将使用本地存储模式")
            self.enabled = False
        else:
            self.enabled = True
            self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
    
    def upload_render(self, local_path: str, render_id: str) -> Optional[str]:
        """
        上传混剪结果到OSS
        
        Args:
            local_path: 本地文件路径
            render_id: 渲染ID（用于生成OSS路径）
        
        Returns:
            OSS URL 或 None（上传失败时）
        """
        if not self.enabled:
            logger.info("OSS未启用，跳过上传")
            return None
        
        try:
            # 生成OSS路径: renders/2024/01/15/render_xxx.mp4
            date_str = datetime.now().strftime('%Y/%m/%d')
            filename = os.path.basename(local_path)
            oss_key = f"renders/{date_str}/{filename}"
            
            # 上传文件
            logger.info(f"开始上传 {local_path} 到 OSS/{oss_key}")
            self.bucket.put_object_from_file(oss_key, local_path)
            
            # 获取URL（使用CDN域名如果配置了）
            if self.cdn_domain:
                url = f"https://{self.cdn_domain}/{oss_key}"
            else:
                url = f"https://{self.bucket_name}.{self.endpoint}/{oss_key}"
            
            logger.info(f"上传成功: {url}")
            return url
            
        except Exception as e:
            logger.error(f"上传到OSS失败: {e}")
            return None
    
    def get_signed_url(self, oss_key: str, expiration: int = 3600) -> Optional[str]:
        """
        获取签名URL（用于私有bucket）
        
        Args:
            oss_key: OSS文件路径
            expiration: 过期时间（秒）
        
        Returns:
            签名URL
        """
        if not self.enabled:
            return None
        
        try:
            url = self.bucket.sign_url('GET', oss_key, expiration)
            return url
        except Exception as e:
            logger.error(f"生成签名URL失败: {e}")
            return None
    
    def delete_object(self, oss_key: str) -> bool:
        """删除OSS文件"""
        if not self.enabled:
            return False
        
        try:
            self.bucket.delete_object(oss_key)
            return True
        except Exception as e:
            logger.error(f"删除OSS文件失败: {e}")
            return False


# 全局OSS客户端实例
oss_client = OSSClient()
```

#### 3.2.2 修改：配置项

**文件**: `backend/config.py`

```python
"""
Configuration settings for MixCut Backend
"""
import os

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Upload folders
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
UNIFIED_FOLDER = os.path.join(BASE_DIR, 'unified')
RENDERS_FOLDER = os.path.join(BASE_DIR, 'renders')

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}

# Database
SQLALCHEMY_DATABASE_URI = 'sqlite:///mixcut_refactored.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Video quality settings
QUALITY_SETTINGS = {
    'low': {'scale': '720:1280', 'crf': '23', 'preset': 'ultrafast'},
    'medium': {'scale': '1080:1920', 'crf': '23', 'preset': 'superfast'},
    'high': {'scale': '1440:2560', 'crf': '22', 'preset': 'veryfast'},
    'ultra': {'scale': '2160:3840', 'crf': '20', 'preset': 'faster'}
}

# Cleanup settings
RENDER_MAX_AGE_HOURS = 24

# ==================== 新增：OSS配置 ====================
OSS_CONFIG = {
    # 从环境变量读取，避免硬编码敏感信息
    'access_key_id': os.environ.get('OSS_ACCESS_KEY_ID', ''),
    'access_key_secret': os.environ.get('OSS_ACCESS_KEY_SECRET', ''),
    'endpoint': os.environ.get('OSS_ENDPOINT', 'oss-cn-beijing.aliyuncs.com'),
    'bucket_name': os.environ.get('OSS_BUCKET_NAME', 'mixcut-renders'),
    'cdn_domain': os.environ.get('OSS_CDN_DOMAIN', ''),  # 可选，如: cdn.mixcut.com
}

# 是否启用OSS（如果没有配置AK，则使用本地模式）
OSS_ENABLED = bool(OSS_CONFIG['access_key_id'] and OSS_CONFIG['access_key_secret'])


def ensure_directories():
    """Ensure all required directories exist"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
    os.makedirs(UNIFIED_FOLDER, exist_ok=True)
    os.makedirs(RENDERS_FOLDER, exist_ok=True)
```

#### 3.2.3 修改：合成任务

**文件**: `backend/routes/renders.py`

```python
"""
Render result routes - 优化版本：支持OSS上传
"""
from flask import Blueprint, request, jsonify, send_from_directory
import os
import uuid
import threading
import json
from models import User, Render, Material
from extensions import db, render_tasks
from config import RENDERS_FOLDER
from utils import fast_concat_videos
# ==================== 新增导入 ====================
from utils.oss import oss_client

renders_bp = Blueprint('renders', __name__, url_prefix='/api')


def fast_concat_task(task_id, combo_id, unified_files, output_path):
    """
    Fast concat using -c copy
    优化：合成完成后上传到OSS
    """
    render_tasks[task_id] = {
        'id': task_id,
        'combo_id': combo_id,
        'status': 'processing',
        'progress': 0,
        'output_path': output_path
    }
    
    try:
        render_tasks[task_id]['progress'] = 50
        success = fast_concat_videos(unified_files, output_path)
        
        if success and os.path.exists(output_path):
            render_tasks[task_id]['progress'] = 80
            
            # ==================== 新增：上传到OSS ====================
            oss_url = oss_client.upload_render(output_path, combo_id)
            
            if oss_url:
                # 上传成功，更新任务状态
                render_tasks[task_id]['progress'] = 100
                render_tasks[task_id]['status'] = 'completed'
                render_tasks[task_id]['video_url'] = oss_url  # OSS URL
                render_tasks[task_id]['oss_url'] = oss_url
                
                # 更新数据库：使用OSS URL
                render = Render.query.get(combo_id)
                if render:
                    render.file_path = oss_url  # 存储OSS URL而不是本地路径
                    render.status = 'completed'
                    db.session.commit()
                
                # 可选：删除本地临时文件（节省磁盘空间）
                try:
                    os.remove(output_path)
                    render_tasks[task_id]['local_cleaned'] = True
                except Exception as e:
                    print(f"删除本地文件失败: {e}")
                
                print(f"任务 {task_id} 完成，OSS URL: {oss_url}")
            else:
                # OSS上传失败，回退到本地模式
                render_tasks[task_id]['progress'] = 100
                render_tasks[task_id]['status'] = 'completed'
                render_tasks[task_id]['video_url'] = f'/renders/{os.path.basename(output_path)}'
                
                # 更新数据库：使用本地路径
                render = Render.query.get(combo_id)
                if render:
                    render.file_path = output_path
                    render.status = 'completed'
                    db.session.commit()
                
                print(f"任务 {task_id} 完成（本地模式）: {output_path}")
        else:
            render_tasks[task_id]['status'] = 'failed'
            render_tasks[task_id]['error'] = 'Concat failed'
            
    except Exception as e:
        print(f"任务 {task_id} 失败: {e}")
        render_tasks[task_id]['status'] = 'failed'
        render_tasks[task_id]['error'] = str(e)


@renders_bp.route('/renders', methods=['GET'])
def get_renders():
    """Get all renders for a user"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': '缺少user_id参数'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        renders = Render.query.filter_by(user_id=user_id).order_by(Render.combo_index).all()
        
        if not renders:
            return jsonify({'combinations': []})
        
        combinations = []
        for render in renders:
            # ==================== 修改：判断文件是否存在（支持本地和OSS） ====================
            file_exists = False
            video_url = None
            
            if render.file_path:
                if render.file_path.startswith('http'):
                    # OSS URL，直接可用
                    file_exists = True
                    video_url = render.file_path
                elif os.path.exists(render.file_path):
                    # 本地文件
                    file_exists = True
                    video_url = f'/renders/{os.path.basename(render.file_path)}'
            
            try:
                material_ids = json.loads(render.material_ids)
            except:
                material_ids = []
            
            materials_data = []
            for mat_id in material_ids:
                material = Material.query.get(mat_id)
                if material and material.user_id == user_id:
                    materials_data.append({
                        'id': material.id,
                        'type': material.type,
                        'url': f'/uploads/{os.path.basename(material.file_path)}',
                        'thumbnail': f'/uploads/thumbnails/{os.path.basename(material.thumbnail_path)}',
                        'duration': material.duration,
                        'name': material.original_name
                    })
            
            combo_data = {
                'id': render.id,
                'index': render.combo_index,
                'materials': materials_data,
                'thumbnail': render.thumbnail,
                'duration': render.duration,
                'duration_seconds': render.duration_seconds,
                'tag': render.tag,
                'preview_status': 'completed' if file_exists else 'pending',
                'preview_url': video_url  # 可能是OSS URL或本地URL
            }
            combinations.append(combo_data)
        
        return jsonify({'combinations': combinations})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 其他路由保持不变...
```

#### 3.2.4 修改：requirements.txt

**文件**: `backend/requirements.txt`

```
flask==3.0.0
flask-cors==4.0.0
flask-sqlalchemy==3.1.1
flask-socketio==5.3.0
pillow==10.1.0
opencv-python==4.8.1.78
# ==================== 新增 ====================
oss2==2.18.3
```

### 3.3 环境变量配置

创建 `.env` 文件（不提交到git）：

```bash
# 阿里云OSS配置
OSS_ACCESS_KEY_ID=your_access_key_id
OSS_ACCESS_KEY_SECRET=your_access_key_secret
OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
OSS_BUCKET_NAME=mixcut-renders
OSS_CDN_DOMAIN=cdn.yourdomain.com  # 可选
```

## 四、前端适配

前端无需大改动，因为：
- `preview_url` 可能是OSS URL（`https://...`）或本地URL（`/renders/...`）
- 浏览器会自动处理这两种URL

```tsx
// ResultsScreen.tsx 无需修改，自动兼容
<video src={`${API_BASE_URL}${item.preview_url}`} ... />
// 如果 preview_url 是完整URL（OSS），API_BASE_URL会被忽略
// 如果 preview_url 是相对路径（本地），会拼接成完整URL
```

## 五、文字快剪（开拍）集成

有了OSS URL后，开拍功能可以直接使用：

```python
# backend/routes/kaipai.py

@kaipai_bp.route('/kaipai/<edit_id>/transcribe', methods=['POST'])
def start_transcription(edit_id):
    edit = KaipaiEdit.query.get(edit_id)
    render = Render.query.get(edit.render_id)
    
    # 直接使用 render.file_path（已经是OSS URL）
    video_url = render.file_path
    
    if not video_url:
        return jsonify({'error': '视频尚未合成'}), 400
    
    if not video_url.startswith('http'):
        # 如果是本地路径，需要上传到OSS获取URL
        # 或者返回错误提示用户先合成视频
        return jsonify({'error': '请先合成视频'}), 400
    
    # 启动ASR任务
    create_asr_task(edit_id, video_url)
    process_asr_task(edit_id, video_url)
    
    return jsonify({'status': 'transcribing'})
```

## 六、实施步骤

### 步骤1：创建阿里云OSS资源
1. 登录阿里云控制台
2. 创建OSS Bucket（如 `mixcut-renders`）
3. 获取 AccessKey ID 和 Secret
4. （可选）配置CDN加速域名

### 步骤2：后端代码修改
1. 创建 `backend/utils/oss.py`
2. 修改 `backend/config.py` 添加OSS配置
3. 修改 `backend/routes/renders.py` 添加上传逻辑
4. 更新 `backend/requirements.txt`
5. 修改 `backend/utils/__init__.py` 导出OSS客户端

### 步骤3：配置环境变量
```bash
export OSS_ACCESS_KEY_ID=your_key
export OSS_ACCESS_KEY_SECRET=your_secret
export OSS_BUCKET_NAME=mixcut-renders
```

### 步骤4：测试
1. 生成混剪组合
2. 点击播放/下载
3. 检查视频是否上传到OSS
4. 检查数据库 `file_path` 是否为OSS URL
5. 测试文字快剪功能

## 七、成本估算

以月合成1000个视频为例：

| 项目 | 单价 | 月费用 |
|------|------|--------|
| OSS标准存储（500GB） | ¥0.12/GB | ¥60 |
| 外网流出流量（500GB） | ¥0.8/GB | ¥400 |
| PUT请求（1000次） | ¥0.01/千次 | ¥0.01 |
| GET请求（5000次） | ¥0.01/千次 | ¥0.05 |
| **总计** | | **约 ¥460/月** |

## 八、回退方案

如果OSS上传失败，自动回退到本地模式：
- 保留本地文件
- 数据库仍存储本地路径
- 功能不受影响

## 九、总结

### 改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/utils/oss.py` | 新增 | OSS工具类 |
| `backend/config.py` | 修改 | 添加OSS配置 |
| `backend/routes/renders.py` | 修改 | 合成后上传OSS |
| `backend/requirements.txt` | 修改 | 添加oss2依赖 |
| `backend/utils/__init__.py` | 修改 | 导出oss_client |

### 优势
1. **改动最小**：只修改合成后的上传逻辑
2. **自动回退**：OSS失败时自动使用本地模式
3. **解决痛点**：文字快剪可以直接使用OSS URL
4. **成本可控**：按需付费，无合成时不产生费用
