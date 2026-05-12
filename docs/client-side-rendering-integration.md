# 客户端渲染集成文档

## 概述

本文档描述如何将客户端渲染功能集成到 MixCut 现有流程中。

## 已完成工作

### 第一阶段：基础能力 ✅
- FFmpeg WASM 集成（`ffmpeg.ts`）
- OPFS/IndexedDB 存储（`opfs.ts`, `indexedDB.ts`）
- 素材本地转码（`clientMaterialProcessor.ts`）
- WebCodecs 快速转码（`webcodecsTranscoder.ts`）
- 设备能力检测（`deviceCapability.ts`）

### 第二阶段：核心功能 ✅
- 前端组合生成（`combinationGenerator.ts`）
- 客户端拼接渲染（`clientRenderer.ts`）
- 秒级拼接（copy 模式）
- 预览播放

### 第三阶段：导出功能 ✅
- 本地导出（`clientExport.ts`）
- 使用已有拼接结果（不重新编码）
- OSS 上传模拟

### 第四阶段：集成组件 ✅
- 客户端渲染主控 Hook（`useClientRendering.ts`）
- 客户端渲染开关（`ClientRenderingToggle.tsx`）
- 客户端素材上传器（`ClientMaterialUploader.tsx`）
- ASR 对比测试（`ASRComparisonTest.tsx`）

## 集成步骤

### 1. 添加客户端渲染开关

在设置页面或编辑页面添加 `ClientRenderingToggle` 组件：

```tsx
import ClientRenderingToggle from './components/ClientRenderingToggle';
import { useClientRendering } from './hooks/useClientRendering';

function SettingsPage() {
  const { state, enable, disable, forceEnable } = useClientRendering();

  return (
    <ClientRenderingToggle
      capability={state.capability}
      isEnabled={state.isEnabled}
      isForced={state.isForced}
      onEnable={enable}
      onDisable={disable}
      onForceEnable={forceEnable}
    />
  );
}
```

### 2. 改造上传流程

在 `EditScreen` 中使用 `ClientMaterialUploader` 替代原有上传：

```tsx
import ClientMaterialUploader from './components/ClientMaterialUploader';

// 在 EditScreen 中
{state.isEnabled ? (
  <ClientMaterialUploader
    userId={userId}
    shotId={shot.id}
    onUploadComplete={(material) => {
      // 添加到本地素材列表
      addLocalMaterial(material);
    }}
    onError={(error) => alert(error)}
  />
) : (
  // 原有上传逻辑
)}
```

### 3. 改造结果页面

在 `ResultsScreen` 中使用本地渲染：

```tsx
import { useClientRendering } from './hooks/useClientRendering';

function ResultsScreen() {
  const { state, renderPreview, exportVideo } = useClientRendering();

  const handlePreview = async (combination) => {
    if (state.isEnabled) {
      // 客户端渲染
      const result = await renderPreview(combination);
      setVideoUrl(result.blobUrl);
    } else {
      // 服务器渲染
      const result = await fetchServerRender(combination);
      setVideoUrl(result.url);
    }
  };

  const handleExport = async (combination) => {
    if (state.isEnabled) {
      // 客户端导出
      const result = await exportVideo(combination, 'hd');
      setVideoUrl(result.blobUrl);
    } else {
      // 服务器导出
      const result = await fetchServerExport(combination);
      setVideoUrl(result.url);
    }
  };
}
```

### 4. 后端接口改造

#### 4.1 素材元数据上传接口

```python
# backend/routes/materials.py
@app.route('/api/materials/metadata', methods=['POST'])
def upload_material_metadata():
    user_id = request.form.get('user_id')
    shot_id = request.form.get('shot_id')
    material_id = request.form.get('material_id')
    duration = request.form.get('duration')
    width = request.form.get('width')
    height = request.form.get('height')
    file_size = request.form.get('file_size')
    
    # 保存缩略图
    thumbnail = request.files.get('thumbnail')
    thumbnail_url = save_thumbnail(thumbnail) if thumbnail else None
    
    # 保存素材元数据（视频在客户端本地）
    material = Material(
        id=material_id,
        user_id=user_id,
        shot_id=shot_id,
        duration=duration,
        width=width,
        height=height,
        file_size=file_size,
        thumbnail_url=thumbnail_url,
        is_local=True,  # 标记为本地素材
        status='ready',  # 无需转码
    )
    db.session.add(material)
    db.session.commit()
    
    return jsonify({
        'id': material_id,
        'thumbnail_url': thumbnail_url,
        'status': 'ready',
    })
```

#### 4.2 修改现有上传接口

在 `upload.py` 中检测是否使用客户端渲染：

