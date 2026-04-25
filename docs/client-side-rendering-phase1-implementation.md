# MixCut 客户端渲染架构 - 阶段1实现文档

> **阶段**: 第一阶段 - 基础能力构建  
> **日期**: 2026-04-24  
> **状态**: ✅ 已完成  

---

## 一、实现概述

本阶段完成了客户端渲染架构的基础能力建设，包括：

1. **FFmpeg WASM 集成** - 浏览器端视频处理能力
2. **OPFS 存储封装** - 浏览器私有文件系统存储
3. **IndexedDB 降级存储** - 当 OPFS 不可用时的降级方案
4. **设备能力检测** - 自动检测设备性能和兼容性

---

## 二、新增文件清单

### 2.1 核心模块文件

| 文件路径 | 说明 | 大小 |
|---------|------|------|
| `frontend/src/utils/ffmpeg.ts` | FFmpeg WASM 封装模块 | ~15KB |
| `frontend/src/utils/opfs.ts` | OPFS 存储封装模块 | ~12KB |
| `frontend/src/utils/indexedDB.ts` | IndexedDB 降级存储 | ~10KB |
| `frontend/src/utils/deviceCapability.ts` | 设备能力检测 | ~12KB |

### 2.2 FFmpeg WASM 核心文件

| 文件路径 | 说明 | 大小 |
|---------|------|------|
| `frontend/public/ffmpeg/ffmpeg-core.js` | FFmpeg WASM JS 入口 | ~114KB |
| `frontend/public/ffmpeg/ffmpeg-core.wasm` | FFmpeg WASM 二进制 | ~32MB |

### 2.3 依赖更新

```json
// package.json 新增依赖
{
  "@ffmpeg/ffmpeg": "^0.12.15",
  "@ffmpeg/util": "^0.12.2"
}
```

---

## 三、模块详细说明

### 3.1 ffmpeg.ts - FFmpeg WASM 封装

**主要功能**:
- FFmpeg WASM 单例管理
- 视频转码（支持高中低三种质量）
- 视频拼接（copy 模式秒级拼接）
- 缩略图生成
- 视频信息获取

**核心 API**:

```typescript
// 获取 FFmpeg 实例
const ffmpeg = await getFFmpeg();

// 转码视频
const blob = await transcodeVideo(file, 'medium');

// 拼接视频
const blob = await concatVideos(videoFiles, false);

// 生成缩略图
const thumbnail = await generateThumbnail(videoFile, 1, 300, 400);

// 检查支持
const support = checkFFmpegSupport();
```

**质量配置**:

| 质量 | CRF | Preset | 分辨率 | 适用场景 |
|------|-----|--------|--------|----------|
| low | 28 | ultrafast | 720x1280 | 移动端/低端设备 |
| medium | 23 | superfast | 1080x1920 | 默认配置 |
| high | 18 | medium | 1080x1920 | 高质量导出 |

### 3.2 opfs.ts - OPFS 存储封装

**主要功能**:
- 素材持久化存储
- 渲染结果存储
- 存储配额管理
- LRU 清理策略

**核心 API**:

```typescript
// 保存素材
await saveMaterial(materialId, videoBlob, thumbnailBlob);

// 读取素材
const { video, thumbnail } = await loadMaterial(materialId);

// 检查存在
const exists = await hasMaterial(materialId);

// 删除素材
await deleteMaterial(materialId);

// 获取存储配额
const { usage, quota } = await getStorageQuota();

// LRU 清理
await cleanupLRU(targetBytes);
```

**存储结构**:

```
OPFS Root/
├── materials/
│   └── {materialId}/
│       ├── video.mp4
│       └── thumbnail.jpg
└── renders/
    └── {renderId}.mp4
```

### 3.3 indexedDB.ts - 降级存储

**主要功能**:
- 当 OPFS 不可用时的降级方案
- 支持素材和渲染结果存储
- LRU 清理策略
- 存储大小限制（最大 200MB，单文件 50MB）

**使用场景**:
- Safari 16.4 以下版本
- 隐私模式下 OPFS 被禁用
- 其他 OPFS 不支持的环境

### 3.4 deviceCapability.ts - 设备能力检测

**主要功能**:
- 检测 FFmpeg WASM 支持
- 检测 OPFS 支持
- 检测 WebCodecs 支持
- 评估设备性能等级
- 提供推荐配置

**检测项**:

| 检测项 | 说明 | 最低要求 |
|--------|------|----------|
| WebAssembly | WASM 支持 | 必需 |
| SharedArrayBuffer | 共享内存 | 必需 |
| OPFS | 私有文件系统 | 推荐 |
| WebCodecs | 编解码 API | 可选 |
| 内存 | 设备内存 | 4GB |
| CPU 核心 | 处理器核心数 | 2核 |

**性能等级**:

| 等级 | 内存 | CPU | 最大文件 | 质量 |
|------|------|-----|----------|------|
| high | ≥16GB | ≥8核 | 500MB | high |
| medium | ≥8GB | ≥4核 | 200MB | medium |
| low | ≥4GB | ≥2核 | 100MB | low |
| unsupported | <4GB | <2核 | - | 服务器降级 |

---

## 四、使用示例

### 4.1 初始化检测

```typescript
import { detectDeviceCapability } from './utils/deviceCapability';

async function initialize() {
  const capability = await detectDeviceCapability();
  
  if (!capability.canUseClientRendering) {
    console.log('不支持客户端渲染，使用服务器降级:', capability.unsupportedReasons);
    // 切换到服务器处理模式
    return;
  }
  
  console.log('设备性能等级:', capability.performanceLevel);
  console.log('推荐质量:', capability.recommendedQuality);
  console.log('最大文件大小:', capability.maxFileSize);
}
```

