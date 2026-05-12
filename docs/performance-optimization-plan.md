# MixCut 性能优化完整方案

> 解决服务器部署后视频播放卡顿、预览延迟数十秒的问题
> 
> 文档版本: 2.0（已更新 WebCodecs 预览方案）
> 更新日期: 2026-04-24

---

## 一、问题诊断

### 1.1 核心问题

**现状：** 本地运行流畅，服务器部署后视频播放卡顿、预览延迟数十秒

**根本原因：**
```
本地快：本地磁盘读取 (500MB/s+) → 直接播放
服务器慢：OSS下载 (1-10MB/s) → 等待下载完成 → 播放
```

**关键认知：**
- 不是 FFmpeg 合成慢（合成很快）
- 不是服务器性能差
- 是「远程视频下载慢」导致的播放延迟

### 1.2 具体场景分析

| 场景 | 当前实现 | 问题 |
|------|----------|------|
| 混剪结果预览 | 点击后下载完整视频 | 100MB视频需等待10-100秒 |
| 文字快剪预览 | 跳过删除段播放 | 跳转变卡顿，体验差 |
| 时间轴浏览 | 无预览 | 无法快速定位 |

---

## 二、优化目标

### 2.1 性能指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 混剪结果首屏加载 | 10-100秒 | <3秒 |
| 文字快剪预览响应 | 跳转卡顿 | 毫秒级响应 |
| 时间轴浏览 | 无预览 | 零延迟预览 |
| 二次播放 | 重新下载 | 零延迟（本地缓存） |

### 2.2 用户体验目标

- 点击播放后 3 秒内开始播放
- 删除/撤回操作立即看到效果（<100ms）
- 时间轴拖动流畅，无卡顿

---

## 三、架构优化方案

### 3.1 核心思想：预览与导出分离

```
预览阶段（本地）：
用户上传视频 → 浏览器本地缓存 → WebCodecs解码播放 → 只渲染保留片段
                                    ↓
                              毫秒级响应，无缝播放

导出阶段（云端）：
点击导出 → 提交原视频OSS URL + 删除节点数据 → 阿里云处理
              ↓
        和当前实现一致
```

**关键洞察：** 预览和导出是两个独立场景，可以用不同技术方案

### 3.2 双轨存储架构

**OSS 用于导出处理，本地用于预览播放**

```
上传视频
    ↓
[后端] ① 保存原始文件 → 上传OSS（给导出时用）
       ② 返回视频信息（包含OSS URL）
    ↓
[前端] ① 下载视频到浏览器本地存储（OPFS/Cache API）
       ② WebCodecs解码播放（预览时）
       ③ 导出时使用OSS URL（提交阿里云）
```

---

## 四、具体实施方案

### 阶段1：WebCodecs 本地预览（P0，推荐方案）

#### 4.1.1 后端改造

**文件：** `backend/routes/upload.py`

```python
@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    # ... 原有上传逻辑 ...
    
    # 上传到OSS（给导出时用）
    oss_url = oss_client.upload_file(filepath)
    
    # 同时返回本地访问URL（给WebCodecs预览用）
    return jsonify({
        'id': material_id,
        'original_url': f'/uploads/{filename}',  # 本地URL，给WebCodecs用
        'oss_url': oss_url,                       # OSS URL，给导出用
        # ... 其他字段
    })
```

#### 4.1.2 前端本地缓存

**文件：** `frontend/src/utils/opfs.ts`（新增）

