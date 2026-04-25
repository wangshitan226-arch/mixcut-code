# 文字快剪客户端渲染最小改动集成记录

## 日期
2026-04-25

## 背景
用户反馈之前对文字快剪的客户端渲染集成方式错误：
- 错误地在删除片段时触发OSS上传
- 错误地在导出时重写客户端裁剪逻辑
- 用户强调：服务器路径已经走通，不要重写已有逻辑

## 服务器路径流程（已走通）
1. `create_kaipai_edit` → 需要 `render.oss_url`（原始视频URL）
2. `start_transcription` → 需要 `edit.original_video_url` 进行ASR
3. 用户删除片段 → 只记录 `removed_segments` 到 `edit_params`
4. `export_video`（导出）→ 读取 `removed_segments` + `original_video_url` → 提交ICE渲染或FFmpeg拼接

## 问题核心
当使用客户端渲染时，混剪结果只存在于浏览器本地（Blob URL），没有 `render.oss_url`，导致：
- 无法创建文字快剪草稿（`create_kaipai_edit` 检查 `render.oss_url`）
- 无法进行ASR（`start_transcription` 需要 `video_url`）

## 最小改动方案

### 改动1：后端 `create_kaipai_edit` 接口
**文件**: `backend/routes/kaipai.py`

允许前端传入 `video_url` 参数来覆盖 `render.oss_url`：

```python
# 检查是否有OSS URL
video_url = render.oss_url

# 允许前端传入video_url（客户端渲染场景）
if not video_url:
    video_url = data.get('video_url')

if not video_url:
    return jsonify({'error': '视频尚未上传到OSS，请稍后再试', 'code': 'NO_OSS_URL'}), 400
```

### 改动2：前端 `ResultsScreen` 点击文字快剪时上传OSS
**文件**: `frontend/src/components/ResultsScreen.tsx`

在 `handleOpenKaipai` 中：
1. 检测视频URL是否是 Blob URL（客户端渲染）
2. 如果是，fetch Blob 并使用 `uploadToOSSDirect` 上传到OSS
3. 调用 `/api/renders/${item.id}/kaipai/edit` 时传入 `video_url` 参数

```typescript
// 如果是客户端渲染的Blob URL，需要先上传到OSS
if (videoUrl && videoUrl.startsWith('blob:')) {
  const response = await fetch(videoUrl);
  const blob = await response.blob();
  const uploadResult = await uploadToOSSDirect(blob, filename, userId);
  finalVideoUrl = uploadResult.url;
}

// 创建 KaipaiEdit 任务
const response = await fetch(`${API_BASE_URL}/api/renders/${item.id}/kaipai/edit`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    video_url: finalVideoUrl // 传入OSS URL（客户端渲染场景）
  })
});
```

### 改动3：删除 `KaipaiEditor` 中错误添加的代码
**文件**: `frontend/src/components/KaipaiEditor/index.tsx`

删除以下内容：
- `autoUploadToOSS` 函数（错误地在删除时上传）
- `clientExportVideo` 函数（重写了导出逻辑）
- `exportVideo` 中的客户端导出逻辑（导出时应调用服务器接口）
- `getVideoDurationFromBlob` 函数
- 相关未使用的 import（`exportCombination`, `loadMaterial`, `loadMaterialFromIndexedDB`, `trimVideo`, `calculateKeepRanges`, `uploadClientRender`）

保留：
- `exportVideo` 只调用原有的 `/api/kaipai/${editId}/export` 服务器接口
- 删除片段只记录到后端，不触发上传
- 视频缓存逻辑（`cacheVideoToLocal`）

## 验证
- 前端构建成功
- 文字快剪流程：
  1. 客户端渲染生成混剪结果 → Blob URL
  2. 点击"文字快剪" → 检测Blob URL → 上传OSS → 获取OSS URL
  3. 创建文字快剪草稿 → ASR语音识别 → 显示片段
  4. 删除片段 → 只记录时间戳到后端
  5. 导出 → 调用服务器 `/api/kaipai/${editId}/export` → ICE渲染或FFmpeg拼接

## 关键原则
- **不要重写已有逻辑**：服务器路径已经走通，只添加必要的桥接代码
- **最小改动**：只在关键节点（创建草稿前）添加OSS上传
- **保持原有流程**：删除、导出等操作完全保持原有服务器逻辑
