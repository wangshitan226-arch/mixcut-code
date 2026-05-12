# MixCut 视频混剪系统架构方案

## 1. 项目概述

MixCut 是一个视频智能混剪工具，用户上传素材到多个镜头，系统生成大量不同的排列组合视频（1000+条）。

### 核心特点
- 多镜头素材管理
- 自动生成排列组合（1000+种）
- 实时 FFmpeg 合成（按需）
- 缩略图预览 + 延迟加载视频

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端（浏览器）                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  IndexedDB 缓存层（~30MB）                                           │   │
│  │  • 视频缩略图（WebP，每张10-30KB）                                    │   │
│  │  • 视频元数据（ID、时长、标签、排列组合信息）                           │   │
│  │  • 镜头-素材映射关系                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  不缓存（实时获取）                                                   │   │
│  │  • 原始视频素材（太大）                                               │   │
│  │  • 合成后的完整视频（按需生成）                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
                              HTTP API / WebSocket
                                      ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                              服务端（Flask）                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  本地存储（服务器磁盘）                                               │   │
│  │  /uploads/                                                          │   │
│  │    ├── materials/        ← 原始素材（视频/图片）                      │   │
│  │    ├── thumbnails/       ← 缩略图（快速访问）                         │   │
│  │    └── temp/             ← 临时合成文件（定期清理）                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  FFmpeg 合成引擎（按需触发）                                          │   │
│  │  • 接收排列组合参数（镜头顺序、素材选择）                              │   │
│  │  • 实时合成视频                                                      │   │
│  │  • 输出到临时目录或直传OSS                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  数据库（SQLite/PostgreSQL）                                          │   │
│  │  • projects: 项目信息                                                │   │
│  │  • shots: 镜头定义                                                   │   │
│  │  • materials: 素材信息                                               │   │
│  │  • combinations: 排列组合规则（不存视频，只存规则）                     │   │
│  │  • renders: 渲染记录（谁下载过，URL是什么）                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
                            可选：阿里云OSS（长期存储）
```

---

## 3. 数据模型

### 3.1 数据库表结构

```sql
-- 项目表
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, ready, archived
    total_combinations INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 镜头表
CREATE TABLE shots (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    sequence INTEGER NOT NULL,  -- 镜头顺序
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 素材表
CREATE TABLE materials (
    id VARCHAR(36) PRIMARY KEY,
    shot_id INTEGER NOT NULL,
    type VARCHAR(20) NOT NULL,  -- video, image
    original_name VARCHAR(255),
    file_path VARCHAR(500) NOT NULL,      -- 服务器本地路径
    thumbnail_path VARCHAR(500) NOT NULL, -- 缩略图路径
    duration FLOAT,  -- 视频时长（秒）
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shot_id) REFERENCES shots(id)
);