```typescript
// 使用 OPFS (Origin Private File System) 存储大文件

const DB_NAME = 'MixCutVideos';
const STORE_NAME = 'videos';

// 保存视频到本地存储
export async function saveVideoToLocal(
  id: string, 
  file: File
): Promise<void> {
  // 方式1: 使用 IndexedDB（推荐，兼容性好）
  return saveToIndexedDB(id, file);
  
  // 方式2: 使用 OPFS（Chrome/Edge，性能更好）
  // return saveToOPFS(id, file);
}

async function saveToIndexedDB(id: string, file: File): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      
      const putRequest = store.put({
        id,
        file,
        timestamp: Date.now(),
        size: file.size
      });
      
      putRequest.onsuccess = () => resolve();
      putRequest.onerror = () => reject(putRequest.error);
    };
    
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    };
  });
}

async function saveToOPFS(id: string, file: File): Promise<void> {
  const root = await navigator.storage.getDirectory();
  const fileHandle = await root.getFileHandle(`video_${id}.mp4`, { create: true });
  
  const writable = await fileHandle.createWritable();
  await writable.write(file);
  await writable.close();
}

// 从本地存储获取视频
export async function getVideoFromLocal(id: string): Promise<File | null> {
  try {
    // 优先尝试 IndexedDB
    const file = await getFromIndexedDB(id);
    if (file) return file;
    
    // 回退到 OPFS
    return await getFromOPFS(id);
  } catch {
    return null;
  }
}

async function getFromIndexedDB(id: string): Promise<File | null> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    
    request.onsuccess = () => {
      const db = request.result;
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const getRequest = store.get(id);
      
      getRequest.onsuccess = () => {
        resolve(getRequest.result?.file || null);
      };
      getRequest.onerror = () => reject(getRequest.error);
    };
    
    request.onerror = () => resolve(null);
  });
}

async function getFromOPFS(id: string): Promise<File | null> {
  try {
    const root = await navigator.storage.getDirectory();
    const fileHandle = await root.getFileHandle(`video_${id}.mp4`);
    return await fileHandle.getFile();
  } catch {
    return null;
  }
}

// 清理旧视频（LRU策略）
export async function cleanupVideos(maxSize = 500 * 1024 * 1024): Promise<void> {
  const request = indexedDB.open(DB_NAME, 1);
  
  request.onsuccess = () => {
    const db = request.result;
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const getAllRequest = store.getAll();
    
    getAllRequest.onsuccess = () => {
      const videos = getAllRequest.result;
      const totalSize = videos.reduce((sum, v) => sum + v.size, 0);
      
      if (totalSize > maxSize) {
        // 按时间排序，删除最旧的
        videos.sort((a, b) => a.timestamp - b.timestamp);
        
        let currentSize = totalSize;
        const deleteTransaction = db.transaction([STORE_NAME], 'readwrite');
        const deleteStore = deleteTransaction.objectStore(STORE_NAME);
        
        for (const video of videos) {
          if (currentSize <= maxSize * 0.8) break;
          deleteStore.delete(video.id);
          currentSize -= video.size;
        }
      }
    };
  };
}
```

#### 4.1.3 WebCodecs 播放器

**文件：** `frontend/src/components/KaipaiEditor/WebCodecsPlayer.tsx`（新增）

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import MP4Box from 'mp4box';

interface Segment {
  id: string;
  beginTime: number;
  endTime: number;
}

interface WebCodecsPlayerProps {
  videoFile: File;
  segments: Segment[];
  removedIds: Set<string>;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: string | null) => void;
}

