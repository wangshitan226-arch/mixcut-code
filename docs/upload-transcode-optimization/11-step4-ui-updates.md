# 步骤4: 更新UI显示队列状态

## 修改文件
- `frontend/src/components/EditScreen.tsx`

## 修改内容

### 1. 文件输入支持多选
```tsx
<input
  ref={fileInputRef}
  type="file"
  multiple  // 添加多选支持
  accept="video/*,image/*"
  onChange={handleFileSelect}
  className="hidden"
/>
```

### 2. 添加按钮显示队列状态
```tsx
<button 
  onClick={() => handleAddMaterialClick(shot.id)}
  disabled={currentShotId === shot.id && hasActiveUploads()}
  className="..."
>
  {currentShotId === shot.id && currentUploadItem() ? (
    <>
      {/* 进度条背景 */}
      <div className="absolute inset-0 bg-blue-50 transition-all" 
           style={{ width: `${currentUploadItem()?.progress || 0}%` }} />
      <div className="relative z-10 flex flex-col items-center px-1">
        {/* 当前上传文件名 */}
        <span className="text-[9px] text-blue-600 font-medium truncate w-full text-center">
          {currentUploadItem()?.fileName}
        </span>
        {/* 进度百分比 */}
        <span className="text-[10px] text-blue-600 font-medium">
          {currentUploadItem()?.progress || 0}%
        </span>
        {/* 等待文件数 */}
        {pendingCount() > 0 && (
          <span className="text-[8px] text-blue-500 mt-0.5">
            等待 {pendingCount()} 个
          </span>
        )}
      </div>
    </>
  ) : (
    <>
      <Plus size={20} className="mb-1" />
      <span className="text-[10px]">添加素材</span>
    </>
  )}
</button>
```

### 3. 底部按钮显示上传进度
```tsx
<button 
  onClick={onSynthesize}
  disabled={isLoading || hasTranscodingMaterials || sortedShots.every(s => (s.materials?.length || 0) === 0)}
>
  {isLoading ? (
    <>生成中...</>
  ) : currentUploadItem() ? (
    <>
      <Loader2 size={18} className="animate-spin" />
      上传中 {currentUploadItem()?.progress || 0}%
      {/* 显示队列进度：当前/总数 */}
      {uploadQueue.length > 1 && (
        <span className="text-xs">
          ({uploadQueue.filter(i => i.status === 'completed').length + 1}/{uploadQueue.length})
        </span>
      )}
    </>
  ) : transcodingMaterials.size > 0 ? (
    <>转码中...</>
  ) : (
    '开始合成视频'
  )}
</button>
```

## UI效果

### 场景1：选择3个文件上传
```
┌─────────────────────────┐
│  文件1.mp4              │
│  [=======>     ] 60%    │
│  等待 2 个              │
└─────────────────────────┘
```

### 场景2：底部按钮显示
```
上传中 60% (1/3)
```

### 场景3：上传完成后
- 添加按钮恢复正常
- 新素材显示在列表中
- 底部按钮显示"开始合成视频"

## 用户体验改进

1. **文件名显示**：可以看到当前正在上传哪个文件
2. **进度可视化**：进度条实时更新
3. **队列感知**：知道还有多少个文件在等待
4. **全局进度**：底部按钮显示总体进度 (当前/总数)
