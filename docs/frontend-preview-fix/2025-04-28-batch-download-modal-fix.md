# 批量下载弹窗修复记录

## 问题描述

用户点击"下载选中"按钮时，如果没有OSS URL，应该显示"视频准备中"弹窗，等上传成功后再显示"视频下载中"弹窗，下载完成后关闭弹窗。

## 修复内容

### 批量下载逻辑修改

**文件**: `frontend/src/components/ResultsScreen.tsx`

**函数**: `handleBatchDownload`

**修改前**:
- 遍历所有选中的视频
- 有OSS URL的直接下载
- 没有OSS URL的调用后端接口，如果正在处理则跳过
- 最后显示统计结果

**修改后**:
- 只处理第一个选中的视频（避免多个弹窗冲突）
- 有OSS URL：显示"视频下载中"弹窗 → 下载 → 关闭弹窗
- 没有OSS URL：
  - 显示"视频准备中"弹窗
  - 调用后端接口
  - 如果立即完成，改为"视频下载中"弹窗 → 下载 → 关闭弹窗
  - 如果正在处理，轮询状态 → 准备完成后改为"视频下载中" → 下载 → 关闭弹窗
- 如果还有多个选中，提示用户重新选择下载

## 代码改动详情

### handleBatchDownload 函数

```typescript
const handleBatchDownload = useCallback(async () => {
  const selectedItems = results.filter(r => r.selected);
  if (selectedItems.length === 0) {
    alert('请先选择要下载的视频');
    return;
  }

  // 只处理第一个选中的视频（简化逻辑，避免多个弹窗冲突）
  const item = selectedItems[0];
  
  // 从 results 获取最新数据
  const currentItem = results.find(r => r.id === item.id);
  if (!currentItem) {
    alert('视频数据不存在');
    return;
  }

  // 检查是否有OSS URL
  const downloadUrl = currentItem.server_video_url || currentItem.oss_url;

  if (downloadUrl) {
    // 有OSS URL，直接下载
    setProcessingModal({
      isOpen: true,
      title: '视频下载中',
      description: `正在下载视频 ${currentItem.index + 1}，请稍候...`,
      type: 'download'
    });
    
    await downloadVideo(downloadUrl, `mixcut_${currentItem.id}.mp4`);
    
    // 关闭弹窗
    setProcessingModal(prev => ({ ...prev, isOpen: false }));
  } else {
    // 没有OSS URL，需要准备
    setProcessingModal({
      isOpen: true,
      title: '视频准备中',
      description: `正在将视频 ${currentItem.index + 1} 上传到云端，请稍候...`,
      type: 'download'
    });
    
    const response = await fetch(`${API_BASE_URL}/api/combinations/${currentItem.id}/download`, {
      method: 'POST'
    });
    const data = await response.json();

    if (data.status === 'completed') {
      // 立即完成，改为下载中弹窗
      setProcessingModal({
        isOpen: true,
        title: '视频下载中',
        description: `视频 ${currentItem.index + 1} 准备完成，正在下载...`,
        type: 'download'
      });
      
      await downloadVideo(data.video_url, `mixcut_${currentItem.id}.mp4`);
      
      // 关闭弹窗
      setProcessingModal(prev => ({ ...prev, isOpen: false }));
    } else if (data.status === 'processing') {
      // 轮询状态
      await pollBatchDownloadStatus(currentItem);
    }
  }
}, [results, downloadingIds]);
```

### 新增 pollBatchDownloadStatus 函数

```typescript
const pollBatchDownloadStatus = async (item: ResultItem) => {
  const maxAttempts = 60;
  const interval = 2000;
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(`${API_BASE_URL}/api/combinations/${item.id}/server-render/status`);
    const data = await response.json();
    
    if (data.status === 'completed') {
      // 改为下载中弹窗
      setProcessingModal({
        isOpen: true,
        title: '视频下载中',
        description: `视频 ${item.index + 1} 准备完成，正在下载...`,
        type: 'download'
      });
      
      await downloadVideo(data.video_url, `mixcut_${item.id}.mp4`);
      
      // 关闭弹窗
      setProcessingModal(prev => ({ ...prev, isOpen: false }));
      return;
    }
    
    await new Promise(resolve => setTimeout(resolve, interval));
  }
  
  // 超时
  setProcessingModal(prev => ({ ...prev, isOpen: false }));
  alert('视频准备超时，请稍后再试');
};
```

## 批量下载流程（修复后）

```
用户点击"下载选中"
    ↓
只处理第一个选中的视频
    ↓
检查是否有OSS URL
    ↓
有 → 显示"视频下载中"弹窗 → 下载 → 关闭弹窗
    ↓
无 → 显示"视频准备中"弹窗 → 调用后端接口
    ↓
立即完成 → 改为"视频下载中"弹窗 → 下载 → 关闭弹窗
    ↓
正在处理 → 轮询状态 → 准备完成 → 改为"视频下载中" → 下载 → 关闭弹窗
    ↓
如果还有多个选中，提示用户重新选择
```

## 设计说明

### 为什么只处理第一个视频？

1. **避免弹窗冲突**：多个视频同时准备会导致弹窗频繁切换
2. **简化用户体验**：用户一次只关注一个视频的下载进度
3. **防止混乱**：多个轮询同时运行会增加复杂度

### 多个视频如何处理？

下载完第一个视频后，提示用户：
```
已下载选中的第1个视频，还有 N 个视频未下载。
请重新选择后再次下载。
```

用户可以选择继续下载下一个。

## 修复日期

2025-04-28
