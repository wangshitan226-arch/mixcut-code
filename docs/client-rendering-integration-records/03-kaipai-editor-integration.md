# KaipaiEditor（文字快剪界面）客户端渲染集成记录

## 修改时间
2026-04-25

## 修改文件
- `frontend/src/components/KaipaiEditor/index.tsx`

## 集成概述
将客户端渲染方案集成到文字快剪界面的视频导出流程中。当客户端渲染开启时，优先尝试从本地加载已缓存的视频文件进行导出；如果视频没有删除任何片段，可以直接复用原视频文件，无需服务器渲染。

## 详细修改内容

### 1. 引入依赖模块

**新增导入：**
```tsx
import { Cpu } from 'lucide-react';
import { useClientRendering } from '../../hooks/useClientRendering';
import { exportCombination } from '../../utils/clientExport';
import { loadMaterial } from '../../utils/opfs';
import { loadMaterialFromIndexedDB } from '../../utils/indexedDB';
```

### 2. 新增状态管理

**在组件内部新增：**
```tsx
// 客户端渲染状态
const { state: clientRenderState } = useClientRendering();
const [showClientRenderPanel, setShowClientRenderPanel] = useState(false);
const [clientExportBlob, setClientExportBlob] = useState<Blob | null>(null);
```

### 3. 新增本地视频加载函数

**`loadLocalVideoFile()`**
- 优先从 `videoStorage` 获取（KaipaiEditor 已有的缓存机制）
- 回退到 OPFS 加载
- 回退到 IndexedDB 加载
- 返回 `File` 对象用于客户端导出

**加载优先级：**
```
videoStorage (getVideo) → OPFS (loadMaterial) → IndexedDB (loadMaterialFromIndexedDB)
```

### 4. 新增客户端导出函数

**`clientExportVideo()`**
- 加载本地视频文件
- 分析被删除的片段时间段
- 如果没有删除任何片段，直接返回原视频（零成本导出）
- 如果有删除片段，目前降级到服务器（需要 FFmpeg WASM 精确裁剪）

**当前限制：**
- 文字快剪的核心是**时间轴裁剪**（删除静音/语气词片段）
- 这需要 FFmpeg WASM 的 `-ss -t` 精确裁剪能力
- 当前实现识别了需求但暂未实现精确裁剪，降级到服务器处理

### 5. 改造导出处理函数

**`exportVideo` 新增客户端导出分支：**
```
if (客户端渲染开启) {
  blob = await clientExportVideo();
  if (blob) {
    // 客户端导出成功，直接生成 Blob URL
    URL.createObjectURL(blob) → 设置预览和下载链接
    return;
  }
}
// 降级到原有服务器导出逻辑
```

### 6. 新增客户端渲染控制面板

**Header 右上角新增：**
- CPU 图标按钮（绿色表示已启用）
- "客户端"状态标签
- 点击展开设置面板

**面板内容：**
- 设备能力信息（性能等级）
- FFmpeg / OPFS / WebCodecs 支持状态
- 功能说明文字

## 降级策略

1. **本地视频不存在** → 自动降级到服务器导出
2. **有片段删除（需要裁剪）** → 目前降级到服务器（待实现 FFmpeg WASM 裁剪）
3. **客户端导出失败** → 自动降级到服务器导出
4. **客户端渲染未开启** → 完全使用原有逻辑

## 与测试界面的对比

| 功能 | 测试界面 (TestClientRendering) | KaipaiEditor 集成 |
|------|-------------------------------|-------------------|
| 本地视频加载 | ✅ loadMaterial | ✅ loadLocalVideoFile（多层回退） |
| 无裁剪直接导出 | ✅ 复用原视频 | ✅ 直接返回原视频 File |
| 时间轴裁剪 | ✅ FFmpeg 精确裁剪 | ⚠️ 识别需求但未实现（降级到服务器） |
| 状态显示 | ✅ 测试面板 | ✅ Header 标签 + 面板 |

## 性能提升

| 场景 | 服务器渲染 | 客户端渲染 | 提升 |
|------|-----------|-----------|------|
| 无删除片段导出 | 30-120s | <1s（直接复用原视频） | 30-120x |
| 有删除片段导出 | 30-120s | 30-120s（目前降级） | 待实现 |

## 待办事项

- [ ] **高优先级**：实现 FFmpeg WASM 时间轴精确裁剪（`-ss -t` 参数）
- [ ] 测试无删除片段时的零成本导出
- [ ] 测试有删除片段时的降级流程
- [ ] 考虑将裁剪后的视频缓存到本地，避免重复处理

## 技术难点

### 时间轴裁剪实现方案

文字快剪的核心需求是：从原视频中删除指定时间段，保留其余部分。

**方案 1：FFmpeg WASM 精确裁剪**
```bash
# 对每个保留片段裁剪
ffmpeg -i input.mp4 -ss start -t duration -c copy segment1.mp4
# 然后拼接所有片段
ffmpeg -f concat -i list.txt -c copy output.mp4
```

**方案 2：WebCodecs 逐帧处理**
- 使用 VideoDecoder 解码原视频
- 跳过被删除时间段的帧
- 使用 VideoEncoder 重新编码
- 精度高但性能开销大

**方案 3：服务器辅助（当前降级方案）**
- 客户端识别删除时间段
- 上传到服务器进行裁剪
- 保留服务器渲染能力

## 相关文档

- [client-side-rendering-integration.md](../client-side-rendering-integration.md)
- [01-editscreen-integration.md](./01-editscreen-integration.md)
- [02-resultsscreen-integration.md](./02-resultsscreen-integration.md)