-- 排列组合表（只存规则，不存视频）
CREATE TABLE combinations (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id INTEGER NOT NULL,
    combination_index INTEGER NOT NULL,  -- 第N种组合（0-999）
    material_sequence TEXT NOT NULL,     -- JSON: ["mat_id_1", "mat_id_2", ...]
    tag VARCHAR(50),                     -- 完全不重复、极低重复率、普通
    is_favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 渲染记录表（谁下载过，URL是什么）
CREATE TABLE renders (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    combination_id INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    file_path VARCHAR(500),                -- 本地路径或OSS URL
    file_size INTEGER,
    duration FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (combination_id) REFERENCES combinations(id)
);
```

### 3.2 排列组合生成算法

```python
# 示例：3个镜头，每个镜头有若干素材
shots = {
    1: [mat_a1, mat_a2, mat_a3],  # 镜头1：3个素材
    2: [mat_b1, mat_b2],          # 镜头2：2个素材
    3: [mat_c1, mat_c2, mat_c3]   # 镜头3：3个素材
}

# 总组合数 = 3 × 2 × 3 = 18种
# 实际项目中可能是 10镜头 × 5素材 = 9765625种
# 需要限制生成数量（如前1000种）

def generate_combinations(shots, limit=1000):
    """生成排列组合"""
    from itertools import product
    
    shot_ids = sorted(shots.keys())
    material_lists = [shots[sid] for sid in shot_ids]
    
    combinations = []
    for idx, combo in enumerate(product(*material_lists)):
        if idx >= limit:
            break
        combinations.append({
            'index': idx,
            'materials': list(combo),
            'tag': calculate_uniqueness_tag(combo)  # 计算重复率标签
        })
    
    return combinations
```

---

## 4. API 设计

### 4.1 核心接口

```python
# 1. 获取排列组合列表（带缩略图）
GET /api/projects/{project_id}/combinations?page=1&limit=20
Response: {
    "total": 1000,
    "page": 1,
    "combinations": [
        {
            "id": 1,
            "index": 0,
            "tag": "完全不重复",
            "duration": "01:23",
            "thumbnails": ["/thumbs/mat1.jpg", "/thumbs/mat2.jpg", ...],
            "material_ids": ["uuid-1", "uuid-2", ...]
        }
    ]
}

# 2. 预览视频（实时合成低码率版本）
POST /api/combinations/{combo_id}/preview
Body: {"quality": "low"}  # low: 480p, medium: 720p
Response: {
    "task_id": "task-123",
    "status": "processing"
}

# 3. 查询合成进度
GET /api/tasks/{task_id}/status
Response: {
    "status": "processing",  # pending, processing, completed, failed
    "progress": 65,  # 百分比
    "preview_url": null  # 完成后返回临时URL
}

# 4. 下载视频（合成高清版本）
POST /api/combinations/{combo_id}/render
Body: {"quality": "high"}  # high: 1080p
Response: {
    "task_id": "task-456",
    "status": "processing"
}

# 5. 获取下载链接
GET /api/renders/{render_id}/download
Response: {
    "url": "https://oss.example.com/video.mp4?signature=xxx",
    "expires_at": "2024-01-01T12:00:00Z"
}
```

### 4.2 缩略图优化接口

```python
# 批量获取缩略图（支持HTTP/2多路复用）
GET /api/thumbnails/batch?ids=uuid1,uuid2,uuid3
Response: {
    "thumbnails": [
        {"id": "uuid1", "url": "/thumbs/uuid1.webp", "width": 300, "height": 400},
        ...
    ]
}

# 缩略图支持 WebP 格式（体积减少30-50%）
GET /thumbnails/{id}.webp
```

---

## 5. 客户端缓存策略

### 5.1 IndexedDB 结构

```javascript
// 使用 idb 库
const db = await openDB('MixCutDB', 1, {
  upgrade(db) {
    // 缩略图表
    const thumbStore = db.createObjectStore('thumbnails', { keyPath: 'id' });
    thumbStore.createIndex('projectId', 'projectId');
    thumbStore.createIndex('timestamp', 'timestamp');
    
    // 组合元数据表
    const comboStore = db.createObjectStore('combinations', { keyPath: 'id' });
    comboStore.createIndex('projectId', 'projectId');
    comboStore.createIndex('tag', 'tag');
    
    // 素材映射表
    db.createObjectStore('materials', { keyPath: 'id' });
  }
});

// 缓存策略
const CACHE_CONFIG = {
  maxThumbnails: 2000,        // 最多缓存2000张缩略图
  maxAge: 7 * 24 * 60 * 60 * 1000,  // 7天过期
  thumbnailQuality: 0.8,      // WebP质量
  maxThumbnailSize: 50 * 1024 // 单张最大50KB
};
```

### 5.2 缓存清理策略

```javascript
// LRU 清理
async function cleanupCache() {
  const thumbs = await db.getAll('thumbnails');
  
  // 按时间排序，删除最旧的
  thumbs.sort((a, b) => a.timestamp - b.timestamp);
  
  const totalSize = thumbs.reduce((sum, t) => sum + (t.blob?.size || 0), 0);
  const maxSize = 30 * 1024 * 1024; // 30MB
  
  if (totalSize > maxSize) {
    let currentSize = totalSize;
    for (const thumb of thumbs) {
      if (currentSize <= maxSize * 0.8) break;
      await db.delete('thumbnails', thumb.id);
      currentSize -= thumb.blob?.size || 0;
    }
  }
}
```

---

## 6. FFmpeg 合成策略

### 6.1 实时合成流程

```python
import subprocess
import tempfile
import os

def render_combination(material_paths, output_path, quality='medium'):
    """
    合成视频
    quality: low (480p), medium (720p), high (1080p)
    """
    # 质量参数
    quality_settings = {
        'low': {'scale': '854:480', 'crf': '28', 'preset': 'superfast'},
        'medium': {'scale': '1280:720', 'crf': '23', 'preset': 'veryfast'},
        'high': {'scale': '1920:1080', 'crf': '18', 'preset': 'medium'}
    }
    
    settings = quality_settings[quality]
    
    # 创建 concat 文件列表
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for path in material_paths:
            # 统一转换为相同格式（如果需要）
            f.write(f"file '{path}'\n")
        concat_file = f.name
    
    try:
        # FFmpeg 合成命令
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-vf', f'scale={settings["scale"]}:force_original_aspect_ratio=decrease,pad={settings["scale"].replace(":", ":")}:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264',
            '-crf', settings['crf'],
            '-preset', settings['preset'],
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',  # 支持流式播放
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
    finally:
        os.unlink(concat_file)
    
    return output_path
```

### 6.2 异步任务队列

```python
from celery import Celery
import redis

# 使用 Celery + Redis 处理合成任务
celery_app = Celery('mixcut', broker='redis://localhost:6379/0')

@celery_app.task
def render_video_task(combination_id, quality='medium'):
    """异步合成视频"""
    # 1. 查询组合信息
    combo = db.get_combination(combination_id)
    materials = db.get_materials(combo.material_ids)
    
    # 2. 更新状态为处理中
    render = db.create_render(combination_id, quality)
    
    try:
        # 3. 执行合成
        output_path = f"/tmp/renders/{render.id}.mp4"
        material_paths = [m.file_path for m in materials]
        
        render_combination(material_paths, output_path, quality)
        
        # 4. 上传到OSS（可选）
        if USE_OSS:
            oss_url = upload_to_oss(output_path)
            render.file_path = oss_url
        else:
            render.file_path = output_path
        
        render.status = 'completed'
        render.file_size = os.path.getsize(output_path)
        
    except Exception as e:
        render.status = 'failed'
        render.error = str(e)
    
    db.save(render)
    return render.id
```

---

## 7. 成本优化策略

### 7.1 存储分层

| 数据类型 | 存储位置 | 保留时间 | 预估成本 |
|---------|---------|---------|---------|
| 原始素材 | 服务器本地 | 项目期间 | ¥0（磁盘成本） |
| 缩略图 | 服务器本地 + 浏览器缓存 | 项目期间 | ¥0 |
| 预览视频（480p） | 服务器本地临时 | 7天 | ¥0 |
| 合成视频（1080p） | 按需生成，可选OSS | 用户下载后删除 | 极低 |

### 7.2 流量优化

```
用户浏览列表
    ↓
加载缩略图（从浏览器缓存或服务器）
    ↓ 点击预览
实时合成 480p 预览版（服务器本地）
    ↓ 确认下载
实时合成 1080p 高清版
    ↓
用户下载到本地
    ↓
可选：删除服务器上的合成文件
```

### 7.3 与纯OSS方案对比

| 方案 | 存储成本 | 流量成本 | 适用场景 |
|-----|---------|---------|---------|
| 纯OSS预存1000个视频 | ¥12/月 + 流量费 | ¥80-240/月 | 高频访问 |
| 本方案（按需合成） | ¥0-5/月 | ¥0-20/月 | 低频/不确定访问 |
| 节省比例 | ~95% | ~90% | - |

---

## 8. 实现路线图

### Phase 1: 基础功能（1-2周）
- [ ] 数据库模型实现
- [ ] 排列组合生成算法
- [ ] 基础API接口
- [ ] 缩略图生成与缓存

### Phase 2: 核心功能（2-3周）
- [ ] FFmpeg 实时合成
- [ ] 预览功能（480p）
- [ ] 下载功能（1080p）
- [ ] 异步任务队列

### Phase 3: 优化（1-2周）
- [ ] 浏览器 IndexedDB 缓存
- [ ] 进度实时推送（WebSocket）
- [ ] 视频压缩优化
- [ ] 可选OSS集成

---

## 9. 关键代码示例

### 9.1 前端：缩略图懒加载

```tsx
// ResultsScreen.tsx 优化版
import { useEffect, useState, useRef } from 'react';
import { openDB } from 'idb';

const DB_NAME = 'MixCutDB';
const THUMB_STORE = 'thumbnails';

export default function ResultsScreen({ projectId }) {
  const [combinations, setCombinations] = useState([]);
  const [loading, setLoading] = useState(false);
  const observerRef = useRef<IntersectionObserver>();
  
  // 初始化数据库
  useEffect(() => {
    const initDB = async () => {
      const db = await openDB(DB_NAME, 1, {
        upgrade(db) {
          if (!db.objectStoreNames.contains(THUMB_STORE)) {
            db.createObjectStore(THUMB_STORE, { keyPath: 'id' });
          }
        }
      });
      return db;
    };
    initDB();
  }, []);
  
  // 获取缩略图（优先从缓存）
  const getThumbnail = async (comboId: string, urls: string[]) => {
    const db = await openDB(DB_NAME, 1);
    const cached = await db.get(THUMB_STORE, comboId);
    
    if (cached && Date.now() - cached.timestamp < 7 * 24 * 60 * 60 * 1000) {
      return URL.createObjectURL(cached.blob);
    }
    
    // 从服务器获取
    const response = await fetch(`/api/combinations/${comboId}/thumbnail`);
    const blob = await response.blob();
    
    // 缓存到 IndexedDB
    await db.put(THUMB_STORE, {
      id: comboId,
      blob,
      timestamp: Date.now()
    });
    
    return URL.createObjectURL(blob);
  };
  
  // 懒加载 + 虚拟滚动
  const renderItem = (combo: Combination) => (
    <div 
      key={combo.id}
      className="relative aspect-[3/4] bg-gray-200 rounded-lg overflow-hidden"
      data-combo-id={combo.id}
    >
      <LazyThumbnail combo={combo} />
      {/* 选中、标签、时长等UI */}
    </div>
  );
  
  return (
    <div className="grid grid-cols-2 gap-3">
      {combinations.map(renderItem)}
    </div>
  );
}

// 懒加载缩略图组件
function LazyThumbnail({ combo }) {
  const [src, setSrc] = useState('/placeholder.jpg');
  const imgRef = useRef<HTMLImageElement>(null);
  
  useEffect(() => {
    const observer = new IntersectionObserver(
      async (entries) => {
        if (entries[0].isIntersecting) {
          const url = await getThumbnail(combo.id, combo.thumbnails);
          setSrc(url);
          observer.disconnect();
        }
      },
      { rootMargin: '50px' }
    );
    
    if (imgRef.current) {
      observer.observe(imgRef.current);
    }
    
    return () => observer.disconnect();
  }, [combo.id]);
  
  return <img ref={imgRef} src={src} className="w-full h-full object-cover" />;
}
```

### 9.2 后端：合成任务管理

```python
# tasks.py
from celery import Celery
from flask import Flask
import ffmpeg
import os

app = Flask(__name__)
celery = Celery(app.name, broker='redis://localhost:6379/0')

@celery.task(bind=True)
def render_combination_task(self, combination_id, quality='medium'):
    """Celery 异步任务"""
    try:
        # 更新进度
        self.update_state(state='PROGRESS', meta={'progress': 0})
        
        # 获取组合信息
        combo = Combination.query.get(combination_id)
        materials = Material.query.filter(
            Material.id.in_(combo.material_ids)
        ).all()
        
        # 创建输出目录
        output_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'renders')
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f'{combination_id}_{quality}.mp4')
        
        # 构建 FFmpeg 输入
        inputs = []
        for mat in materials:
            inputs.append(ffmpeg.input(mat.file_path))
        
        # 设置质量参数
        settings = {
            'low': {'vf': 'scale=854:480', 'crf': 28},
            'medium': {'vf': 'scale=1280:720', 'crf': 23},
            'high': {'vf': 'scale=1920:1080', 'crf': 18}
        }[quality]
        
        # 执行合成
        self.update_state(state='PROGRESS', meta={'progress': 30})
        
        (
            ffmpeg
            .concat(*inputs, v=1, a=1)
            .filter('scale', 1280, 720)
            .output(
                output_path,
                vcodec='libx264',
                acodec='aac',
                crf=settings['crf'],
                preset='fast',
                movflags='faststart'
            )
            .run(quiet=True)
        )
        
        self.update_state(state='PROGRESS', meta={'progress': 90})
        
        # 保存记录
        render = Render(
            combination_id=combination_id,
            quality=quality,
            file_path=output_path,
            file_size=os.path.getsize(output_path),
            status='completed'
        )
        db.session.add(render)
        db.session.commit()
        
        return {'status': 'completed', 'render_id': render.id}
        
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
```

---

## 10. 部署建议

### 服务器配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: ./backend
    ports:
      - "3002:3002"
    volumes:
      - ./uploads:/app/uploads
      - ./renders:/app/renders
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=sqlite:///app/mixcut.db
    depends_on:
      - redis
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
  
  worker:
    build: ./backend
    command: celery -A tasks worker --loglevel=info --concurrency=2
    volumes:
      - ./uploads:/app/uploads
      - ./renders:/app/renders
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  redis_data:
```

### 硬件建议

| 场景 | CPU | 内存 | 存储 | 预估价格 |
|-----|-----|-----|------|---------|
| 开发测试 | 4核 | 8GB | 100GB SSD | ¥200/月 |
| 小规模（100组合/天） | 8核 | 16GB | 500GB SSD | ¥500/月 |
| 中规模（1000组合/天） | 16核 | 32GB | 2TB SSD | ¥1200/月 |

---

## 11. 总结

### 核心优势

1. **存储成本极低**：不预存视频，按需合成
2. **流量成本可控**：缩略图本地缓存，视频按需生成
3. **用户体验良好**：列表浏览流畅，预览/下载可接受延迟
4. **扩展性强**：可水平扩展 worker 节点

### 关键决策

| 决策点 | 选择 | 理由 |
|-------|-----|-----|
| 视频存储 | 服务器本地 + 可选OSS | 成本低，合成速度快 |
| 缩略图 | 浏览器 IndexedDB 缓存 | 减少服务器压力 |
| 合成时机 | 用户点击时实时合成 | 避免无效合成 |
| 任务队列 | Celery + Redis | 可靠，易扩展 |

---

*文档版本: 1.0*  
*更新日期: 2026-04-15*
