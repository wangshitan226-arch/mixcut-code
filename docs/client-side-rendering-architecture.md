# MixCut 客户端渲染架构方案

> 将视频处理从服务器迁移到用户浏览器，实现零成本无限并发
> 
> 文档版本: 1.0
> 更新日期: 2026-04-24

---

## 一、当前架构完整流程梳理

### 1.1 现有流程全链路

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              当前服务器端渲染流程                              │
└─────────────────────────────────────────────────────────────────────────────┘

【1. 素材上传阶段】
用户选择文件 → 浏览器FormData上传 → 服务器接收保存(uploads/)
                                                            ↓
服务器后台线程：ffmpeg转码(unified/) ← 生成缩略图(thumbnails/)
                                                            ↓
返回素材信息 + 转码任务ID

【2. 排列组合生成阶段】
用户点击"生成混剪" → 服务器生成1000+种组合规则(数据库)
                                                            ↓
生成缩略图网格展示

【3. 预览播放阶段】
用户点击某个组合"播放" → 服务器检查是否已渲染
                                                            ↓
未渲染：fast_concat_videos()秒级拼接(renders/)
已渲染：直接返回文件URL
                                                            ↓
服务器传输视频 → 浏览器播放
同时：异步上传OSS

【4. 文字快剪阶段】
用户选择视频 → 服务器返回OSS URL → 阿里云ICE处理
                                                            ↓
ICE回调 → 下载到本地 → 文字快剪界面

【5. 下载导出阶段】
用户点击下载 → 从OSS获取高清版本 → 用户下载

【成本分析】
- 服务器：2核4G ¥50/月
- OSS存储：¥10-50/月
- ICE渲染：¥0.06/分钟 × 总时长
- 并发：1-2人（服务器瓶颈）
```

### 1.2 各环节资源消耗

| 环节 | 计算资源 | 存储 | 带宽 | 耗时 |
|------|---------|------|------|------|
| 素材上传 | 低 | 原始文件 | 上传带宽 | 秒级 |
| 素材转码 | **高（ffmpeg）** | 转码后文件 | - | 10-30秒 |
| 组合生成 | 低 | 数据库记录 | - | 秒级 |
| 视频拼接 | **中（ffmpeg concat）** | 成品文件 | - | 1-3秒 |
| 视频传输 | - | - | **下载带宽（瓶颈）** | 视文件大小 |
| ICE渲染 | **云端（按量付费）** | - | - | 3-10秒 |

---

## 二、客户端渲染架构设计

### 2.1 核心思想

```
传统：用户设备 → 上传 → 服务器处理 → 下载 → 播放
新架构：用户设备 → 本地处理 → 本地播放 → 按需上传

