# MixCut 客户端渲染架构 - 阶段1&2 检验指南

> **日期**: 2026-04-24  
> **范围**: 阶段1（基础能力）+ 阶段2（核心功能）  
> **状态**: 待验证  

---

## 一、自动检验（已执行）

### 1.1 文件完整性检查

| 检查项 | 期望结果 | 实际结果 | 状态 |
|--------|----------|----------|------|
| `src/utils/ffmpeg.ts` | 存在 | ✅ 存在 | 通过 |
| `src/utils/opfs.ts` | 存在 | ✅ 存在 | 通过 |
| `src/utils/indexedDB.ts` | 存在 | ✅ 存在 | 通过 |
| `src/utils/deviceCapability.ts` | 存在 | ✅ 存在 | 通过 |
| `src/utils/clientMaterialProcessor.ts` | 存在 | ✅ 存在 | 通过 |
| `src/utils/clientRenderer.ts` | 存在 | ✅ 存在 | 通过 |
| `src/utils/combinationGenerator.ts` | 存在 | ✅ 存在 | 通过 |
| `src/utils/clientExport.ts` | 存在 | ✅ 存在 | 通过 |
| `src/hooks/useFFmpeg.ts` | 存在 | ✅ 存在 | 通过 |
| `src/hooks/useOPFS.ts` | 存在 | ✅ 存在 | 通过 |
| `src/hooks/useClientRendering.ts` | 存在 | ✅ 存在 | 通过 |
| `src/components/ClientMaterialUploader.tsx` | 存在 | ✅ 存在 | 通过 |
| `src/components/ClientResultsScreen.tsx` | 存在 | ✅ 存在 | 通过 |
| `public/ffmpeg/ffmpeg-core.js` | 存在 | ✅ 存在 | 通过 |
| `public/ffmpeg/ffmpeg-core.wasm` | 存在 | ✅ 存在 | 通过 |

### 1.2 TypeScript 类型检查

```bash
cd d:\project\mixcut\frontend
npm run lint
# 结果: tsc --noEmit
# 退出码: 0 ✅
```

**状态**: ✅ 通过 - 无类型错误

---

## 二、手动检验步骤

### 2.1 阶段1基础能力检验

#### 检验 1.1: FFmpeg WASM 加载

**步骤**:
1. 启动开发服务器
   ```bash
   cd d:\project\mixcut\frontend
   npm run dev
   ```

2. 打开浏览器访问 `http://localhost:5173`

3. 打开浏览器控制台 (F12)

4. 在控制台执行:
   ```javascript
   import('./src/utils/ffmpeg.ts').then(m => {
     m.getFFmpeg().then(ffmpeg => {
       console.log('✅ FFmpeg 加载成功');
       console.log('实例:', ffmpeg);
     }).catch(err => {
       console.error('❌ FFmpeg 加载失败:', err);
     });
   });
   ```

**期望结果**:
- 控制台显示 "FFmpeg Loaded successfully"
- `ffmpeg` 实例不为 null
- 网络面板显示 `ffmpeg-core.js` 和 `ffmpeg-core.wasm` 已加载

**常见问题**:
- 如果报错 `SharedArrayBuffer is not defined`，需要配置 COOP/COEP headers
- 如果 WASM 加载失败，检查 `public/ffmpeg/` 目录下文件是否存在

---

#### 检验 1.2: OPFS 存储功能

**步骤**:
1. 在浏览器控制台执行:
   ```javascript
   import('./src/utils/opfs.ts').then(m => {
     // 检查支持
     console.log('OPFS 支持:', m.isOPFSSupported());
     
     // 测试保存
     const testBlob = new Blob(['test'], { type: 'text/plain' });
     m.saveMaterial('test-123', testBlob).then(() => {
       console.log('✅ 保存成功');
       
       // 测试读取
       return m.loadMaterial('test-123');
     }).then(result => {
       console.log('✅ 读取成功:', result);
       
       // 测试删除
       return m.deleteMaterial('test-123');
     }).then(deleted => {
       console.log('✅ 删除成功:', deleted);
     }).catch(err => {
       console.error('❌ OPFS 测试失败:', err);
     });
   });
   ```

