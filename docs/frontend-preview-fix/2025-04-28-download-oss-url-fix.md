# 视频下载功能修复记录 - 强制使用OSS URL

## 问题描述

点击下载选中按钮时报错：
```
Access to fetch at 'http://localhost:3002/renders/combo_xxx.mp4' 
from origin 'http://localhost:3000' has been blocked by CORS policy
```

## 根本原因

1. **前端直接使用服务器本地文件路径下载**：`http://localhost:3002/renders/xxx.mp4`
2. **CORS跨域问题**：前端运行在3000端口，后端在3002端口
3. **架构设计问题**：
   - 客户端浏览器渲染的视频仅用于快速预览（效果差）
   - 下载必须使用服务器FFmpeg渲染的高质量视频
   - 服务器本地文件不应该直接暴露给公网下载

## 修复方案

### 核心原则

| 场景 | 视频来源 | 质量 | URL类型 |
|------|----------|------|---------|
| **预览** | 客户端Blob URL 或 服务器本地文件 | 差/中 | Blob URL / 本地路径 |
| **下载** | 服务器FFmpeg + OSS | 好 | 公网OSS URL |
| **ASR/剪辑** | 服务器FFmpeg + OSS | 好 | 公网OSS URL |

### 下载流程

```
用户点击下载
    ↓
前端检查是否有 server_video_url（服务器FFmpeg高质量视频）
    ↓
有 → 直接下载（公网URL，无CORS问题）
    ↓
无 → 检查是否有 oss_url（普通OSS URL）
    ↓
有 → 直接下载
    ↓
无 → 调用后端 /api/combinations/{id}/download 接口
    ↓
后端启动服务器渲染+上传OSS任务
    ↓
返回 processing 状态，提示用户稍后再试
```

## 代码修改

### 1. 后端接口修改

**文件**: `backend/routes/renders.py`

**接口**: `POST /api/combinations/<combo_id>/download`

**修改前**:
```python
# 优先使用OSS URL
if render.oss_url:
    return jsonify({'video_url': render.oss_url})

# 如果没有OSS URL，使用本地文件
if render.file_path:
    return jsonify({'video_url': f'/renders/{output_filename}'})  # 导致CORS错误
```

**修改后**:
```python
# 优先级1: server_video_url（服务器FFmpeg高质量视频URL）
if render.server_video_url:
    return jsonify({
        'status': 'completed',
        'video_url': render.server_video_url,
        'source': 'server_oss'
    })

# 优先级2: oss_url（普通OSS URL）
if render.oss_url:
    return jsonify({
        'status': 'completed',
        'video_url': render.oss_url,
        'source': 'oss'
    })

# 优先级3: 触发服务器渲染+上传OSS
# 检查是否已经在处理中
for task_id, task in render_tasks.items():
    if task.get('combo_id') == combo_id:
        if task['status'] == 'processing':
            return jsonify({
                'status': 'processing',
                'message': '视频正在准备中，请稍后再试'
            })

# 启动服务器渲染任务
# ... 启动 server_concat_task

return jsonify({
    'status': 'processing',
    'message': '视频正在准备中，请稍后再试'
})
```

### 2. 前端下载逻辑修改

**文件**: `frontend/src/components/ResultsScreen.tsx`

**函数**: `handleDownload`

**修改前**:
```typescript
const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
  // 优先尝试客户端导出
  if (clientRenderState.isEnabled) {
    const blob = await clientExportVideo(item);
    // ... 下载blob
  }

  let videoUrl = item.preview_url;
  
  // 使用本地路径下载（导致CORS错误）
  const fullUrl = videoUrl.startsWith('http') ? videoUrl : `${API_BASE_URL}${videoUrl}`;
  await downloadVideo(fullUrl, filename);
}, []);
```

**修改后**:
```typescript
const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
  // 检查是否已经在下载中
  if (downloadingIds.has(item.id)) {
    return;
  }

  setDownloadingIds(prev => new Set(prev).add(item.id));

  try {
    // 优先级1: 检查是否已有 server_video_url
    if (item.server_video_url) {
      await downloadVideo(item.server_video_url, filename);
      return;
    }

    // 优先级2: 检查是否已有 oss_url
    const ossUrl = currentItem?.oss_url;
    if (ossUrl) {
      await downloadVideo(ossUrl, filename);
      return;
    }

    // 优先级3: 调用后端下载接口
    const response = await fetch(`${API_BASE_URL}/api/combinations/${item.id}/download`, {
      method: 'POST'
    });
    const data = await response.json();

    if (data.status === 'completed') {
      await downloadVideo(data.video_url, filename);
      // 更新本地状态，缓存OSS URL
      setResults(prev => prev.map(r =>
        r.id === item.id ? { ...r, server_video_url: data.video_url } : r
      ));
    } else if (data.status === 'processing') {
      alert('视频正在准备中，请稍后再试');
    }
  } finally {
    setDownloadingIds(prev => {
      const newSet = new Set(prev);
      newSet.delete(item.id);
      return newSet;
    });
  }
}, [results, downloadingIds]);
```

### 3. 批量下载逻辑修改

**文件**: `frontend/src/components/ResultsScreen.tsx`

**函数**: `handleBatchDownload`

**修改内容**:
- 同样强制使用OSS URL下载
- 跳过正在处理中的视频
- 提供下载结果统计

## 关键改动点

### 后端

1. **`/api/combinations/<combo_id>/download` 接口**
   - 不再返回本地文件路径
   - 只返回OSS URL（`server_video_url` 或 `oss_url`）
   - 无OSS URL时触发服务器渲染任务

### 前端

1. **`handleDownload` 函数**
   - 移除客户端导出逻辑（不再用于下载）
   - 优先级：`server_video_url` > `oss_url` > 调用后端接口
   - 添加下载状态锁定

2. **`handleBatchDownload` 函数**
   - 同样强制使用OSS URL
   - 添加下载统计和结果反馈

## 数据模型

**`Render` 模型的相关字段**:

```python
class Render(db.Model):
    file_path = db.Column(db.String(500))      # 本地文件路径（仅用于预览）
    oss_url = db.Column(db.String(500))        # OSS URL（普通质量）
    server_video_url = db.Column(db.String(500))  # 服务器FFmpeg高质量视频URL
    server_video_status = db.Column(db.String(20))  # pending, processing, completed, failed
```

## 验证方法

1. 打开作品结果界面
2. 点击单个视频下载按钮
3. 验证：
   - 如果已有OSS URL，直接下载
   - 如果没有OSS URL，提示"视频正在准备中"
4. 检查控制台日志，确认使用的是OSS URL
5. 批量下载时，验证跳过正在准备中的视频

## 预期效果

- ✅ 下载始终使用服务器FFmpeg渲染的高质量视频
- ✅ 无CORS跨域问题
- ✅ 生产环境可正常工作
- ✅ 用户有明确的状态反馈

## 修复日期

2025-04-28

## 相关文件

- `backend/routes/renders.py` - 后端下载接口
- `frontend/src/components/ResultsScreen.tsx` - 前端下载逻辑