关键洞察：
1. 现代浏览器可以运行 FFmpeg（WebAssembly）
2. 浏览器存储（OPFS/IndexedDB）可以存大文件
3. 用户设备性能足够（手机都能剪视频）
4. 只有"分享/下载"需要云端，其他全部本地
```

### 2.2 新架构流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端渲染新架构                                  │
└─────────────────────────────────────────────────────────────────────────────┘

【1. 素材上传阶段 → 改为"素材本地缓存"】
用户选择文件 → 浏览器读取File对象
                                    ↓
┌─────────────────────────────────────────┐
│ 浏览器本地处理（不经过服务器）            │
│ • FFmpeg WASM 转码 → 统一格式           │
│ • 生成缩略图（Canvas）                   │
│ • 保存到 OPFS/IndexedDB                  │
└─────────────────────────────────────────┘
                                    ↓
仅上传：素材元数据（文件名、时长、大小）→ 服务器数据库

【2. 排列组合生成阶段 → 纯前端计算】
用户点击"生成混剪" → 浏览器计算排列组合
                                    ↓
无需服务器参与，纯前端JavaScript生成1000+种组合规则
                                    ↓
展示缩略图网格（从本地缓存读取）

【3. 预览播放阶段 → 本地秒级拼接】
用户点击某个组合"播放"
                                    ↓
┌─────────────────────────────────────────┐
│ 浏览器本地处理                            │
│ • FFmpeg WASM concat（秒级）             │
│ • 生成 Blob URL                          │
│ • video标签播放                          │
└─────────────────────────────────────────┘
                                    ↓
播放完成 → 询问用户"是否满意？"
                                    ↓
满意 → 上传到OSS（供下载/分享用）
不满意 → 直接丢弃，零成本

【4. 文字快剪阶段 → 本地WebCodecs处理】
用户选择视频 → 从本地缓存读取File对象
                                    ↓
┌─────────────────────────────────────────┐
│ 浏览器本地处理                            │
│ • WebCodecs API 解码                     │
│ • Canvas 渲染 + 跳过删除段                │
│ • 实时预览，毫秒级响应                    │
└─────────────────────────────────────────┘
                                    ↓
确认导出 → FFmpeg WASM 重新编码 → 上传OSS

【5. 下载导出阶段 → 从OSS获取】
用户点击下载 → 从OSS获取高清版本（CDN加速）→ 用户下载

【成本分析】
- 服务器：2核2G ¥30/月（纯API，无计算）
- OSS存储：¥5-20/月（仅存储用户确认的视频）
- 计算成本：¥0（用户设备承担）
- 并发：无限（每个用户用自己的设备）
```

---

## 三、详细改造方案

### 3.1 素材处理环节改造

#### 当前实现
```python
# backend/routes/upload.py
@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    file.save(filepath)  # 保存到服务器
    # 后台线程转码
    thread = threading.Thread(target=async_transcode_task, ...)
```

#### 新架构实现
```typescript
// frontend/src/utils/clientMaterialProcessor.ts

import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile } from '@ffmpeg/util';

export class ClientMaterialProcessor {
  private ffmpeg: FFmpeg | null = null;
  
  async init() {
    this.ffmpeg = new FFmpeg();
    await this.ffmpeg.load({
      coreURL: '/ffmpeg/ffmpeg-core.js',
      wasmURL: '/ffmpeg/ffmpeg-core.wasm',
    });
  }
  
  async processMaterial(file: File): Promise<ProcessedMaterial> {
    // 1. 生成唯一ID
    const materialId = generateUUID();
    
    // 2. 转码为统一格式
    const inputName = `input_${materialId}`;
    const outputName = `unified_${materialId}.mp4`;
    
    await this.ffmpeg!.writeFile(inputName, await fetchFile(file));
    
    await this.ffmpeg!.exec([
      '-i', inputName,
      '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30',
      '-c:v', 'libx264',
      '-crf', '23',
      '-preset', 'superfast',
      '-c:a', 'aac',
      '-b:a', '128k',
      '-movflags', '+faststart',
      outputName
    ]);
    
    // 3. 读取转码结果
    const data = await this.ffmpeg!.readFile(outputName);
    const unifiedBlob = new Blob([data.buffer], { type: 'video/mp4' });
    
    // 4. 生成缩略图（Canvas）
    const thumbnailBlob = await this.generateThumbnail(unifiedBlob);
    
    // 5. 保存到 OPFS（持久化存储）
    await this.saveToOPFS(materialId, unifiedBlob, thumbnailBlob);
    
    // 6. 获取视频信息
    const duration = await this.getVideoDuration(unifiedBlob);
    
    // 7. 仅上传元数据到服务器
    await this.uploadMetadata({
      id: materialId,
      originalName: file.name,
      duration,
      size: unifiedBlob.size,
      // 不上传视频文件！
    });
    
    return {
      id: materialId,
      duration,
      thumbnailUrl: URL.createObjectURL(thumbnailBlob),
    };
  }
  
  private async saveToOPFS(id: string, video: Blob, thumbnail: Blob) {
    const root = await navigator.storage.getDirectory();
    
    // 创建素材目录
    const dir = await root.getDirectoryHandle(`material_${id}`, { create: true });
    
    // 保存视频
    const videoFile = await dir.getFileHandle('video.mp4', { create: true });
    const videoWriter = await videoFile.createWritable();
    await videoWriter.write(video);
    await videoWriter.close();
    
    // 保存缩略图
    const thumbFile = await dir.getFileHandle('thumbnail.jpg', { create: true });
    const thumbWriter = await thumbFile.createWritable();
    await thumbWriter.write(thumbnail);
    await thumbWriter.close();
  }
  
  private async generateThumbnail(videoBlob: Blob): Promise<Blob> {
    const video = document.createElement('video');
    video.src = URL.createObjectURL(videoBlob);
    
    await new Promise((resolve) => {
      video.onloadedmetadata = () => {
        video.currentTime = 1; // 第1秒
        video.onseeked = resolve;
      };
    });
    
    const canvas = document.createElement('canvas');
    canvas.width = 300;
    canvas.height = 400;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    return new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob!), 'image/jpeg', 0.8);
    });
  }
}
```