**期望结果**:
- `isOPFSSupported()` 返回 `true`（Chrome/Edge）
- 保存、读取、删除都成功
- 控制台显示相应成功日志

---

#### 检验 1.3: 设备能力检测

**步骤**:
1. 在浏览器控制台执行:
   ```javascript
   import('./src/utils/deviceCapability.ts').then(m => {
     m.detectDeviceCapability().then(capability => {
       console.log('设备能力检测结果:');
       console.log('  支持客户端渲染:', capability.canUseClientRendering);
       console.log('  性能等级:', capability.performanceLevel);
       console.log('  支持 OPFS:', capability.supportsOPFS);
       console.log('  支持 FFmpeg:', capability.supportsFFmpeg);
       console.log('  支持 WebCodecs:', capability.supportsWebCodecs);
       console.log('  内存:', capability.memoryGB, 'GB');
       console.log('  CPU 核心:', capability.cpuCores);
       console.log('  推荐质量:', capability.recommendedQuality);
       console.log('  最大文件:', capability.maxFileSize / 1024 / 1024, 'MB');
       
       if (!capability.canUseClientRendering) {
         console.warn('不支持原因:', capability.unsupportedReasons);
       }
     });
   });
   ```

**期望结果**:
- 显示设备详细信息
- `canUseClientRendering` 根据设备返回 true/false
- 如果不支持，显示具体原因

---

#### 检验 1.4: IndexedDB 降级存储

**步骤**:
1. 在浏览器控制台执行:
   ```javascript
   import('./src/utils/indexedDB.ts').then(m => {
     // 检查支持
     console.log('IndexedDB 支持:', m.isIndexedDBSupported());
     
     // 测试保存
     const testBlob = new Blob(['test'], { type: 'text/plain' });
     m.saveMaterialToIndexedDB('test-idb-123', testBlob).then(success => {
       console.log('✅ IndexedDB 保存:', success);
       
       // 测试读取
       return m.loadMaterialFromIndexedDB('test-idb-123');
     }).then(result => {
       console.log('✅ IndexedDB 读取:', result);
       
       // 测试删除
       return m.deleteMaterialFromIndexedDB('test-idb-123');
     }).then(deleted => {
       console.log('✅ IndexedDB 删除:', deleted);
     }).catch(err => {
       console.error('❌ IndexedDB 测试失败:', err);
     });
   });
   ```

**期望结果**:
- `isIndexedDBSupported()` 返回 `true`
- 保存返回 `true`
- 读取返回 `{ video: Blob, thumbnail: Blob }`
- 删除返回 `true`

---

### 2.2 阶段2核心功能检验

#### 检验 2.1: 素材本地处理

**步骤**:
1. 准备一个测试视频文件（建议 10MB 以内）

2. 在浏览器控制台执行:
   ```javascript
   import('./src/utils/clientMaterialProcessor.ts').then(m => {
     // 创建测试文件
     const input = document.createElement('input');
     input.type = 'file';
     input.accept = 'video/*';
     input.onchange = async (e) => {
       const file = e.target.files[0];
       if (!file) return;
       
       console.log('开始处理素材:', file.name, file.size);
       
       try {
         const result = await m.processMaterial(file, {
           quality: 'low',  // 使用低质量加快测试
           onProgress: (progress, stage) => {
             console.log(`  ${stage}: ${Math.round(progress)}%`);
           }
         });
         
         console.log('✅ 处理完成:');
         console.log('  ID:', result.id);
         console.log('  时长:', result.duration);
         console.log('  尺寸:', result.width, 'x', result.height);
         console.log('  大小:', (result.size / 1024 / 1024).toFixed(2), 'MB');
         console.log('  缩略图:', result.thumbnailUrl);
         
       } catch (err) {
         console.error('❌ 处理失败:', err);
       }
     };
     input.click();
   });
   ```

