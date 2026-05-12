/**
 * 客户端渲染功能测试页面
 * 独立测试页面，不影响现有功能
 * 访问路径: /test
 */

import React, { useState, useRef, useCallback } from 'react';
import { 
  Play, Download, RefreshCw, CheckCircle, XCircle, 
  Loader2, Film, HardDrive, Cpu, Smartphone, AlertTriangle,
  ChevronLeft, TestTube
} from 'lucide-react';
import { getFFmpeg, isFFmpegLoaded, checkFFmpegSupport, setLoadProgressCallback } from '../utils/ffmpeg';
import { isOPFSSupported, saveMaterial, loadMaterial, deleteMaterial, getStorageQuota } from '../utils/opfs';
import { isIndexedDBSupported, saveMaterialToIndexedDB, loadMaterialFromIndexedDB } from '../utils/indexedDB';
import { detectDeviceCapability, DeviceCapability } from '../utils/deviceCapability';
import { processMaterial, ProcessedMaterial } from '../utils/clientMaterialProcessor';
import { renderPreview, renderPreviewFromFiles, RenderResult, releaseBlobUrl } from '../utils/clientRenderer';
import { generateCombinations, convertServerMaterials, groupMaterialsByShot } from '../utils/combinationGenerator';
import { exportCombination, uploadToOSS } from '../utils/clientExport';

// 测试状态类型
type TestStatus = 'idle' | 'running' | 'success' | 'failed';

interface TestItem {
  id: string;
  name: string;
  status: TestStatus;
  message: string;
  duration?: number;
}

