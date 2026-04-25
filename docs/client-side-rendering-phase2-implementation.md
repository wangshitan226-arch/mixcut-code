# MixCut 客户端渲染架构 - 阶段2实现文档

> **阶段**: 第二阶段 - 核心功能实现  
> **日期**: 2026-04-24  
> **状态**: ✅ 已完成  

---

## 一、实现概述

本阶段完成了客户端渲染的核心功能，实现了前端组合生成、本地视频拼接和渲染结果预览。主要包含：

1. **素材本地处理** - 浏览器端转码、缩略图生成
2. **前端组合生成** - 纯 JS 计算排列组合
3. **客户端拼接渲染** - FFmpeg WASM 本地视频拼接
4. **客户端导出上传** - 本地渲染后直传 OSS
5. **React Hooks** - 状态管理和流程控制
6. **UI 组件** - 上传组件和结果展示组件

---

## 二、新增文件清单

### 2.1 核心处理模块

| 文件路径 | 说明 | 大小 |
|---------|------|------|
| `frontend/src/utils/clientMaterialProcessor.ts` | 素材本地处理（转码+缩略图） | ~12KB |
| `frontend/src/utils/clientRenderer.ts` | 客户端拼接渲染 | ~10KB |
| `frontend/src/utils/combinationGenerator.ts` | 前端组合生成 | ~8KB |
| `frontend/src/utils/clientExport.ts` | 客户端导出上传 | ~6KB |

### 2.2 React Hooks

| 文件路径 | 说明 | 大小 |
|---------|------|------|
| `frontend/src/hooks/useFFmpeg.ts` | FFmpeg 状态管理 | ~3KB |
| `frontend/src/hooks/useOPFS.ts` | OPFS 存储状态 | ~3KB |
| `frontend/src/hooks/useClientRendering.ts` | 主控 Hook | ~8KB |

### 2.3 UI 组件

| 文件路径 | 说明 | 大小 |
|---------|------|------|
| `frontend/src/components/ClientMaterialUploader.tsx` | 客户端素材上传组件 | ~6KB |
| `frontend/src/components/ClientResultsScreen.tsx` | 客户端结果展示组件 | ~12KB |

---

## 三、模块详细说明

### 3.1 clientMaterialProcessor.ts - 素材本地处理

**主要功能**:
- 本地视频转码（支持高中低三种质量）
- 缩略图生成（FFmpeg 或 Canvas 降级）
- 自动存储到 OPFS/IndexedDB
- 设备能力适配

**核心 API**:

```typescript
// 处理单个素材
const material = await processMaterial(file, {
  quality: 'medium',
  generateThumbnail: true,
  onProgress: (progress, stage) => {
    console.log(`${stage}: ${progress}%`);
  },
});

// 批量处理
const materials = await processMaterials(files, options);

// 检查素材是否已处理
const exists = await isMaterialProcessed(materialId);
```

**处理流程**:

```
用户选择文件
    ↓
检测设备能力
    ↓
FFmpeg 转码（15% -> 70%）
    ↓
生成缩略图（75% -> 90%）
    ↓
保存到 OPFS/IndexedDB（90% -> 100%）
    ↓
上传元数据到服务器
```

### 3.2 clientRenderer.ts - 客户端拼接渲染

**主要功能**:
- 快速预览渲染（copy 模式，秒级）
- 高清渲染（重新编码）
- 素材本地加载（OPFS/IndexedDB）
- Blob URL 生命周期管理

**核心 API**:

```typescript
// 渲染预览（秒级）
const preview = await renderPreview(combination, {
  onProgress: (progress, stage) => {
    console.log(`${stage}: ${progress}%`);
  },
});

// 渲染高清版本
const hd = await renderHD(combination, options);

// 获取已渲染视频
const blobUrl = await getRenderedVideo(renderId);

// 释放 Blob URL
releaseBlobUrl(blobUrl);
```

**渲染模式对比**:

| 模式 | 速度 | 质量 | 适用场景 |
|------|------|------|----------|
| 预览 (copy) | 1-3秒 | 原始质量 | 快速预览 |
| 高清 (encode) | 10-30秒 | 重新编码 | 最终导出 |

### 3.3 combinationGenerator.ts - 前端组合生成

**主要功能**:
- 纯 JavaScript 计算排列组合
- 唯一性评分算法
- 智能生成策略（高唯一性优先）
- 服务器数据转换

**核心 API**:

```typescript
// 生成所有组合
const combinations = generateCombinations(shots, materialsMap, {
  limit: 1000,
  minUniqueness: 50,
});

// 智能生成（优先高唯一性）
const smartCombos = generateSmartCombinations(shots, materialsMap);

// 转换服务器数据
const materials = convertServerMaterials(serverMaterials);
const materialsMap = groupMaterialsByShot(materials);
```

**唯一性评分算法**:

```typescript
// 基于素材重复程度计算
uniqueness = 100 - (duplicateCount / totalMaterials) * 100

// 标签
90-100: 完全不重复
70-89:  极低重复率
50-69:  低重复率
30-49:  普通
0-29:   高重复率
```