**期望结果**:
- 显示处理进度（0% -> 100%）
- 处理完成后显示素材信息
- 视频 Blob 和缩略图 Blob 都不为 null
- 处理时间根据文件大小，通常 10-60 秒

**性能参考**:
| 文件大小 | 预计处理时间 |
|----------|-------------|
| 5MB | 10-20 秒 |
| 20MB | 30-60 秒 |
| 50MB | 60-120 秒 |

---

#### 检验 2.2: 组合生成

**步骤**:
1. 在浏览器控制台执行:
   ```javascript
   import('./src/utils/combinationGenerator.ts').then(m => {
     // 创建测试数据
     const shots = [
       { id: 'shot1', name: '开场', order: 1 },
       { id: 'shot2', name: '主体', order: 2 },
       { id: 'shot3', name: '结尾', order: 3 },
     ];
     
     const materialsMap = new Map([
       ['shot1', [
         { id: 'mat1', shotId: 'shot1', duration: 3, name: '素材1' },
         { id: 'mat2', shotId: 'shot1', duration: 4, name: '素材2' },
       ]],
       ['shot2', [
         { id: 'mat3', shotId: 'shot2', duration: 5, name: '素材3' },
         { id: 'mat4', shotId: 'shot2', duration: 3, name: '素材4' },
         { id: 'mat5', shotId: 'shot2', duration: 4, name: '素材5' },
       ]],
       ['shot3', [
         { id: 'mat6', shotId: 'shot3', duration: 2, name: '素材6' },
       ]],
     ]);
     
     console.log('开始生成组合...');
     const start = performance.now();
     
     const combinations = m.generateCombinations(shots, materialsMap, {
       limit: 1000,
     });
     
     const duration = performance.now() - start;
     
     console.log(`✅ 生成完成: ${combinations.length} 个组合 (${duration.toFixed(2)}ms)`);
     console.log('前5个组合:');
     combinations.slice(0, 5).forEach((combo, i) => {
       console.log(`  ${i + 1}. ID: ${combo.id}, 时长: ${combo.duration}s, 唯一性: ${combo.uniqueness}%, 标签: ${combo.tag}`);
     });
     
     // 测试智能生成
     const smartCombos = m.generateSmartCombinations(shots, materialsMap, {
       limit: 100,
     });
     console.log(`✅ 智能生成: ${smartCombos.length} 个组合`);
   });
   ```

**期望结果**:
- 生成 6 个组合（2 × 3 × 1）
- 每个组合有正确的时长和唯一性评分
- 生成时间 < 100ms
- 智能生成优先高唯一性组合

---

#### 检验 2.3: 客户端渲染

**前置条件**: 已完成检验 2.1，素材已保存到本地

**步骤**:
1. 在浏览器控制台执行:
   ```javascript
   import('./src/utils/clientRenderer.ts').then(async m => {
     // 使用之前生成的素材 ID
     const materialIds = ['mat_xxx_xxx']; // 替换为实际的素材 ID
     
     const combination = {
       id: 'combo_test_123',
       materials: materialIds.map(id => ({
         id,
         duration: 3,
       })),
     };
     
     console.log('开始渲染预览...');
     const start = performance.now();
     
     try {
       const result = await m.renderPreview(combination, {
         onProgress: (progress, stage) => {
           console.log(`  ${stage}: ${Math.round(progress)}%`);
         }
       });
       
       const duration = performance.now() - start;
       console.log('✅ 渲染完成:');
       console.log('  耗时:', duration.toFixed(2), 'ms');
       console.log('  时长:', result.duration, '秒');
       console.log('  Blob URL:', result.blobUrl);
       
       // 测试播放
       const video = document.createElement('video');
       video.src = result.blobUrl;
       video.controls = true;
       video.style.width = '300px';
       document.body.appendChild(video);
       
     } catch (err) {
       console.error('❌ 渲染失败:', err);
     }
   });
   ```