#### 内存风险控制
```typescript
// 大文件分片处理
export async function processLargeFile(file: File) {
  const CHUNK_SIZE = 50 * 1024 * 1024; // 50MB分片
  
  if (file.size > CHUNK_SIZE) {
    // 大文件：流式处理
    return await streamProcess(file);
  } else {
    // 小文件：直接处理
    return await normalProcess(file);
  }
}

// 设备性能检测
export function checkDeviceCapability(): DeviceCapability {
  const memory = (navigator as any).deviceMemory || 4; // GB
  const cores = navigator.hardwareConcurrency || 2;
  
  return {
    canProcess: memory >= 4 && cores >= 4,
    maxFileSize: memory >= 8 ? 500 * 1024 * 1024 : 200 * 1024 * 1024,
    recommendedQuality: memory >= 8 ? 'high' : 'medium',
  };
}
```

---

### 3.2 排列组合生成环节改造

#### 当前实现
```python
# 服务器生成组合，保存到数据库
combinations = generate_combinations(shots, limit=1000)
db.session.add_all(combinations)
```

#### 新架构实现
```typescript
// frontend/src/utils/combinationGenerator.ts

export function generateCombinations(
  shots: Shot[],
  materials: Map<string, Material[]>,
  limit: number = 1000
): Combination[] {
  // 纯前端计算，不经过服务器
  const combinations: Combination[] = [];
  
  function backtrack(index: number, current: Material[]) {
    if (combinations.length >= limit) return;
    
    if (index === shots.length) {
      combinations.push({
        id: generateComboId(current),
        materials: [...current],
        duration: calculateDuration(current),
        tag: calculateUniqueness(current),
      });
      return;
    }
    
    const shotMaterials = materials.get(shots[index].id) || [];
    for (const material of shotMaterials) {
      current.push(material);
      backtrack(index + 1, current);
      current.pop();
    }
  }
  
  backtrack(0, []);
  return combinations;
}
```

---

### 3.3 预览播放环节改造

#### 当前实现
```python
# 服务器拼接，传输视频
success = fast_concat_videos(unified_files, output_path)
return jsonify({'video_url': f'/renders/{filename}'})
```