export default function WebCodecsPlayer({
  videoFile,
  segments,
  removedIds,
  onTimeUpdate,
  onSegmentChange
}: WebCodecsPlayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const decoderRef = useRef<VideoDecoder | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const frameQueueRef = useRef<VideoFrame[]>([]);
  const animationRef = useRef<number>();
  
  // 计算保留的时间段
  const keepSegments = segments.filter(s => !removedIds.has(s.id));
  
  useEffect(() => {
    initDecoder();
    return () => {
      decoderRef.current?.close();
      cancelAnimationFrame(animationRef.current);
    };
  }, [videoFile]);
  
  // 当删除状态改变时，重新计算时长
  useEffect(() => {
    const virtualDuration = keepSegments.reduce(
      (sum, seg) => sum + (seg.endTime - seg.beginTime), 
      0
    );
    setDuration(virtualDuration);
  }, [keepSegments]);
  
  const initDecoder = async () => {
    const buffer = await videoFile.arrayBuffer();
    
    const mp4box = MP4Box.createFile();
    
    mp4box.onReady = (info) => {
      const track = info.videoTracks[0];
      
      decoderRef.current = new VideoDecoder({
        output: (frame) => {
          frameQueueRef.current.push(frame);
        },
        error: (e) => console.error('解码错误:', e)
      });
      
      decoderRef.current.configure({
        codec: track.codec,
        description: track.description,
        hardwareAcceleration: 'prefer-hardware'
      });
      
      mp4box.setExtractionOptions(track.id);
      mp4box.start();
    };
    
    mp4box.onSamples = (trackId, ref, samples) => {
      for (const sample of samples) {
        const chunk = new EncodedVideoChunk({
          type: sample.is_sync ? 'key' : 'delta',
          timestamp: sample.cts,
          data: sample.data
        });
        decoderRef.current?.decode(chunk);
      }
    };
    
    const arrayBuffer = new Uint8Array(buffer);
    (arrayBuffer as any).fileStart = 0;
    mp4box.appendBuffer(arrayBuffer);
  };
  
  // 渲染循环
  const renderLoop = useCallback(() => {
    if (!isPlaying || !canvasRef.current) {
      animationRef.current = requestAnimationFrame(renderLoop);
      return;
    }
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // 获取当前应该显示的帧
    const now = performance.now();
    const frame = frameQueueRef.current.shift();
    
    if (frame) {
      const timestamp = frame.timestamp / 1000; // 毫秒
      
      // 检查是否在保留时间段内
      const inKeepSegment = keepSegments.some(
        seg => timestamp >= seg.beginTime && timestamp <= seg.endTime
      );
      
      if (inKeepSegment) {
        // 渲染帧
        ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
        setCurrentTime(timestamp);
        onTimeUpdate?.(timestamp);
        
        // 通知当前片段
        const currentSeg = segments.find(
          s => timestamp >= s.beginTime && timestamp <= s.endTime
        );
        onSegmentChange?.(currentSeg?.id || null);
      }
      
      frame.close(); // 必须释放
    }
    
    animationRef.current = requestAnimationFrame(renderLoop);
  }, [isPlaying, keepSegments, segments, onTimeUpdate, onSegmentChange]);
  
  useEffect(() => {
    animationRef.current = requestAnimationFrame(renderLoop);
    return () => cancelAnimationFrame(animationRef.current);
  }, [renderLoop]);
  
  // 播放控制
  const togglePlay = () => setIsPlaying(!isPlaying);
  
  // Seek到指定时间
  const seekTo = (time: number) => {
    // 找到对应时间点的关键帧，重新解码
    // ... 实现seek逻辑
  };
  
  return (
    <div className="relative w-full h-full">
      <canvas 
        ref={canvasRef}
        width={1080}
        height={1920}
        className="w-full h-full object-contain bg-black"
        onClick={togglePlay}
      />
      
      {/* 播放控制UI */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex items-center gap-4">
          <button 
            onClick={togglePlay}
            className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center text-white"
          >
            {isPlaying ? '❚❚' : '▶'}
          </button>
          
          <div className="flex-1">
            <div className="text-white text-sm">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
            {/* 进度条 */}
            <div className="mt-2 h-1 bg-white/30 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 transition-all"
                style={{ width: `${(currentTime / duration) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTime(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
```

#### 4.1.4 浏览器兼容性检测

**文件：** `frontend/src/utils/webcodecs.ts`（新增）

```typescript
// 检测 WebCodecs 支持
export function isWebCodecsSupported(): boolean {
  return (
    typeof VideoDecoder !== 'undefined' &&
    typeof VideoEncoder !== 'undefined' &&
    typeof EncodedVideoChunk !== 'undefined' &&
    typeof VideoFrame !== 'undefined'
  );
}

// 检测 OPFS 支持
export function isOPFSSupported(): boolean {
  return typeof navigator.storage?.getDirectory === 'function';
}

// 获取推荐方案
export function getRecommendedPlayer(): 'webcodecs' | 'fallback' {
  if (isWebCodecsSupported()) {
    return 'webcodecs';
  }
  return 'fallback';
}
```

#### 4.1.5 降级方案（传统播放器）

**文件：** `frontend/src/components/KaipaiEditor/FallbackPlayer.tsx`（新增）

```typescript
// 当 WebCodecs 不支持时的回退方案
// 使用虚拟时间轴映射 + 跳转方式
import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { VirtualTimelineMapper } from '../../utils/virtualTimeline';

interface FallbackPlayerProps {
  videoUrl: string;
  segments: Segment[];
  removedIds: Set<string>;
  onTimeUpdate?: (time: number) => void;
}

export default function FallbackPlayer({
  videoUrl,
  segments,
  removedIds,
  onTimeUpdate
}: FallbackPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [virtualTime, setVirtualTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const timeMapper = useMemo(() => {
    return new VirtualTimelineMapper(segments, removedIds);
  }, [segments, removedIds]);
  
  // 播放循环（检测并跳过删除段）
  useEffect(() => {
    if (!isPlaying || !videoRef.current) return;
    
    let animationFrameId: number;
    
    const loop = () => {
      const video = videoRef.current;
      if (!video) return;
      
      const originalTime = video.currentTime * 1000;
      const virtualTimeNow = timeMapper.originalToVirtual(originalTime);
      
      if (virtualTimeNow === null) {
        // 在被删除片段中，跳转
        const nextValid = timeMapper.getNextValidTime(originalTime);
        if (nextValid !== null) {
          video.currentTime = nextValid / 1000;
        } else {
          setIsPlaying(false);
        }
      } else {
        setVirtualTime(virtualTimeNow);
        onTimeUpdate?.(virtualTimeNow);
      }
      
      animationFrameId = requestAnimationFrame(loop);
    };
    
    animationFrameId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animationFrameId);
  }, [isPlaying, timeMapper, onTimeUpdate]);
  
  return (
    <div className="relative">
      <video
        ref={videoRef}
        src={videoUrl}
        className="w-full h-full"
        playsInline
        onClick={() => setIsPlaying(!isPlaying)}
      />
      {/* 控制UI */}
    </div>
  );
}
```

#### 4.1.6 统一播放器组件

**文件：** `frontend/src/components/KaipaiEditor/UnifiedPlayer.tsx`（新增）

```typescript
import { useEffect, useState } from 'react';
import { isWebCodecsSupported, getVideoFromLocal } from '../../utils/opfs';
import WebCodecsPlayer from './WebCodecsPlayer';
import FallbackPlayer from './FallbackPlayer';

interface UnifiedPlayerProps {
  videoId: string;
  videoUrl: string;  // OSS URL，用于降级
  segments: Segment[];
  removedIds: Set<string>;
  onTimeUpdate?: (time: number) => void;
}

export default function UnifiedPlayer(props: UnifiedPlayerProps) {
  const { videoId, videoUrl, ...otherProps } = props;
  const [localFile, setLocalFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    // 尝试从本地获取视频
    getVideoFromLocal(videoId).then(file => {
      if (file) {
        setLocalFile(file);
      }
      setIsLoading(false);
    });
  }, [videoId]);
  
  if (isLoading) {
    return <div className="loading">加载中...</div>;
  }
  
  // 有本地文件且支持 WebCodecs → 使用 WebCodecs
  if (localFile && isWebCodecsSupported()) {
    return <WebCodecsPlayer videoFile={localFile} {...otherProps} />;
  }
  
  // 否则使用降级方案
  return <FallbackPlayer videoUrl={videoUrl} {...otherProps} />;
}
```

**预期效果：** 
- Chrome/Edge 用户：WebCodecs 无缝播放，毫秒级响应
- 其他浏览器用户：降级到跳转方案，仍有改善

---

### 阶段2：低码率预览版（备用方案）

当 WebCodecs 不可行时，作为降级方案

#### 4.2.1 后端生成低码率版

```python
def transcode_to_preview(input_path, output_path):
    """生成低码率预览版本"""
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', 'scale=480:-2',
        '-c:v', 'libx264',
        '-crf', '28',
        '-preset', 'fast',
        '-b:v', '800k',
        '-c:a', 'aac',
        '-b:a', '96k',
        '-movflags', '+faststart',
        output_path
    ]
    subprocess.run(cmd, capture_output=True, text=True)
```

#### 4.2.2 前端缓存

```typescript
// 使用 Cache API 缓存低码率视频
const cache = await caches.open('video-cache');
const response = await fetch(previewUrl);
await cache.put(previewUrl, response);
```

---

### 阶段3：时间轴帧图预览（P1）

同原方案，略

---

## 五、数据流对比

### 原方案

```
上传 → OSS存储 → 预览时下载 → 跳转播放（卡顿）
                ↓
        导出时用同一个OSS URL
```

### 新方案（WebCodecs）

```
上传 → OSS存储（导出用）
    → 浏览器本地缓存（预览用）
                ↓
        预览：WebCodecs 本地解码，只渲染保留片段（流畅）
        导出：OSS URL + 删除节点 → 阿里云（功能完整）
```

---

## 六、浏览器兼容性

| 浏览器 | WebCodecs | OPFS | 推荐方案 |
|--------|-----------|------|----------|
| Chrome 94+ | ✅ | ✅ | WebCodecs + OPFS |
| Edge 94+ | ✅ | ✅ | WebCodecs + OPFS |
| Firefox | ⚠️ 部分 | ❌ | 降级方案 |
| Safari | ❌ | ❌ | 降级方案 |

**覆盖率：** 约 70% 用户可用 WebCodecs，30% 用降级方案

---

## 七、实施计划

### 第一周：WebCodecs 基础功能

| 天数 | 任务 | 产出 |
|------|------|------|
| 1-2 | 本地存储工具（OPFS/IndexedDB） | `opfs.ts` |
| 2-3 | WebCodecs 播放器基础 | `WebCodecsPlayer.tsx` |
| 3-4 | 降级方案播放器 | `FallbackPlayer.tsx` |
| 4-5 | 统一播放器组件 | `UnifiedPlayer.tsx` |
| 5-7 | 集成测试 | 预览延迟 <100ms |

### 第二周：优化与完善

| 天数 | 任务 | 产出 |
|------|------|------|
| 1-2 | Seek功能实现 | 精确跳转 |
| 2-3 | 音频同步 | 音画同步播放 |
| 3-4 | 性能优化 | 内存管理优化 |
| 4-5 | 帧图时间轴 | `Timeline.tsx` |
| 5-7 | 全面测试 | 兼容性测试 |

---

## 八、预期效果

### 8.1 性能提升

| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| 文字快剪预览响应 | 跳转卡顿 | <100ms | 实时 |
| 删除/撤回反馈 | 需重新合成 | 立即生效 | 毫秒级 |
| 播放流畅度 | 频繁跳转 | 无缝播放 | 接近APP |

### 8.2 用户体验

- ✅ Chrome/Edge 用户：丝滑流畅的剪辑体验
- ✅ 其他浏览器用户：仍有改善的降级体验
- ✅ 删除/撤回操作立即看到效果
- ✅ 无需等待视频重新合成

---

## 九、风险与应对

| 风险 | 可能性 | 应对措施 |
|------|--------|----------|
| WebCodecs 兼容性 | 中 | 完善的降级方案，自动检测切换 |
| 大视频内存占用 | 中 | 及时释放 VideoFrame，限制缓存大小 |
| 音频处理复杂 | 中 | 第一阶段可先实现视频，音频用 Web Audio API |
| 开发时间超预期 | 中 | 分阶段实施，基础功能优先 |

---

## 十、总结

**核心思路：**
1. **预览与导出分离** - 预览用本地 WebCodecs，导出用阿里云
2. **本地优先** - 视频缓存到浏览器，零延迟播放
3. **渐进增强** - WebCodecs 支持则体验最佳，不支持则降级

**关键认知：**
- WebCodecs 不是替代方案，是增强方案
- 70% 用户可获得 APP 级体验
- 30% 用户仍有改善的降级体验

**下一步行动：**
1. 评审本方案
2. 开始第一周开发（WebCodecs 基础功能）
3. 同步准备降级方案
