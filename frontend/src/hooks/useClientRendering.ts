/**
 * 客户端渲染主控 Hook
 * 整合所有客户端渲染功能，提供统一的接口
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { detectDeviceCapability, DeviceCapability } from '../utils/deviceCapability';
import { processMaterial, ProcessedMaterial } from '../utils/clientMaterialProcessor';
import { renderPreviewFromFiles, RenderResult, releaseBlobUrl } from '../utils/clientRenderer';
import { exportCombination, uploadToOSS } from '../utils/clientExport';
import { generateCombinations } from '../utils/combinationGenerator';

export interface ClientRenderingState {
  // 设备能力
  capability: DeviceCapability | null;
  // 是否启用客户端渲染
  isEnabled: boolean;
  // 是否强制启用（移动端）
  isForced: boolean;
  // 加载状态
  isLoading: boolean;
  // 错误信息
  error: string | null;
}

export interface UseClientRenderingReturn {
  // 状态
  state: ClientRenderingState;
  // 操作
  enable: () => void;
  disable: () => void;
  forceEnable: () => void;
  // 素材处理
  processMaterials: (files: File[]) => Promise<ProcessedMaterial[]>;
  // 组合生成
  generateCombos: (shots: any[], materials: Map<string, any[]>) => any[];
  // 渲染预览
  renderPreview: (combination: any) => Promise<RenderResult>;
  // 导出视频
  exportVideo: (combination: any, quality?: 'preview' | 'hd' | '4k') => Promise<any>;
  // 清理资源
  cleanup: () => void;
}

export function useClientRendering(): UseClientRenderingReturn {
  // 强制开启客户端渲染，跳过设备检测
  const [state, setState] = useState<ClientRenderingState>({
    capability: null,
    isEnabled: true, // 强制开启
    isForced: true,
    isLoading: false, // 跳过检测
    error: null,
  });

  const [processedMaterials, setProcessedMaterials] = useState<ProcessedMaterial[]>([]);
  const [renderedVideos, setRenderedVideos] = useState<Map<string, string>>(new Map());
  
  const isMounted = useRef(true);

  // 设备检测已禁用，强制开启客户端渲染
  useEffect(() => {
    console.log('[ClientRendering] 客户端渲染已强制开启，跳过设备检测');
  }, []);

  // 启用客户端渲染
  const enable = useCallback(() => {
    setState(prev => ({ ...prev, isEnabled: true, isForced: false }));
  }, []);

  // 禁用客户端渲染
  const disable = useCallback(() => {
    setState(prev => ({ ...prev, isEnabled: false, isForced: false }));
  }, []);

  // 强制启用（移动端）
  const forceEnable = useCallback(() => {
    setState(prev => ({ 
      ...prev, 
      isEnabled: true, 
      isForced: true,
      capability: prev.capability ? {
        ...prev.capability,
        canUseClientRendering: true,
        performanceLevel: 'low',
        maxFileSize: 50 * 1024 * 1024,
        recommendedQuality: 'low',
        recommendedPreset: 'ultrafast',
      } : null,
    }));
  }, []);

  // 处理素材
  const processMaterials = useCallback(async (files: File[]): Promise<ProcessedMaterial[]> => {
    const results: ProcessedMaterial[] = [];
    
    for (const file of files) {
      try {
        const result = await processMaterial(file, {
          quality: state.capability?.recommendedQuality || 'medium',
          generateThumbnail: true,
        });
        results.push(result);
        setProcessedMaterials(prev => [...prev, result]);
      } catch (err) {
        console.error('素材处理失败:', err);
      }
    }

    return results;
  }, [state.capability]);

  // 生成组合
  const generateCombos = useCallback((shots: any[], materials: Map<string, any[]>): any[] => {
    return generateCombinations(shots, materials, { limit: 100 });
  }, []);

  // 渲染预览
  const renderPreview = useCallback(async (combination: any): Promise<RenderResult> => {
    const files = combination.materials.map((m: any) => {
      const material = processedMaterials.find(pm => pm.id === m.id);
      if (!material) throw new Error(`素材未找到: ${m.id}`);
      return new File([material.videoBlob], `${m.id}.mp4`, { type: 'video/mp4' });
    });

    const result = await renderPreviewFromFiles(files, {
      renderId: `combo_${combination.id}`,
    });

    setRenderedVideos(prev => new Map(prev).set(result.renderId, result.blobUrl));
    return result;
  }, [processedMaterials]);

  // 导出视频
  const exportVideo = useCallback(async (combination: any, quality: 'preview' | 'hd' | '4k' = 'hd') => {
    const files = combination.materials.map((m: any) => {
      const material = processedMaterials.find(pm => pm.id === m.id);
      if (!material) throw new Error(`素材未找到: ${m.id}`);
      return new File([material.videoBlob], `${m.id}.mp4`, { type: 'video/mp4' });
    });

    // 检查是否已有渲染结果
    const existingRenderId = Array.from(renderedVideos.keys()).find(id => (id as string).includes(combination.id));
    let existingBlob: Blob | undefined;
    
    if (existingRenderId) {
      const response = await fetch(renderedVideos.get(existingRenderId)!);
      existingBlob = await response.blob();
    }

    const result = await exportCombination(files, {
      quality,
      existingBlob,
    });

    // 上传到 OSS
    const uploadResult = await uploadToOSS(
      result.blob,
      `export_${Date.now()}.mp4`
    );

    return {
      ...result,
      ossUrl: uploadResult.url,
    };
  }, [processedMaterials, renderedVideos]);

  // 清理资源
  const cleanup = useCallback(() => {
    // 释放所有 Blob URL
    renderedVideos.forEach(url => releaseBlobUrl(url));
    setRenderedVideos(new Map());
    setProcessedMaterials([]);
  }, [renderedVideos]);

  return {
    state,
    enable,
    disable,
    forceEnable,
    processMaterials,
    generateCombos,
    renderPreview,
    exportVideo,
    cleanup,
  };
}