#### 新架构实现
```typescript
// frontend/src/utils/clientRenderer.ts

export class ClientRenderer {
  private ffmpeg: FFmpeg;
  
  async renderPreview(combination: Combination): Promise<string> {
    // 1. 从 OPFS 读取素材
    const materialFiles: File[] = [];
    for (const material of combination.materials) {
      const file = await this.loadFromOPFS(material.id);
      materialFiles.push(file);
    }
    
    // 2. 写入 FFmpeg WASM
    for (let i = 0; i < materialFiles.length; i++) {
      await this.ffmpeg.writeFile(`input${i}.mp4`, await fetchFile(materialFiles[i]));
    }
    
    // 3. 创建 concat 列表
    const list = materialFiles.map((_, i) => `file 'input${i}.mp4'`).join('\n');
    await this.ffmpeg.writeFile('input.txt', list);
    
    // 4. 秒级拼接（copy模式）
    await this.ffmpeg.exec([
      '-f', 'concat',
      '-safe', '0',
      '-i', 'input.txt',
      '-c:v', 'copy',  // 秒级的关键！
      '-c:a', 'copy',
      'output.mp4'
    ]);
    
    // 5. 读取结果
    const data = await this.ffmpeg.readFile('output.mp4');
    const blob = new Blob([data.buffer], { type: 'video/mp4' });
    
    // 6. 生成 Blob URL（直接播放，无需上传）
    return URL.createObjectURL(blob);
  }
  
  async renderForUpload(combination: Combination): Promise<Blob> {
    // 用户满意后，生成高质量版本上传
    // 使用重新编码而非copy，保证质量
    await this.ffmpeg.exec([
      '-f', 'concat',
      '-safe', '0',
      '-i', 'input.txt',
      '-c:v', 'libx264',
      '-crf', '18',
      '-preset', 'slow',  // 质量优先
      '-c:a', 'aac',
      '-b:a', '192k',
      'output_hd.mp4'
    ]);
    
    const data = await this.ffmpeg.readFile('output_hd.mp4');
    return new Blob([data.buffer], { type: 'video/mp4' });
  }
}
```

---

### 3.4 文字快剪环节改造

#### 当前实现
```python
# 提交到阿里云ICE
ice_client.submit_job(inputs, output)
```

#### 新架构实现
```typescript
// 使用已有的 WebCodecsPlayer
// 从本地缓存读取File对象，无需服务器

const videoFile = await loadFromOPFS(materialId);
<WebCodecsPlayer videoFile={videoFile} segments={segments} />
```

---

### 3.5 下载导出环节改造

#### 当前实现
```python
# 从OSS获取下载链接
return jsonify({'download_url': oss_url})
```

#### 新架构实现
```typescript
// 用户确认后，上传高清版到OSS
async function exportVideo(combination: Combination) {
  // 1. 生成本地高清版
  const hdBlob = await clientRenderer.renderForUpload(combination);
  
  // 2. 上传到OSS（直传）
  const signature = await fetch('/api/oss/signature').then(r => r.json());
  await uploadToOSS(hdBlob, signature);
  
  // 3. 通知服务器记录
  await fetch('/api/exports', {
    method: 'POST',
    body: JSON.stringify({
      combinationId: combination.id,
      ossUrl: signature.cdnUrl,
    })
  });
  
  return signature.cdnUrl;
}
```

---

## 四、移动端支持分析

### 4.1 移动端可行性

| 功能 | 可行性 | 说明 |
|------|--------|------|
| FFmpeg WASM | ✅ 支持 | Chrome/Edge/Safari iOS 都支持 |
| OPFS | ✅ 支持 | iOS 16.4+, Android Chrome |
| WebCodecs | ⚠️ 部分 | iOS Safari 16+ 支持 |
| 内存限制 | ⚠️ 需注意 | 手机内存小，大文件分片 |

### 4.2 移动端优化

```typescript
// 移动端检测
const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

// 移动端降级策略
if (isMobile) {
  // 降低转码质量
  config.crf = 28;  // 更高压缩
  config.preset = 'ultrafast';  // 更快
  
  // 限制文件大小
  config.maxFileSize = 100 * 1024 * 1024;  // 100MB
  
  // 简化功能
  config.enableWebCodecs = false;  // 用传统播放器
}
```

---

## 五、完整数据流对比

### 5.1 当前架构数据流