### 3.4 clientExport.ts - 客户端导出上传

**主要功能**:
- 本地高清渲染
- OSS 直传（带进度）
- 批量导出
- 本地下载

**核心 API**:

```typescript
// 导出到 OSS
const result = await exportVideoToOSS(combination, {
  quality: 'high',
  onProgress: (progress, stage) => {
    console.log(`${stage}: ${progress}%`);
  },
});

// 批量导出
const results = await batchExport(combinations, options);

// 本地下载
downloadVideo(blob, 'video.mp4');
```

**上传流程**:

```
本地高清渲染 (0% -> 60%)
    ↓
获取 OSS 签名 (60% -> 65%)
    ↓
直传到 OSS (65% -> 95%)
    ↓
通知服务器记录 (95% -> 100%)
```

### 3.5 React Hooks

#### useFFmpeg.ts

```typescript
const {
  ffmpeg,        // FFmpeg 实例
  isLoaded,      // 是否已加载
  isLoading,     // 是否加载中
  error,         // 错误信息
  loadProgress,  // 加载进度
  load,          // 加载方法
  terminate,     // 终止方法
} = useFFmpeg();
```

#### useOPFS.ts

```typescript
const {
  storageInfo,   // 存储信息
  isChecking,    // 是否检查中
  error,         // 错误信息
  refresh,       // 刷新方法
  checkSpace,    // 检查空间
} = useOPFS();
```

#### useClientRendering.ts

```typescript
const {
  // 设备能力
  deviceCapability,
  isDetecting,

  // 渲染模式
  mode,
  setMode,

  // 状态
  isProcessing,
  processingProgress,
  isRendering,
  renderProgress,
  isExporting,
  exportProgress,

  // 操作方法
  processMaterialFile,
  renderPreviewVideo,
  renderHDVideo,
  exportVideo,
  generateCombinationList,
} = useClientRendering('auto');
```

---

## 四、UI 组件

### 4.1 ClientMaterialUploader

**功能**:
- 文件选择
- 客户端转码（带进度显示）
- 自动降级到服务器上传
- 元数据上传

**使用示例**:

```tsx
<ClientMaterialUploader
  userId="user123"
  shotId={1}
  onUploadComplete={(material) => {
    console.log('上传完成:', material.id);
  }}
  onError={(error) => {
    console.error('上传失败:', error);
  }}
/>
```

**界面状态**:

| 状态 | 显示 |
|------|------|
| 空闲 | "+ 添加素材" |
| 处理中 | 进度条 + 阶段文字 |
| 完成 | 自动关闭，触发 onUploadComplete |

### 4.2 ClientResultsScreen

**功能**:
- 自动检测设备渲染能力
- 优先本地渲染，降级服务器渲染
- Blob URL 播放
- 本地下载
- 批量操作

**渲染策略**:

```
用户点击播放
    ↓
检查本地缓存
    ↓
有缓存 → 直接播放
    ↓
无缓存 → 检查设备能力
    ↓
支持本地渲染 → 客户端拼接（1-3秒）
    ↓
不支持 → 服务器渲染（3-5秒）
    ↓
播放视频
```

---

## 五、使用示例

### 5.1 完整流程示例

```typescript
import { useClientRendering } from '../hooks/useClientRendering';

function MyComponent() {
  const {
    deviceCapability,
    processMaterialFile,
    renderPreviewVideo,
    exportVideo,
    isProcessing,
    processingProgress,
    isRendering,
    renderProgress,
  } = useClientRendering('auto');

  // 处理素材
  const handleUpload = async (file: File) => {
    const material = await processMaterialFile(file, {
      quality: deviceCapability?.recommendedQuality,
    });

    if (material) {
      // 保存素材 ID
      console.log('素材处理完成:', material.id);
    }
  };

  // 渲染预览
  const handlePreview = async (combination: Combination) => {
    const result = await renderPreviewVideo(combination);

    if (result) {
      // 播放视频
      videoRef.current.src = result.blobUrl;
      videoRef.current.play();
    }
  };

  // 导出视频
  const handleExport = async (combination: Combination) => {
    const result = await exportVideo(combination, {
      quality: 'high',
    });

    if (result) {
      console.log('导出成功:', result.cdnUrl);
    }
  };
}
```

### 5.2 组合生成示例

```typescript
import {
  convertServerMaterials,
  groupMaterialsByShot,
  generateSmartCombinations,
} from '../utils/combinationGenerator';

// 从服务器数据生成组合
const materials = convertServerMaterials(serverMaterials);
const materialsMap = groupMaterialsByShot(materials);

const shots = [
  { id: 'shot1', name: '开场', order: 1 },
  { id: 'shot2', name: '主体', order: 2 },
  { id: 'shot3', name: '结尾', order: 3 },
];

const combinations = generateSmartCombinations(shots, materialsMap, {
  limit: 1000,
});

console.log(`生成了 ${combinations.length} 个组合`);
console.log('前10个组合:', combinations.slice(0, 10));
```

---

## 六、技术要点

### 6.1 FFmpeg WASM 类型处理