export default function TestClientRendering() {
  const [activeTab, setActiveTab] = useState<'overview' | 'ffmpeg' | 'storage' | 'material' | 'render' | 'combo'>('overview');
  const [tests, setTests] = useState<Map<string, TestItem>>(new Map());
  const [deviceCapability, setDeviceCapability] = useState<DeviceCapability | null>(null);
  const [processedMaterials, setProcessedMaterials] = useState<ProcessedMaterial[]>([]);
  const [renderedVideos, setRenderedVideos] = useState<Map<string, string>>(new Map());
  const [combinations, setCombinations] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // 更新测试状态
  const updateTest = useCallback((id: string, status: TestStatus, message: string, duration?: number) => {
    setTests(prev => new Map(prev).set(id, { id, name: getTestName(id), status, message, duration }));
  }, []);

  const getTestName = (id: string): string => {
    const names: Record<string, string> = {
      'ffmpeg-load': 'FFmpeg WASM 加载',
      'ffmpeg-transcode': '视频转码',
      'opfs-support': 'OPFS 支持检测',
      'opfs-write': 'OPFS 写入',
      'opfs-read': 'OPFS 读取',
      'opfs-delete': 'OPFS 删除',
      'idb-support': 'IndexedDB 支持检测',
      'idb-write': 'IndexedDB 写入',
      'idb-read': 'IndexedDB 读取',
      'device-detect': '设备能力检测',
      'material-process': '素材处理',
      'render-preview': '预览渲染',
      'combo-generate': '组合生成',
    };
    return names[id] || id;
  };

  // 运行所有基础测试
  const runAllTests = async () => {
    setIsLoading(true);
    
    // 1. 设备能力检测
    updateTest('device-detect', 'running', '检测中...');
    const start = performance.now();
    try {
      const cap = await detectDeviceCapability();
      setDeviceCapability(cap);
      updateTest('device-detect', 'success', `等级: ${cap.performanceLevel}`, performance.now() - start);
    } catch (err) {
      updateTest('device-detect', 'failed', '检测失败', performance.now() - start);
    }

    // 2. FFmpeg 支持检测
    updateTest('ffmpeg-load', 'running', '检查支持...');
    const ffmpegSupport = checkFFmpegSupport();
    if (!ffmpegSupport.supported) {
      updateTest('ffmpeg-load', 'failed', ffmpegSupport.reason || '不支持');
      setIsLoading(false);
      return;
    }

    // 3. 加载 FFmpeg（带超时处理）
    updateTest('ffmpeg-load', 'running', '加载中... (0%)');
    const ffmpegStart = performance.now();
    
    // 设置进度回调
    setLoadProgressCallback((progress) => {
      updateTest('ffmpeg-load', 'running', `加载中... (${progress}%)`);
    });
    
    try {
      // 创建超时 Promise
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => {
          reject(new Error('FFmpeg 加载超时（60秒），请检查网络连接或刷新页面重试'));
        }, 60000);
      });
      
      // 竞争：FFmpeg 加载 vs 超时
      await Promise.race([
        getFFmpeg(),
        timeoutPromise
      ]);
      
      updateTest('ffmpeg-load', 'success', '加载成功', performance.now() - ffmpegStart);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '加载失败';
      updateTest('ffmpeg-load', 'failed', errorMsg, performance.now() - ffmpegStart);
      setIsLoading(false);
      return;
    } finally {
      setLoadProgressCallback(null);
    }

    // 4. OPFS 检测
    updateTest('opfs-support', 'running', '检测中...');
    const opfsSupported = isOPFSSupported();
    updateTest('opfs-support', opfsSupported ? 'success' : 'failed', opfsSupported ? '支持' : '不支持');

    // 5. IndexedDB 检测
    updateTest('idb-support', 'running', '检测中...');
    const idbSupported = isIndexedDBSupported();
    updateTest('idb-support', idbSupported ? 'success' : 'failed', idbSupported ? '支持' : '不支持');

    setIsLoading(false);
  };

  // 测试 OPFS 读写删
  const testOPFS = async () => {
    if (!isOPFSSupported()) {
      alert('OPFS 不支持');
      return;
    }

    const testId = 'test-opfs-' + Date.now();
    const testBlob = new Blob(['test content'], { type: 'text/plain' });

    // 写入
    updateTest('opfs-write', 'running', '写入中...');
    const writeStart = performance.now();
    try {
      await saveMaterial(testId, testBlob);
      updateTest('opfs-write', 'success', '写入成功', performance.now() - writeStart);
    } catch (err) {
      updateTest('opfs-write', 'failed', '写入失败', performance.now() - writeStart);
      return;
    }

    // 读取
    updateTest('opfs-read', 'running', '读取中...');
    const readStart = performance.now();
    try {
      const result = await loadMaterial(testId);
      if (result.video) {
        updateTest('opfs-read', 'success', '读取成功', performance.now() - readStart);
      } else {
        updateTest('opfs-read', 'failed', '读取失败', performance.now() - readStart);
      }
    } catch (err) {
      updateTest('opfs-read', 'failed', '读取失败', performance.now() - readStart);
    }

    // 删除
    updateTest('opfs-delete', 'running', '删除中...');
    const deleteStart = performance.now();
    try {
      await deleteMaterial(testId);
      updateTest('opfs-delete', 'success', '删除成功', performance.now() - deleteStart);
    } catch (err) {
      updateTest('opfs-delete', 'failed', '删除失败', performance.now() - deleteStart);
    }
  };

  // 测试 IndexedDB 读写删
  const testIndexedDB = async () => {
    if (!isIndexedDBSupported()) {
      alert('IndexedDB 不支持');
      return;
    }

    const testId = 'test-idb-' + Date.now();
    const testBlob = new Blob(['test content'], { type: 'text/plain' });

    // 写入
    updateTest('idb-write', 'running', '写入中...');
    const writeStart = performance.now();
    try {
      await saveMaterialToIndexedDB(testId, testBlob);
      updateTest('idb-write', 'success', '写入成功', performance.now() - writeStart);
    } catch (err) {
      updateTest('idb-write', 'failed', '写入失败', performance.now() - writeStart);
      return;
    }

    // 读取
    updateTest('idb-read', 'running', '读取中...');
    const readStart = performance.now();
    try {
      const result = await loadMaterialFromIndexedDB(testId);
      if (result.video) {
        updateTest('idb-read', 'success', '读取成功', performance.now() - readStart);
      } else {
        updateTest('idb-read', 'failed', '读取失败', performance.now() - readStart);
      }
    } catch (err) {
      updateTest('idb-read', 'failed', '读取失败', performance.now() - readStart);
    }
  };

  // 处理素材
  const handleProcessMaterial = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    updateTest('material-process', 'running', `处理中: ${file.name}`);
    
    try {
      const result = await processMaterial(file, {
        quality: 'low',
        onProgress: (progress, stage) => {
          updateTest('material-process', 'running', `${stage}: ${Math.round(progress)}%`);
        },
      });

      setProcessedMaterials(prev => [...prev, result]);
      updateTest('material-process', 'success', `完成: ${result.id}`);
    } catch (err) {
      updateTest('material-process', 'failed', err instanceof Error ? err.message : '处理失败');
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // 渲染预览
  const handleRenderPreview = async () => {
    if (processedMaterials.length === 0) {
      alert('请先处理素材');
      return;
    }

    updateTest('render-preview', 'running', '渲染中...');
    
    try {
      // 直接使用已处理的素材进行拼接
      const filesToConcat = processedMaterials.slice(0, 3).map(m => {
        return new File([m.videoBlob], `${m.id}.mp4`, {
          type: 'video/mp4',
        });
      });

      const result = await renderPreviewFromFiles(filesToConcat, {
        renderId: `preview_${Date.now()}`,
        onProgress: (progress, stage) => {
          updateTest('render-preview', 'running', `${stage}: ${Math.round(progress)}%`);
        },
      });

      setRenderedVideos(prev => new Map(prev).set(result.renderId, result.blobUrl));
      updateTest('render-preview', 'success', `完成: ${result.renderId} (${filesToConcat.length}个素材)`);
    } catch (err) {
      console.error('[Test] 渲染失败:', err);
      updateTest('render-preview', 'failed', err instanceof Error ? err.message : '渲染失败');
    }
  };

  // 生成组合
  const handleGenerateCombinations = () => {
    if (processedMaterials.length === 0) {
      alert('请先处理素材');
      return;
    }

    updateTest('combo-generate', 'running', '生成中...');
    const start = performance.now();

    try {
      // 创建测试镜头
      const shots = [
        { id: 'shot1', name: '开场', order: 1 },
        { id: 'shot2', name: '主体', order: 2 },
        { id: 'shot3', name: '结尾', order: 3 },
      ];

      // 将素材分配到镜头
      const materialsMap = new Map<string, any[]>();
      processedMaterials.forEach((mat, index) => {
        const shotId = shots[index % shots.length].id;
        const list = materialsMap.get(shotId) || [];
        list.push({
          id: mat.id,
          shotId,
          duration: mat.duration,
          name: mat.id,
        });
        materialsMap.set(shotId, list);
      });

      const combos = generateCombinations(shots, materialsMap, { limit: 100 });
      setCombinations(combos);
      updateTest('combo-generate', 'success', `生成 ${combos.length} 个组合`, performance.now() - start);
    } catch (err) {
      updateTest('combo-generate', 'failed', err instanceof Error ? err.message : '生成失败', performance.now() - start);
    }
  };

  // 拼接指定组合的视频
  const handleRenderCombination = async (combo: any) => {
    if (processedMaterials.length === 0) {
      alert('请先处理素材');
      return;
    }

    updateTest('render-preview', 'running', `正在拼接组合: ${combo.id}...`);
    
    try {
      // 从 processedMaterials 中找到组合对应的视频文件
      const filesToConcat: File[] = [];
      
      for (const comboMaterial of combo.materials) {
        // 在 processedMaterials 中查找对应的素材
        const processedMat = processedMaterials.find(pm => pm.id === comboMaterial.id);
        if (processedMat && processedMat.videoBlob) {
          // 将 Blob 转换为 File
          const file = new File([processedMat.videoBlob], `${comboMaterial.id}.mp4`, {
            type: 'video/mp4',
          });
          filesToConcat.push(file);
        } else {
          console.warn(`[Test] 素材未找到: ${comboMaterial.id}`);
        }
      }

      if (filesToConcat.length === 0) {
        throw new Error('没有找到可拼接的素材');
      }

      console.log(`[Test] 拼接 ${filesToConcat.length} 个视频文件`);

      const result = await renderPreviewFromFiles(filesToConcat, {
        renderId: `combo_${combo.id}`,
        onProgress: (progress, stage) => {
          updateTest('render-preview', 'running', `${stage}: ${Math.round(progress)}%`);
        },
      });

      setRenderedVideos(prev => new Map(prev).set(result.renderId, result.blobUrl));
      updateTest('render-preview', 'success', `组合拼接完成: ${result.renderId} (${filesToConcat.length}个素材)`);
    } catch (err) {
      console.error('[Test] 拼接失败:', err);
      updateTest('render-preview', 'failed', err instanceof Error ? err.message : '拼接失败');
    }
  };

  // 导出高清视频
  const handleExport = async (quality: 'preview' | 'hd' | '4k' = 'hd') => {
    if (processedMaterials.length === 0) {
      alert('请先处理素材');
      return;
    }

    updateTest('export-video', 'running', `导出 ${quality.toUpperCase()} 中...`);

    try {
      // 检查是否已有拼接好的视频
      const existingRenderId = Array.from(renderedVideos.keys()).find(id => (id as string).startsWith('preview_') || (id as string).startsWith('combo_'));
      let existingBlob: Blob | undefined;

      if (existingRenderId) {
        // 从已有的 Blob URL 获取 Blob
        const response = await fetch(renderedVideos.get(existingRenderId)!);
        existingBlob = await response.blob();
        console.log('[Test] 使用已有拼接结果:', existingRenderId);
      }

      const filesToExport = processedMaterials.slice(0, 3).map(m => {
        return new File([m.videoBlob], `${m.id}.mp4`, {
          type: 'video/mp4',
        });
      });

      const result = await exportCombination(filesToExport, {
        quality,
        existingBlob,
        onProgress: (progress, stage) => {
          updateTest('export-video', 'running', `${stage}: ${Math.round(progress)}%`);
        },
      });

      // 显示导出结果
      setRenderedVideos(prev => new Map(prev).set(`export_${quality}`, result.blobUrl));
      updateTest('export-video', 'success', 
        `导出完成: ${(result.size / 1024 / 1024).toFixed(2)}MB, ${result.duration.toFixed(1)}秒`);

      // 模拟上传到 OSS
      updateTest('upload-oss', 'running', '上传到 OSS...');
      const uploadResult = await uploadToOSS(result.blob, `export_${Date.now()}.mp4`, (progress) => {
        updateTest('upload-oss', 'running', `上传: ${progress}%`);
      });

      if (uploadResult.success) {
        updateTest('upload-oss', 'success', `上传完成: ${uploadResult.url}`);
      } else {
        updateTest('upload-oss', 'failed', '上传失败');
      }
    } catch (err) {
      console.error('[Test] 导出失败:', err);
      updateTest('export-video', 'failed', err instanceof Error ? err.message : '导出失败');
    }
  };

  // 获取状态图标
  const getStatusIcon = (status: TestStatus) => {
    switch (status) {
      case 'success': return <CheckCircle size={16} className="text-green-500" />;
      case 'failed': return <XCircle size={16} className="text-red-500" />;
      case 'running': return <Loader2 size={16} className="animate-spin text-blue-500" />;
      default: return <div className="w-4 h-4 rounded-full border-2 border-gray-300" />;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex-shrink-0">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-2">
            <TestTube size={20} className="text-blue-600" />
            <h1 className="font-semibold text-gray-900">客户端渲染测试</h1>
          </div>
          <button 
            onClick={() => window.history.back()}
            className="flex items-center gap-1 text-gray-600 hover:text-gray-900"
          >
            <ChevronLeft size={16} />
            <span className="text-sm">返回</span>
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-4 pb-20">
        {/* 设备信息卡片 */}
        {deviceCapability && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
            <h2 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
              <Smartphone size={16} />
              设备能力
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">客户端渲染</div>
                <div className={`font-medium ${deviceCapability.canUseClientRendering ? 'text-green-600' : 'text-red-600'}`}>
                  {deviceCapability.canUseClientRendering ? '✅ 支持' : '❌ 不支持'}
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">性能等级</div>
                <div className="font-medium text-gray-900">{deviceCapability.performanceLevel}</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">内存</div>
                <div className="font-medium text-gray-900">{deviceCapability.memoryGB} GB</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">CPU 核心</div>
                <div className="font-medium text-gray-900">{deviceCapability.cpuCores} 核</div>
              </div>
            </div>
            {!deviceCapability.canUseClientRendering && (
              <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertTriangle size={16} className="text-yellow-600 mt-0.5" />
                  <div>
                    <div className="text-sm font-medium text-yellow-800">不支持客户端渲染</div>
                    <div className="text-xs text-yellow-700 mt-1">
                      {deviceCapability.unsupportedReasons.join(', ')}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 操作按钮 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={runAllTests}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              运行基础测试
            </button>
            <button
              onClick={testOPFS}
              disabled={!isOPFSSupported()}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <HardDrive size={16} />
              测试 OPFS
            </button>
            <button
              onClick={testIndexedDB}
              disabled={!isIndexedDBSupported()}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <HardDrive size={16} />
              测试 IndexedDB
            </button>
          </div>
        </div>

        {/* 测试结果 */}
        {tests.size > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
            <h2 className="font-medium text-gray-900 mb-3">测试结果</h2>
            <div className="space-y-2">
              {Array.from(tests.values()).map((test: TestItem) => (
                <div key={test.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                  {getStatusIcon(test.status)}
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-900">{test.name}</div>
                    <div className="text-xs text-gray-500">{test.message}</div>
                  </div>
                  {test.duration && (
                    <div className="text-xs text-gray-400">{test.duration.toFixed(0)}ms</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 素材处理测试 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
          <h2 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Film size={16} />
            素材处理测试
          </h2>
          <div className="flex flex-wrap gap-2 mb-4">
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={handleProcessMaterial}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              <Film size={16} />
              选择视频测试
            </button>
            <button
              onClick={handleRenderPreview}
              disabled={processedMaterials.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              <Play size={16} />
              渲染预览
            </button>
            <button
              onClick={handleGenerateCombinations}
              disabled={processedMaterials.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50"
            >
              <Cpu size={16} />
              生成组合
            </button>
            <button
              onClick={() => handleExport('hd')}
              disabled={processedMaterials.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              <Download size={16} />
              导出 HD
            </button>
            <button
              onClick={() => handleExport('preview')}
              disabled={processedMaterials.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50"
            >
              <Download size={16} />
              导出预览
            </button>
          </div>

          {/* 已处理素材 */}
          {processedMaterials.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">已处理素材 ({processedMaterials.length})</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {processedMaterials.map(mat => (
                  <div key={mat.id} className="bg-gray-50 rounded-lg p-2">
                    <img src={mat.thumbnailUrl} alt="thumbnail" className="w-full aspect-video object-cover rounded mb-1" />
                    <div className="text-xs text-gray-600 truncate">{mat.id}</div>
                    <div className="text-xs text-gray-500">{mat.duration.toFixed(1)}s / {(mat.size / 1024 / 1024).toFixed(2)}MB</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 渲染的视频 */}
          {renderedVideos.size > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">渲染结果 ({renderedVideos.size})</h3>
              <div className="space-y-2">
                {Array.from(renderedVideos.entries()).map(([id, url]) => (
                  <div key={id} className="bg-gray-50 rounded-lg p-2">
                    <video 
                      ref={videoRef}
                      src={url} 
                      controls 
                      className="w-full max-w-md rounded"
                      style={{ maxHeight: '300px' }}
                    />
                    <div className="text-xs text-gray-500 mt-1">{id}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 生成的组合 */}
          {combinations.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">生成的组合 ({combinations.length})</h3>
              <div className="max-h-60 overflow-y-auto space-y-1">
                {combinations.slice(0, 20).map((combo, index) => (
                  <div key={combo.id} className="flex items-center gap-2 p-2 bg-gray-50 rounded text-sm">
                    <span className="text-gray-400 w-6">{index + 1}</span>
                    <span className="flex-1 truncate">{combo.id}</span>
                    <span className="text-gray-500">{combo.duration}s</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      combo.uniqueness >= 90 ? 'bg-green-100 text-green-700' : 
                      combo.uniqueness >= 50 ? 'bg-blue-100 text-blue-700' : 
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {combo.uniqueness}%
                    </span>
                    <span className="text-xs text-gray-500">{combo.tag}</span>
                    <button
                      onClick={() => handleRenderCombination(combo)}
                      className="ml-2 px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs hover:bg-purple-200"
                    >
                      拼接预览
                    </button>
                  </div>
                ))}
                {combinations.length > 20 && (
                  <div className="text-center text-xs text-gray-500 py-2">
                    还有 {combinations.length - 20} 个...
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 使用说明 */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-blue-900 mb-2">测试步骤</h3>
          <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
            <li>点击"运行基础测试"检测设备能力和 FFmpeg 加载</li>
            <li>点击"测试 OPFS/IndexedDB"验证存储功能</li>
            <li>点击"选择视频测试"上传视频进行本地处理</li>
            <li>处理完成后点击"渲染预览"测试视频拼接</li>
            <li>点击"生成组合"测试组合生成算法</li>
          </ol>
        </div>
        </div>
      </div>
    </div>
  );
}