```python
@app.route('/api/upload', methods=['POST'])
def upload_file():
    # ... 原有逻辑 ...
    
    # 检查是否使用客户端渲染
    use_client_rendering = request.form.get('use_client_rendering') == 'true'
    
    if use_client_rendering:
        # 客户端渲染模式：只保存原始文件，不转码
        # 转码在客户端完成
        pass
    else:
        # 服务器渲染模式：原有逻辑
        pass
```

### 5. 数据流改造

#### 原有流程
```
用户上传视频 → 服务器转码 → 保存到 OSS → 返回 URL
                ↓
            文字快剪：上传 OSS → ASR → 编辑 → 导出
                ↓
            组合生成：服务器计算 → 返回组合
                ↓
            渲染：服务器拼接 → 返回视频 URL
```

#### 客户端渲染流程
```
用户上传视频 → 客户端转码 → 保存到本地 OPFS
                ↓
            上传元数据到服务器（缩略图、时长等）
                ↓
            组合生成：前端计算（秒级）
                ↓
            渲染预览：客户端拼接（秒级，copy 模式）
                ↓
            文字快剪：上传到 OSS → ASR → 编辑 → 导出
                ↓
            导出：使用已有拼接结果（秒级）或重新编码
```

## 文件结构

```
frontend/src/
├── utils/
│   ├── ffmpeg.ts                    # FFmpeg WASM 封装
│   ├── opfs.ts                      # OPFS 存储
│   ├── indexedDB.ts                 # IndexedDB 降级存储
│   ├── clientMaterialProcessor.ts   # 素材本地处理
│   ├── webcodecsTranscoder.ts      # WebCodecs 快速转码
│   ├── clientRenderer.ts           # 客户端渲染
│   ├── clientExport.ts             # 本地导出
│   ├── combinationGenerator.ts     # 组合生成
│   ├── deviceCapability.ts         # 设备能力检测
│   ├── mobileForceEnable.ts        # 移动端强制启用
│   └── videoValidator.ts           # 视频验证
├── hooks/
│   └── useClientRendering.ts       # 客户端渲染主控 Hook
├── components/
│   ├── ClientRenderingToggle.tsx   # 客户端渲染开关
│   ├── ClientMaterialUploader.tsx  # 客户端素材上传器
│   ├── ClientResultsScreen.tsx     # 客户端结果页面（可选）
│   └── ASRComparisonTest.tsx       # ASR 对比测试
└── App.tsx                          # 主应用（集成测试入口）
```

## 配置项

### Vite 配置（vite.config.ts）

```typescript
export default defineConfig({
  // ... 其他配置 ...
  optimizeDeps: {
    exclude: ['@ffmpeg/ffmpeg', '@ffmpeg/util'],
  },
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
});
```

### 环境变量（.env）

```
VITE_API_URL=http://localhost:3002
VITE_ENABLE_CLIENT_RENDERING=true
VITE_MAX_FILE_SIZE=52428800  # 50MB
```

## 性能对比

| 操作 | 服务器渲染 | 客户端渲染 | 提升 |
|------|-----------|-----------|------|
| 素材转码 | 10-30s | 5-20s (WebCodecs) | 2-5x |
| 组合生成 | 1-5s | <100ms | 10-50x |
| 渲染预览 | 10-60s | <1s (copy) | 10-60x |
| 导出视频 | 30-120s | <1s (已有结果) | 30-120x |

## 浏览器支持

| 浏览器 | 支持状态 | 说明 |
|--------|---------|------|
| Chrome 94+ | ✅ 完整支持 | 推荐 |
| Edge 94+ | ✅ 完整支持 | 推荐 |
| Firefox | ⚠️ 部分支持 | 需手动开启 WebCodecs |
| Safari | ❌ 不支持 | 无 SharedArrayBuffer |
| iOS Chrome | ❌ 不支持 | WebKit 内核限制 |
| Android Chrome | ✅ 支持 | 推荐 |

## 降级策略

当客户端渲染不可用时，自动降级到服务器渲染：

```typescript
const handleRender = async (combination) => {
  try {
    if (state.isEnabled) {
      return await clientRender(combination);
    }
  } catch (error) {
    console.warn('客户端渲染失败，降级到服务器:', error);
  }
  
  // 降级到服务器渲染
  return await serverRender(combination);
};
```

## 注意事项

1. **内存管理**：大文件处理时注意内存使用，及时释放 Blob URL
2. **并发控制**：避免同时处理过多文件，建议单线程处理
3. **错误处理**：客户端渲染失败时自动降级到服务器
4. **移动端**：建议限制文件大小（50MB），使用低质量预设
5. **存储限制**：OPFS 有存储配额限制，需要监控使用情况

## 后续优化

1. **Web Worker**：将转码任务放到 Web Worker 中，避免阻塞 UI
2. **流式处理**：支持大文件分块处理
3. **缓存策略**：优化素材缓存，避免重复转码
4. **增量更新**：只更新修改的部分，减少全量渲染
5. **多线程**：利用多核 CPU 并行处理多个素材