**期望结果**:
- 渲染时间 1-5 秒（copy 模式）
- 生成有效的 Blob URL
- 视频可以正常播放
- 视频时长正确

---

#### 检验 2.4: React Hooks

**步骤**:
1. 创建一个测试组件文件 `TestComponent.tsx`:

```tsx
import React from 'react';
import { useClientRendering } from './hooks/useClientRendering';

export default function TestComponent() {
  const {
    deviceCapability,
    isDetecting,
    mode,
    setMode,
    isProcessing,
    processingProgress,
    isRendering,
    renderProgress,
    error,
  } = useClientRendering('auto');

  return (
    <div style={{ padding: 20 }}>
      <h2>客户端渲染测试</h2>
      
      <div style={{ marginBottom: 20 }}>
        <h3>设备能力</h3>
        {isDetecting ? (
          <p>检测中...</p>
        ) : deviceCapability ? (
          <div>
            <p>支持客户端渲染: {deviceCapability.canUseClientRendering ? '✅' : '❌'}</p>
            <p>性能等级: {deviceCapability.performanceLevel}</p>
            <p>推荐质量: {deviceCapability.recommendedQuality}</p>
            <p>最大文件: {(deviceCapability.maxFileSize / 1024 / 1024).toFixed(0)}MB</p>
          </div>
        ) : (
          <p>未检测到</p>
        )}
      </div>

      <div style={{ marginBottom: 20 }}>
        <h3>渲染模式</h3>
        <select value={mode} onChange={e => setMode(e.target.value as any)}>
          <option value="auto">自动</option>
          <option value="client">客户端</option>
          <option value="server">服务器</option>
        </select>
      </div>

      {isProcessing && (
        <div>
          <h3>处理中</h3>
          <progress value={processingProgress} max={100} />
          <span>{processingProgress}%</span>
        </div>
      )}

      {isRendering && (
        <div>
          <h3>渲染中</h3>
          <progress value={renderProgress} max={100} />
          <span>{renderProgress}%</span>
        </div>
      )}

      {error && (
        <div style={{ color: 'red' }}>
          <h3>错误</h3>
          <p>{error.message}</p>
        </div>
      )}
    </div>
  );
}
```

2. 在 `App.tsx` 中引入测试组件

3. 查看页面显示:
   - 设备能力信息
   - 渲染模式选择
   - 进度条（处理/渲染时）

**期望结果**:
- 正确显示设备能力
- 可以切换渲染模式
- 处理/渲染时显示进度条
- 错误时显示错误信息

---

#### 检验 2.5: UI 组件

**步骤**:
1. 在 `App.tsx` 中测试 `ClientMaterialUploader`:

```tsx
import ClientMaterialUploader from './components/ClientMaterialUploader';

// 在组件中使用
<ClientMaterialUploader
  userId="test-user"
  shotId={1}
  onUploadComplete={(material) => {
    console.log('上传完成:', material);
    alert(`素材处理完成!\nID: ${material.id}\n时长: ${material.duration}秒`);
  }}
  onError={(error) => {
    console.error('上传失败:', error);
    alert('上传失败: ' + error.message);
  }}
/>
```

2. 测试上传功能:
   - 点击上传按钮
   - 选择视频文件
   - 观察进度显示
   - 等待处理完成

**期望结果**:
- 显示上传/处理进度
- 处理完成后触发 `onUploadComplete`
- 如果设备不支持，自动降级到服务器上传

---

## 三、集成测试

### 3.1 完整流程测试

**目标**: 测试从素材上传到视频渲染的完整流程

**步骤**:
1. 使用 `ClientMaterialUploader` 上传 2-3 个视频素材
2. 记录素材 ID
3. 使用 `combinationGenerator` 生成组合
4. 使用 `ClientResultsScreen` 渲染并播放视频
5. 测试下载功能

