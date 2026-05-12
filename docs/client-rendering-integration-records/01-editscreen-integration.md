# EditScreen（智能剪辑界面）客户端渲染集成记录

## 修改时间
2026-04-25

## 修改文件
- `frontend/src/components/EditScreen.tsx`

## 集成概述
将客户端渲染方案集成到智能剪辑界面的上传流程中。当客户端渲染开启时，视频素材会在浏览器本地完成转码、缩略图生成和存储，然后只上传元数据到服务器；图片素材仍走原有服务器上传流程。

## 详细修改内容

### 1. 引入依赖模块

**新增导入：**
```tsx
import { Cpu } from 'lucide-react';
import { useClientRendering } from '../hooks/useClientRendering';
import { processMaterial, ProcessedMaterial } from '../utils/clientMaterialProcessor';
import { isOPFSSupported } from '../utils/opfs';
import { isIndexedDBSupported } from '../utils/indexedDB';
```

### 2. 新增状态管理

**在组件内部新增：**
```tsx
// 客户端渲染状态
const { state: clientRenderState, enable: enableClientRender, disable: disableClientRender, forceEnable: forceEnableClientRender } = useClientRendering();
const [clientProcessedMaterials, setClientProcessedMaterials] = useState<Map<string, ProcessedMaterial>>(new Map());
const [showClientRenderPanel, setShowClientRenderPanel] = useState(false);
```

### 3. 新增客户端上传处理函数

**`handleClientSideUpload(file, shotId)`**
- 调用 `processMaterial()` 在本地转码视频
- 使用设备推荐的质量设置
- 生成缩略图
- 上传元数据到 `/api/materials/metadata`
- 视频 Blob 保留在本地 OPFS/IndexedDB
- 失败时自动降级到服务器上传

**流程：**
```
选择视频文件
  → 本地转码 (processMaterial, 进度 0-80%)
  → 上传元数据到服务器 (进度 85%)
  → 刷新镜头列表 (进度 100%)
```

### 4. 重构原有上传逻辑

**将原有 `handleFileSelect` 中的上传逻辑提取为 `handleServerSideUpload(file, shotId)`**
- 保持原有服务器上传行为不变
- 支持 WebSocket 和轮询跟踪转码状态

### 5. 改造文件选择处理

**新的 `handleFileSelect` 逻辑：**
```
if (图片文件) → handleServerSideUpload
if (视频文件 && 客户端渲染开启) → handleClientSideUpload
if (视频文件 && 客户端渲染关闭) → handleServerSideUpload
```

### 6. 新增客户端渲染控制面板

**Header 右上角新增 CPU 图标按钮：**
- 点击展开/收起客户端渲染设置面板
- 显示设备能力检测结果
- 支持启用/禁用切换
- 移动端支持强制启用

**面板内容：**
- 性能等级、内存信息
- 不支持时的原因提示
- FFmpeg / OPFS / WebCodecs 支持状态标签

## 降级策略

1. **元数据接口不存在** → 自动降级到服务器上传
2. **客户端处理失败** → 提示用户后降级到服务器上传
3. **图片文件** → 始终走服务器上传（无需本地转码）

## 与测试界面的对比

| 功能 | 测试界面 (TestClientRendering) | EditScreen 集成 |
|------|-------------------------------|----------------|
| 设备检测 | ✅ detectDeviceCapability | ✅ useClientRendering |
| 本地转码 | ✅ processMaterial | ✅ handleClientSideUpload |
| 元数据上传 | ✅ /api/materials/metadata | ✅ 相同接口 |
| 上传进度 | ✅ 自定义进度 | ✅ 复用 uploading 状态 |
| 渲染开关 | ✅ ClientRenderingToggle | ✅ 内联面板 |
| 降级策略 | ✅ 手动处理 | ✅ 自动降级 |

## 待办事项

- [ ] 后端需要实现 `/api/materials/metadata` 接口
- [ ] 后端 `upload.py` 需要支持 `is_local` 标记
- [ ] 需要测试客户端渲染开启/关闭的切换
- [ ] 需要测试降级流程

## 相关文档

- [client-side-rendering-integration.md](../client-side-rendering-integration.md)
- [client-side-rendering-architecture.md](../client-side-rendering-architecture.md)