```
用户上传 100MB 视频
    ↓
服务器接收 100MB（带宽）
    ↓
服务器转码（CPU 100% 30秒）
    ↓
生成 100MB 统一格式（存储）
    ↓
用户点击播放
    ↓
服务器拼接（CPU 50% 3秒）
    ↓
生成 100MB 成品（存储）
    ↓
服务器传输 100MB 到浏览器（带宽，慢！）
    ↓
用户观看
    ↓
异步上传 100MB 到 OSS（带宽）

总成本：
- 服务器计算：30秒 × 100% CPU
- 服务器带宽：上传100MB + 下载100MB + OSS上传100MB = 300MB
- 存储：100MB素材 + 100MB统一格式 + 100MB成品 = 300MB
- 时间：30秒转码 + 3秒拼接 + 传输时间
```

### 5.2 客户端渲染数据流

```
用户上传 100MB 视频
    ↓
浏览器本地转码（用户CPU 30秒）
    ↓
生成 100MB 统一格式（OPFS存储）
    ↓
仅上传元数据 1KB 到服务器（带宽可忽略）
    ↓
用户点击播放
    ↓
浏览器本地拼接（用户CPU 1秒）
    ↓
生成 Blob URL（内存，不占用带宽）
    ↓
立即播放！
    ↓
用户满意，点击导出
    ↓
浏览器直传 100MB 到 OSS（带宽）

总成本：
- 服务器计算：0（用户设备承担）
- 服务器带宽：仅元数据 1KB
- 存储：仅用户确认的视频 100MB（OSS）
- 时间：30秒转码 + 1秒拼接 + 0秒传输 = 更快！
```

---

## 六、实施路线图

### 第一阶段：基础能力（2周）

| 天数 | 任务 | 产出 |
|------|------|------|
| 1-3 | FFmpeg WASM 集成 | `ffmpeg.ts` 加载模块 |
| 3-5 | OPFS 存储封装 | `opfs.ts` 读写模块 |
| 5-7 | 素材本地转码 | `clientMaterialProcessor.ts` |
| 7-10 | 元数据上传接口 | 改造 `upload.py` |
| 10-14 | 测试优化 | 内存控制、错误处理 |

### 第二阶段：核心功能（2周）

| 天数 | 任务 | 产出 |
|------|------|------|
| 1-3 | 前端组合生成 | `combinationGenerator.ts` |
| 3-6 | 客户端拼接 | `clientRenderer.ts` |
| 6-9 | 预览播放改造 | 改造 `ResultsScreen.tsx` |
| 9-12 | 本地缓存管理 | 改造 `videoCache.ts` |
| 12-14 | 集成测试 | 完整流程测试 |

### 第三阶段：文字快剪（1周）

| 天数 | 任务 | 产出 |
|------|------|------|
| 1-2 | WebCodecs 本地播放 | 改造 `WebCodecsPlayer.tsx` |
| 2-4 | 本地导出功能 | `clientExport.ts` |
| 4-5 | OSS直传集成 | 改造 `oss.ts` |

### 第四阶段：优化完善（1周）

| 天数 | 任务 | 产出 |
|------|------|------|
| 1-2 | 移动端适配 | 响应式降级 |
| 2-3 | 性能优化 | 内存管理、并发控制 |
| 3-4 | 错误处理 | 降级方案完善 |
| 4-5 | 全面测试 | 多设备测试 |

---

## 七、风险评估与应对

### 7.1 技术风险

| 风险 | 可能性 | 影响 | 应对 |
|------|--------|------|------|
| FFmpeg WASM 加载失败 | 中 | 无法处理视频 | 检测后降级到服务器处理 |
| OPFS 存储空间不足 | 中 | 无法保存素材 | LRU清理 + 提示用户清理 |
| 大文件内存溢出 | 中 | 浏览器崩溃 | 分片处理 + 文件大小限制 |
| 低端设备性能不足 | 高 | 转码极慢 | 设备检测 + 质量降级 |
| iOS Safari 兼容性 | 中 | 部分功能不可用 | 功能检测 + 优雅降级 |

### 7.2 降级策略