**期望结果**:
- 素材成功上传到本地存储
- 组合正确生成
- 视频本地渲染成功
- Blob URL 可以播放
- 可以下载到本地

---

### 3.2 降级测试

**目标**: 测试设备不支持时的降级行为

**步骤**:
1. 在 `useClientRendering` 中强制设置 `mode: 'server'`
2. 重复完整流程测试

**期望结果**:
- 素材上传到服务器（不是本地处理）
- 视频渲染使用服务器 API
- 功能仍然可用

---

## 四、性能测试

### 4.1 渲染性能

**测试方法**:
```javascript
const start = performance.now();
const result = await renderPreview(combination);
const duration = performance.now() - start;
console.log(`渲染耗时: ${duration.toFixed(2)}ms`);
```

**参考标准**:

| 场景 | 优秀 | 良好 | 需优化 |
|------|------|------|--------|
| 预览渲染（3个素材） | < 3秒 | 3-5秒 | > 5秒 |
| 高清渲染（3个素材） | < 15秒 | 15-30秒 | > 30秒 |
| 组合生成（1000个） | < 100ms | 100-500ms | > 500ms |

### 4.2 内存使用

**测试方法**:
1. 打开 Chrome 任务管理器 (Shift+Esc)
2. 观察内存使用
3. 渲染前后对比

**参考标准**:
- 空闲时: < 200MB
- 渲染时: < 1GB
- 渲染后: 回到 < 300MB

---

## 五、问题排查

### 5.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| FFmpeg 加载失败 | COOP/COEP headers 未配置 | 检查 vite.config.ts |
| OPFS 不可用 | 浏览器不支持 | 使用 IndexedDB 降级 |
| 转码失败 | 内存不足 | 降低质量或使用小文件测试 |
| 拼接失败 | 素材格式不一致 | 确保素材都是 MP4 格式 |
| Blob URL 无法播放 | 视频编码问题 | 检查视频编码是否为 H.264 |

### 5.2 调试技巧

1. **查看 FFmpeg 日志**:
   ```javascript
   ffmpeg.on('log', ({ message }) => {
     console.log('[FFmpeg]', message);
   });
   ```

2. **检查 OPFS 内容**:
   ```javascript
   const root = await navigator.storage.getDirectory();
   // 在 Chrome DevTools 中查看
   ```

3. **检查 IndexedDB**:
   - 打开 Chrome DevTools
   - 切换到 Application 标签
   - 查看 IndexedDB -> MixCutFallbackDB

---

## 六、检验清单

### 阶段1检验

- [ ] FFmpeg WASM 可以加载
- [ ] OPFS 可以读写
- [ ] IndexedDB 可以读写
- [ ] 设备能力检测正确
- [ ] TypeScript 类型检查通过

### 阶段2检验

- [ ] 素材可以本地处理（转码+缩略图）
- [ ] 组合可以前端生成
- [ ] 视频可以本地拼接（预览+高清）
- [ ] Blob URL 可以播放
- [ ] 可以导出到 OSS
- [ ] React Hooks 工作正常
- [ ] UI 组件显示正确
- [ ] 降级策略工作正常

### 集成检验

- [ ] 完整流程可以跑通
- [ ] 性能满足要求
- [ ] 内存使用合理
- [ ] 错误处理完善

---

## 七、验收标准

### 必须满足

1. ✅ TypeScript 类型检查通过
2. ✅ 所有文件存在且完整
3. ✅ FFmpeg WASM 可以加载
4. ✅ 素材可以本地处理
5. ✅ 视频可以本地拼接
6. ✅ Blob URL 可以播放

### 建议满足

1. 渲染时间 < 5 秒（预览）
2. 内存使用 < 1GB
3. 降级策略无缝切换
4. 移动端可用

---

*文档版本: 1.0*  
*创建日期: 2026-04-24*  
*作者: AI Assistant*
