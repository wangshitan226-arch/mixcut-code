# 优化步骤4: 添加转码失败处理

## 修改文件
- `frontend/src/components/EditScreen.tsx`
- `backend/routes/upload.py`

## 修改内容

### 1. 前端：素材卡片添加重试按钮

当素材转码失败时，在素材卡片上显示：
- 红色遮罩层（透明度30%）
- 错误图标
- "转码失败"文字
- **重试按钮**（红色背景，带刷新图标）

```typescript
{isTranscodeFailed && (
  <div className="absolute inset-0 bg-red-500/30 flex flex-col items-center justify-center">
    <AlertCircle size={20} className="text-red-600 mb-1" />
    <span className="text-[9px] text-red-700 font-medium bg-white/90 px-1.5 py-0.5 rounded mb-1">
      转码失败
    </span>
    <button
      onClick={(e) => {
        e.stopPropagation();
        handleRetryTranscode(material);
      }}
      className="flex items-center gap-0.5 px-2 py-0.5 bg-red-600 text-white text-[9px] rounded-full"
    >
      <RefreshCw size={8} />
      重试
    </button>
  </div>
)}
```

### 2. 前端：添加重试处理函数

```typescript
const handleRetryTranscode = async (material: Material) => {
  if (!material.transcode_task_id) {
    alert('该素材没有转码任务ID，无法重试');
    return;
  }

  // 从失败集合中移除，添加到转码集合
  setTranscodeFailedMaterials(prev => {
    const newSet = new Set(prev);
    newSet.delete(material.id);
    return newSet;
  });
  setTranscodingMaterials(prev => new Set(prev).add(material.id));

  try {
    // 调用后端重试接口
    const response = await fetch(`${API_BASE_URL}/api/transcode/${material.transcode_task_id}/retry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (response.ok) {
      // 开始检查转码状态
      setTimeout(() => {
        checkTranscodeStatusImmediately(material.transcode_task_id!, material.id);
      }, 100);
    } else {
      // 恢复失败状态
      setTranscodingMaterials(prev => {
        const newSet = new Set(prev);
        newSet.delete(material.id);
        return newSet;
      });
      setTranscodeFailedMaterials(prev => new Set(prev).add(material.id));
    }
  } catch (error) {
    // 恢复失败状态
    // ...
  }
};
```

### 3. 后端：添加重试转码接口

```python
@upload_bp.route('/transcode/<task_id>/retry', methods=['POST'])
def retry_transcode(task_id):
    """重试转码任务"""
    # 获取素材信息
    material_id = task_id.replace('transcode_', '')
    material = Material.query.get(material_id)
    
    if not material:
        return jsonify({'error': '素材不存在'}), 404
    
    # 检查原始文件是否存在
    if not os.path.exists(material.file_path):
        return jsonify({'error': '原始文件不存在，无法重试'}), 400
    
    # 清除之前的失败状态
    if task_id in transcode_tasks:
        del transcode_tasks[task_id]
    
    # 清除无效的unified_path
    if material.unified_path and not os.path.exists(material.unified_path):
        material.unified_path = None
        db.session.commit()
    
    # 启动新的转码任务
    unified_filename = f"{material_id}_unified.mp4"
    unified_path = os.path.join(UNIFIED_FOLDER, unified_filename)
    
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=async_transcode_task,
        args=(task_id, material_id, material.file_path, unified_path, 'medium', app, material.user_id)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'processing',
        'message': '转码任务已重新启动'
    })
```

## 用户体验改进

1. **错误可恢复**: 用户不再需要删除重传，可以直接重试转码
2. **即时反馈**: 点击重试后立即看到状态变化（从失败变为处理中）
3. **保留素材**: 重试时保留素材的其他信息（缩略图、时长等）
4. **后端容错**: 后端会检查原始文件是否存在，避免无效重试
