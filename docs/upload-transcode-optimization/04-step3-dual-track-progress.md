# 优化步骤3: 优化双轨进度显示逻辑

## 修改文件
- `frontend/src/components/EditScreen.tsx`

## 问题分析

### 原有问题
1. **进度计算混乱**: 浏览器轨道占0-40%，服务器轨道占0-50%，但它们是并行执行的
2. **进度冲突**: 两个轨道同时更新进度，可能导致显示不准确
3. **完成状态误导**: 显示100%时，实际上服务器转码可能还没完成

## 修改内容

### 1. 添加双轨进度跟踪变量
```typescript
// 双轨进度跟踪
let browserTrackProgress = 0;
let serverTrackProgress = 0;

const updateCombinedProgress = () => {
  // 浏览器轨道占50%，服务器轨道占50%
  const combinedProgress = Math.round((browserTrackProgress * 0.5) + (serverTrackProgress * 0.5));
  setUploading({ shotId, progress: combinedProgress });
};
```

### 2. 浏览器轨道进度 (0-100%，占最终进度的50%)
```typescript
const browserTrackPromise = processMaterial(file, {
  // ...
  onProgress: (progress, stage) => {
    browserTrackProgress = progress;
    updateCombinedProgress();
  },
});
```

### 3. 服务器轨道进度 (0-100%，占最终进度的50%)

#### 上传阶段 (0-50%)
```typescript
xhr.upload.addEventListener('progress', (e) => {
  if (e.lengthComputable) {
    // 上传阶段占服务器轨道的50%
    const uploadRatio = e.loaded / e.total;
    serverTrackProgress = Math.round(uploadRatio * 50);
    updateCombinedProgress();
  }
});
```

#### 上传完成 (50%)
```typescript
xhr.addEventListener('load', () => {
  if (xhr.status === 200) {
    // 上传完成，服务器轨道显示50%，等待转码完成
    serverTrackProgress = 50;
    updateCombinedProgress();
    resolve(result);
  }
});
```

#### 转码阶段 (50-100%)
- 如果有转码任务，上传完成后保持50%
- 转码完成后自动更新到100%（通过全局转码面板显示）
- 如果没有转码任务，直接显示100%

## 新的进度计算逻辑

| 阶段 | 浏览器轨道 | 服务器轨道 | 总进度 |
|------|-----------|-----------|--------|
| 初始 | 0% | 0% | 0% |
| 浏览器转码50%，上传50% | 50% | 25% | 37.5% |
| 浏览器转码完成，上传完成 | 100% | 50% | 75% |
| 转码完成 | 100% | 100% | 100% |

## 用户体验改进

1. **进度更准确**: 两个轨道独立计算，然后合并显示
2. **避免误导**: 上传完成但转码未完成时，进度停在75%左右
3. **透明化**: 用户可以清楚知道当前处于哪个阶段
