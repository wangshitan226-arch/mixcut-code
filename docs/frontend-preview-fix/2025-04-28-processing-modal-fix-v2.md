# 视频处理进度弹窗修复记录 V2

## 问题描述

### 问题 1: 文字快剪进入后视频加载失败

**现象**：选中未预览的视频，点击文字快剪，显示"视频准备中"弹窗，但进入快剪界面后显示视频加载失败。

**根本原因**：
- 弹窗只等待 `server_video_url`（视频①，服务器FFmpeg高质量视频）准备完成
- 但进入快剪界面还需要 `preview_url`（视频②，浏览器WebCodecs预览视频）
- 如果用户没有预览过，`clientRenderPreview` 需要时间来渲染
- 代码没有等待视频②准备好就进入了界面

**修复方案**：
```typescript
// 同时检查两个视频是否需要准备
const needServerVideo = !serverVideoUrl;
const needClientVideo = !clientVideoUrl || item.preview_status !== 'completed';

if (needServerVideo || needClientVideo) {
  // 显示弹窗
  // 同时启动两个准备流程
  const preparePromises = [];
  
  if (needServerVideo) {
    preparePromises.push(prepareServerVideo());
  }
  
  if (needClientVideo) {
    preparePromises.push(prepareClientVideo());
  }
  
  // 等待两者都完成
  await Promise.all(preparePromises);
  
  // 关闭弹窗，进入界面
}
```

### 问题 2: 下载未预览视频时没有显示弹窗

**现象**：选中未预览的视频，点击下载，没有显示"视频准备中"弹窗。

**根本原因**：
- 下载函数接收的 `item` 参数是从点击事件传来的，可能是旧的引用
- `item.server_video_url` 可能为 undefined，但实际 `results` 数组中已有数据
- 代码先从 `item` 检查，再从 `results` 检查，逻辑混乱

**修复方案**：
```typescript
const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
  // 关键修复：从 results 数组中获取最新数据
  const currentItem = results.find(r => r.id === item.id);
  if (!currentItem) {
    alert('视频数据不存在');
    return;
  }
  
  // 使用 currentItem 而不是 item 进行后续操作
  const downloadUrl = currentItem.server_video_url || currentItem.oss_url;
  
  if (downloadUrl) {
    // 直接下载
  } else {
    // 显示弹窗，准备视频
  }
}, [results, downloadingIds]);
```

## 代码改动详情

### 1. 文字快剪逻辑修复

**文件**: `frontend/src/components/ResultsScreen.tsx`

**函数**: `handleOpenKaipai`

**关键改动**:
- 同时检查 `serverVideoUrl` 和 `clientVideoUrl`
- 如果任一需要准备，显示弹窗
- 使用 `Promise.all` 同时启动两个准备流程
- 等待两者都完成后才关闭弹窗进入界面

```typescript
const needServerVideo = !serverVideoUrl;
const needClientVideo = !clientVideoUrl || item.preview_status !== 'completed';

if (needServerVideo || needClientVideo) {
  setProcessingModal({...});
  
  const preparePromises: Promise<void>[] = [];
  
  if (needServerVideo) {
    preparePromises.push(
      new Promise<void>(async (resolve, reject) => {
        // 准备服务器视频...
      })
    );
  }
  
  if (needClientVideo) {
    preparePromises.push(
      new Promise<void>(async (resolve) => {
        // 准备客户端视频...
      })
    );
  }
  
  await Promise.all(preparePromises);
  
  // 如果客户端视频失败，降级使用服务器视频
  if (!clientVideoUrl && serverVideoUrl) {
    clientVideoUrl = serverVideoUrl;
  }
  
  setProcessingModal(prev => ({ ...prev, isOpen: false }));
}
```

### 2. 下载逻辑修复

**文件**: `frontend/src/components/ResultsScreen.tsx`

**函数**: `handleDownload`

**关键改动**:
- 首先从 `results` 数组获取最新数据
- 统一检查 `server_video_url` 和 `oss_url`
- 简化逻辑，避免重复代码

```typescript
const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
  // 关键修复：从 results 数组中获取最新数据
  const currentItem = results.find(r => r.id === item.id);
  if (!currentItem) {
    alert('视频数据不存在');
    return;
  }
  
  // 检查是否有OSS URL
  const downloadUrl = currentItem.server_video_url || currentItem.oss_url;
  
  if (downloadUrl) {
    // 显示下载中弹窗，直接下载
  } else {
    // 显示视频准备中弹窗，调用后端接口
  }
}, [results, downloadingIds]);
```

## 修复效果

### 文字快剪流程（修复后）

```
用户点击文字快剪
    ↓
检查视频①（server_video_url）和视频②（preview_url）
    ↓
两者都已准备好 → 直接进入快剪界面
    ↓
任一未准备好 → 显示"视频准备中"弹窗
    ↓
同时启动：
  - 服务器渲染（视频①）
  - 客户端渲染（视频②）
    ↓
等待两者都完成
    ↓
关闭弹窗 → 进入快剪界面（两个视频都已准备好）
```

### 下载流程（修复后）

```
用户点击下载
    ↓
从 results 获取最新数据
    ↓
检查是否有OSS URL
    ↓
有 → 显示"视频下载中"弹窗 → 下载 → 关闭弹窗
    ↓
无 → 显示"视频准备中"弹窗 → 调用后端 → 轮询 → 下载 → 关闭弹窗
```

## 关键修复点

| 问题 | 修复前 | 修复后 |
|------|--------|--------|
| 文字快剪视频②未准备好 | 只等待视频① | 同时等待视频①和视频② |
| 下载弹窗不显示 | 使用旧 item 引用 | 从 results 获取最新数据 |
| 代码重复 | 分两次检查 server_video_url 和 oss_url | 统一检查 |

## 相关文件

- `frontend/src/components/ResultsScreen.tsx` - 修改下载和快剪逻辑

## 修复日期

2025-04-28