FFmpeg WASM 的 `readFile` 返回 `FileData` 类型（`Uint8Array | string`），需要类型断言：

```typescript
const data = await ffmpeg.readFile(outputName);
const blob = new Blob([data as Uint8Array], { type: 'video/mp4' });
```

### 6.2 Blob URL 生命周期管理

Blob URL 需要手动释放，避免内存泄漏：

```typescript
// 创建
const blobUrl = URL.createObjectURL(blob);

// 使用
video.src = blobUrl;

// 释放（组件卸载时）
URL.revokeObjectURL(blobUrl);
```

### 6.3 降级策略

```typescript
async function autoRender(item: ResultItem): Promise<string | null> {
  // 尝试客户端渲染
  if (useClientRendering) {
    const clientUrl = await clientRender(item);
    if (clientUrl) return clientUrl;
  }

  // 降级到服务器渲染
  return await serverRender(item);
}
```

### 6.4 进度计算

各阶段进度分配：

| 阶段 | 进度范围 | 说明 |
|------|----------|------|
| 素材处理 | 0% -> 100% | 转码 15%-70%，缩略图 75%-90% |
| 预览渲染 | 0% -> 100% | 加载素材 0%-30%，拼接 30%-90% |
| 高清渲染 | 0% -> 100% | 加载素材 0%-20%，编码 20%-95% |
| 导出上传 | 0% -> 100% | 渲染 0%-60%，上传 60%-95% |

---

## 七、性能优化

### 7.1 快速预览

使用 FFmpeg copy 模式拼接，不重新编码：

```typescript
await ffmpeg.exec([
  '-f', 'concat',
  '-safe', '0',
  '-i', listName,
  '-c:v', 'copy',  // 视频直接复制
  '-c:a', 'copy',  // 音频直接复制
  '-y',
  outputName,
]);
```

### 7.2 智能预加载

优先预加载前 3 个视频：

```typescript
const videosToPreload = items
  .filter(item => item.preview_status === 'completed')
  .slice(0, 3);
```

### 7.3 批量处理

支持批量处理多个素材，自动计算总体进度：

```typescript
const materials = await processMaterials(files, {
  onProgress: (overallProgress, stage) => {
    console.log(`总体进度: ${overallProgress}%`);
  },
});
```

---

## 八、已知限制

### 8.1 浏览器兼容性

| 功能 | Chrome | Safari | Firefox |
|------|--------|--------|---------|
| FFmpeg WASM | ✅ | ⚠️ | ⚠️ |
| OPFS | ✅ | 16.4+ | ❌ |
| WebCodecs | ✅ | 16.4+ | ❌ |

### 8.2 文件大小限制

- **单文件处理**: 建议不超过 500MB
- **内存使用**: 取决于设备，建议 8GB+
- **存储配额**: OPFS 取决于磁盘空间

### 8.3 性能考虑

- 首次加载 FFmpeg WASM 需要下载 ~32MB
- 视频转码是 CPU 密集型操作
- 大文件处理时需要等待

---

## 九、下一步计划（阶段3）

阶段3将实现文字快剪本地化和优化：

1. **WebCodecs 本地播放**
   - 从 OPFS 读取素材
   - 本地解码播放
   - 毫秒级响应

2. **本地导出功能**
   - 文字快剪结果本地生成
   - 本地导出和 OSS 直传

3. **移动端适配**
   - 移动端性能优化
   - 触摸操作优化
   - 内存管理优化

---

## 十、文件变更汇总

### 新增文件

```
frontend/
├── src/utils/
│   ├── clientMaterialProcessor.ts    (新增)
│   ├── clientRenderer.ts             (新增)
│   ├── combinationGenerator.ts       (新增)
│   └── clientExport.ts               (新增)
├── src/hooks/
│   ├── useFFmpeg.ts                  (新增)
│   ├── useOPFS.ts                    (新增)
│   └── useClientRendering.ts         (新增)
└── src/components/
    ├── ClientMaterialUploader.tsx    (新增)
    └── ClientResultsScreen.tsx       (新增)
```

### 修改文件

```
frontend/
└── src/components/ResultsScreen.tsx   (修复 saveVideo 调用参数)
```

---

## 十一、验证清单

- [x] TypeScript 类型检查通过
- [x] clientMaterialProcessor.ts 创建完成
- [x] clientRenderer.ts 创建完成
- [x] combinationGenerator.ts 创建完成
- [x] clientExport.ts 创建完成
- [x] useFFmpeg.ts Hook 创建完成
- [x] useOPFS.ts Hook 创建完成
- [x] useClientRendering.ts Hook 创建完成
- [x] ClientMaterialUploader 组件创建完成
- [x] ClientResultsScreen 组件创建完成
- [x] 所有 FFmpeg WASM 类型兼容

---

## 十二、参考文档

- [FFmpeg.wasm API 文档](https://ffmpegwasm.netlify.app/docs/api/ffmpeg/)
- [OPFS API 文档](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system)
- [WebCodecs API 文档](https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API)
- [Blob URL 管理](https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL)

---

*文档版本: 1.0*  
*创建日期: 2026-04-24*  
*作者: AI Assistant*