```typescript
// 自动降级检测
async function initializeClientRendering() {
  const checks = await Promise.all([
    checkFFmpegSupport(),
    checkOPFSSupport(),
    checkMemoryAvailability(),
    checkDevicePerformance(),
  ]);
  
  if (checks.every(c => c.passed)) {
    // 启用客户端渲染
    return new ClientRenderer();
  } else {
    // 降级到服务器渲染
    console.log('降级到服务器渲染:', checks.filter(c => !c.passed).map(c => c.reason));
    return new ServerRenderer();
  }
}
```

---

## 八、成本对比

### 8.1 月度成本对比（100活跃用户，每人生成10个视频）

| 项目 | 当前架构 | 客户端渲染 | 节省 |
|------|---------|-----------|------|
| 服务器 | ¥50（2核4G） | ¥30（2核2G纯API） | ¥20 |
| OSS存储 | ¥50（500GB） | ¥10（100GB，仅成品） | ¥40 |
| CDN流量 | ¥0（走服务器） | ¥30（下载用） | -¥30 |
| ICE渲染 | ¥100（文字快剪） | ¥0（本地处理） | ¥100 |
| **总计** | **¥200/月** | **¥70/月** | **¥130（65%）** |

### 8.2 并发能力对比

| 指标 | 当前架构 | 客户端渲染 |
|------|---------|-----------|
| 同时转码 | 1-2人 | 无限（各用各的设备） |
| 同时拼接 | 3-5人 | 无限 |
| 同时播放 | 5-10人 | 无限（本地Blob URL） |
| 服务器负载 | 100% | 10%（纯API） |

---

## 九、核心代码结构

```
frontend/src/
├── utils/
│   ├── ffmpeg.ts              # FFmpeg WASM 封装
│   ├── opfs.ts                # OPFS 存储封装
│   ├── indexedDB.ts           # IndexedDB 降级存储
│   ├── clientMaterialProcessor.ts  # 素材本地处理
│   ├── clientRenderer.ts      # 客户端拼接渲染
│   ├── clientExport.ts        # 客户端导出上传
│   └── deviceCapability.ts    # 设备能力检测
├── components/
│   ├── MaterialUploader/      # 改造上传组件
│   ├── CombinationGrid/       # 纯前端组合生成
│   ├── ClientVideoPlayer/     # Blob URL播放器
│   └── ExportManager/         # 导出管理
└── hooks/
    ├── useFFmpeg.ts           # FFmpeg 状态管理
    ├── useOPFS.ts             # OPFS 状态管理
    └── useClientRendering.ts  # 客户端渲染主控
```

---

## 十、总结

### 10.1 核心改变

| 环节 | 之前 | 之后 |
|------|------|------|
| 素材上传 | 传到服务器 | **本地处理，只传元数据** |
| 素材转码 | 服务器ffmpeg | **浏览器FFmpeg WASM** |
| 组合生成 | 服务器计算 | **纯前端JavaScript** |
| 视频拼接 | 服务器ffmpeg | **浏览器FFmpeg WASM** |
| 视频播放 | 服务器传输 | **本地Blob URL** |
| 文字快剪 | 阿里云ICE | **浏览器WebCodecs** |
| 导出下载 | 从OSS获取 | **浏览器生成直传OSS** |

### 10.2 关键收益

1. **成本降低65%**：从¥200/月降到¥70/月
2. **并发无限**：每个用户用自己的设备
3. **速度更快**：本地处理，零网络延迟
4. **体验更好**：秒级预览，毫秒级快剪

### 10.3 实施建议

1. **先上CDN**（本周）：解决当前播放卡顿
2. **客户端转码**（下周）：释放服务器转码压力
3. **客户端拼接**（第3周）：实现秒级预览
4. **WebCodecs快剪**（第4周）：完整闭环

### 10.4 一句话总结

> **把视频处理从服务器搬到用户浏览器，让每个用户用自己的设备做计算，服务器只做协调，实现零成本无限并发。**

---

*文档版本: 1.0*  
*更新日期: 2026-04-24*  
*下一步：评审方案，确定实施优先级*