### 4.2 素材处理流程

```typescript
import { transcodeVideo, generateThumbnail } from './utils/ffmpeg';
import { saveMaterial } from './utils/opfs';

async function processMaterial(file: File) {
  // 1. 转码为统一格式
  const videoBlob = await transcodeVideo(file, 'medium');
  
  // 2. 生成缩略图
  const thumbnailBlob = await generateThumbnail(videoBlob, 1);
  
  // 3. 保存到 OPFS
  const materialId = generateUUID();
  await saveMaterial(materialId, videoBlob, thumbnailBlob);
  
  // 4. 只上传元数据到服务器
  await uploadMetadata({
    id: materialId,
    duration: await getVideoDuration(videoBlob),
    size: videoBlob.size,
  });
  
  return materialId;
}
```

### 4.3 视频拼接流程

```typescript
import { concatVideos } from './utils/ffmpeg';
import { loadMaterial, saveRender } from './utils/opfs';

async function renderCombination(materialIds: string[]) {
  // 1. 从 OPFS 读取素材
  const videoFiles = await Promise.all(
    materialIds.map(id => loadMaterial(id).then(m => m.video!))
  );
  
  // 2. 本地拼接（copy 模式，秒级）
  const renderBlob = await concatVideos(videoFiles, false);
  
  // 3. 保存到 OPFS
  const renderId = generateUUID();
  await saveRender(renderId, renderBlob);
  
  // 4. 生成 Blob URL 供播放
  const blobUrl = URL.createObjectURL(renderBlob);
  
  return { renderId, blobUrl };
}
```

---

## 五、技术要点

### 5.1 跨域隔离要求

FFmpeg WASM 需要 `SharedArrayBuffer`，这要求服务器配置以下响应头：

```http
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

Vite 开发服务器配置：

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
});
```

### 5.2 内存管理

- FFmpeg WASM 使用虚拟文件系统，处理完成后需清理临时文件
- OPFS 存储有配额限制，需要实现 LRU 清理策略
- 大文件处理时需要分片，避免内存溢出

### 5.3 降级策略

当客户端渲染不可用时，自动降级到服务器处理：

```typescript
async function initializeClientRendering() {
  const checks = await Promise.all([
    checkFFmpegSupport(),
    checkOPFSSupport(),
    checkMemoryAvailability(),
    checkDevicePerformance(),
  ]);
  
  if (checks.every(c => c.passed)) {
    return new ClientRenderer();
  } else {
    console.log('降级到服务器渲染');
    return new ServerRenderer();
  }
}
```

---

## 六、已知限制

### 6.1 浏览器兼容性

| 浏览器 | 版本要求 | 支持状态 |
|--------|----------|----------|
| Chrome | 89+ | ✅ 完全支持 |
| Edge | 89+ | ✅ 完全支持 |
| Safari | 16.4+ | ⚠️ 部分支持 |
| Firefox | 79+ | ⚠️ 需要配置 |

### 6.2 文件大小限制

- **OPFS**: 取决于磁盘空间，通常可达数 GB
- **IndexedDB**: 最大 200MB（降级方案）
- **内存**: 取决于设备，建议单文件不超过 500MB

### 6.3 性能考虑

- 首次加载 FFmpeg WASM 需要下载 ~32MB 文件
- 视频转码是 CPU 密集型操作，会占用主线程
- 建议在 Web Worker 中执行（未来优化）

---

## 七、下一步计划（阶段2）

阶段2将实现素材本地处理功能：

1. **改造上传流程**
   - 本地转码 → OPFS 存储 → 仅上传元数据
   - 修改后端 `upload.py` 支持元数据-only 上传

2. **添加上传组件**
   - 创建 `MaterialUploader` 组件
   - 集成 FFmpeg 转码进度显示
   - 实现 OPFS 存储状态管理

3. **实现降级策略**
   - 设备不支持时自动回退服务器处理
   - 添加用户提示和引导

---

## 八、文件变更汇总

### 新增文件

```
frontend/
├── src/utils/
│   ├── ffmpeg.ts          (新增)
│   ├── opfs.ts            (新增)
│   ├── indexedDB.ts       (新增)
│   └── deviceCapability.ts (新增)
└── public/ffmpeg/
    ├── ffmpeg-core.js     (新增, 114KB)
    └── ffmpeg-core.wasm   (新增, 32MB)
```

### 修改文件

```
frontend/
├── package.json           (添加 @ffmpeg/ffmpeg, @ffmpeg/util 依赖)
└── vite.config.ts         (需要添加 COOP/COEP headers)
```

---

## 九、验证清单

- [x] FFmpeg WASM 依赖安装成功
- [x] ffmpeg.ts 模块创建完成
- [x] opfs.ts 模块创建完成
- [x] indexedDB.ts 模块创建完成
- [x] deviceCapability.ts 模块创建完成
- [x] FFmpeg WASM 核心文件下载完成
- [x] TypeScript 类型检查通过
- [x] 代码结构符合项目规范

---

## 十、参考文档

- [FFmpeg.wasm 官方文档](https://ffmpegwasm.netlify.app/)
- [OPFS API 文档](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system)
- [WebCodecs API 文档](https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API)
- [SharedArrayBuffer 要求](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer#security_requirements)

---

*文档版本: 1.0*  
*创建日期: 2026-04-24*  
*作者: AI Assistant*
