/**
 * 客户端渲染模块
 * 在浏览器端完成视频拼接和预览生成
 */

import { FFmpeg } from '@ffmpeg/ffmpeg';
import { getFFmpeg } from './ffmpeg';
import { loadMaterial, saveRender, loadRender, hasMaterial } from './opfs';
import { loadMaterialFromIndexedDB, loadRenderFromIndexedDB } from './indexedDB';

// 渲染进度回调
type RenderProgressCallback = (progress: number, stage: string) => void;

// 渲染结果
export interface RenderResult {
  renderId: string;
  blobUrl: string;
  blob: Blob;
  duration: number;
}

// 渲染选项
export interface RenderOptions {
  quality?: 'preview' | 'hd';
  onProgress?: RenderProgressCallback;
}

// 素材信息
export interface MaterialInfo {
  id: string;
  duration: number;
}

// 组合信息
export interface Combination {
  id: string;
  materials: MaterialInfo[];
}

/**
 * 渲染预览（快速拼接）
 * 支持直接从 File[] 拼接，或从 Combination 加载
 */
export async function renderPreview(
  combination: Combination,
  options: RenderOptions = {}
): Promise<RenderResult> {
  const { onProgress } = options;

  const renderId = `preview_${combination.id}_${Date.now()}`;

  try {
    onProgress?.(0, 'loading_materials');

    // 加载素材
    const materialFiles = await loadMaterialsForRender(combination.materials);

    onProgress?.(30, 'concatenating');

    // 快速拼接
    const { blob, duration } = await fastConcatVideos(materialFiles, (progress) => {
      const scaledProgress = 30 + progress * 0.6;
      onProgress?.(scaledProgress, 'concatenating');
    });

    onProgress?.(90, 'saving');

    // 保存到本地存储
    await saveRender(renderId, blob);

    onProgress?.(100, 'completed');

    // 生成 Blob URL
    const blobUrl = URL.createObjectURL(blob);

    return {
      renderId,
      blobUrl,
      blob,
      duration,
    };
  } catch (error) {
    console.error('[ClientRenderer] 预览渲染失败:', error);
    throw error;
  }
}

/**
 * 直接从 File 数组渲染预览
 * 用于测试页面直接拼接已处理的素材
 */
export async function renderPreviewFromFiles(
  files: File[],
  options: RenderOptions & { renderId?: string } = {}
): Promise<RenderResult> {
  const { onProgress, renderId: customRenderId } = options;

  const renderId = customRenderId || `preview_direct_${Date.now()}`;

  try {
    onProgress?.(0, 'preparing');

    if (files.length === 0) {
      throw new Error('没有提供视频文件');
    }

    onProgress?.(30, 'concatenating');

    // 直接拼接传入的文件
    const { blob, duration } = await fastConcatVideos(files, (progress) => {
      const scaledProgress = 30 + progress * 0.6;
      onProgress?.(scaledProgress, 'concatenating');
    });

    onProgress?.(90, 'saving');

    // 保存到本地存储
    await saveRender(renderId, blob);

    onProgress?.(100, 'completed');

    // 生成 Blob URL
    const blobUrl = URL.createObjectURL(blob);

    return {
      renderId,
      blobUrl,
      blob,
      duration,
    };
  } catch (error) {
    console.error('[ClientRenderer] 直接拼接失败:', error);
    throw error;
  }
}

/**
 * 渲染高清版本（重新编码）
 */
export async function renderHD(
  combination: Combination,
  options: RenderOptions = {}
): Promise<RenderResult> {
  const { onProgress } = options;

  const renderId = `hd_${combination.id}_${Date.now()}`;

  try {
    onProgress?.(0, 'loading_materials');

    // 加载素材
    const materialFiles = await loadMaterialsForRender(combination.materials);

    onProgress?.(20, 'encoding');

    // 重新编码拼接
    const { blob, duration } = await encodeConcatVideos(
      materialFiles,
      'high',
      (progress) => {
        const scaledProgress = 20 + progress * 0.75;
        onProgress?.(scaledProgress, 'encoding');
      }
    );

    onProgress?.(95, 'saving');

    // 保存到本地存储
    await saveRender(renderId, blob);

    onProgress?.(100, 'completed');

    // 生成 Blob URL
    const blobUrl = URL.createObjectURL(blob);

    return {
      renderId,
      blobUrl,
      blob,
      duration,
    };
  } catch (error) {
    console.error('[ClientRenderer] 高清渲染失败:', error);
    throw error;
  }
}

/**
 * 快速拼接视频（copy 模式）
 * 前提：所有视频已经过标准化处理（相同编码、分辨率）
 * 速度：秒级，不重新编码
 */
async function fastConcatVideos(
  videoFiles: File[],
  onProgress?: (progress: number) => void
): Promise<{ blob: Blob; duration: number }> {
  const ffmpeg = await getFFmpeg();
  const timestamp = Date.now();

  const inputNames: string[] = [];

  try {
    // 写入所有输入文件
    for (let i = 0; i < videoFiles.length; i++) {
      const inputName = `input_${timestamp}_${i}.mp4`;
      const file = videoFiles[i];
      const arrayBuffer = await file.arrayBuffer();
      await ffmpeg.writeFile(inputName, new Uint8Array(arrayBuffer));
      inputNames.push(inputName);
    }

    // 创建 concat 列表文件
    const listContent = inputNames.map(name => `file '${name}'`).join('\n');
    const listName = `list_${timestamp}.txt`;
    await ffmpeg.writeFile(listName, new TextEncoder().encode(listContent));

    const outputName = `concat_${timestamp}.mp4`;

    onProgress?.(10);

    // 使用 copy 模式拼接（秒级）
    // 要求所有视频编码参数完全一致
    await ffmpeg.exec([
      '-f', 'concat',
      '-safe', '0',
      '-i', listName,
      '-c:v', 'copy',
      '-c:a', 'copy',
      '-movflags', '+faststart',
      '-y',
      outputName,
    ]);

    onProgress?.(80);

    // 读取输出文件
    const outputData = await ffmpeg.readFile(outputName);
    const blob = new Blob([outputData as Uint8Array], { type: 'video/mp4' });

    // 获取时长
    const duration = await getVideoDurationFromBlob(blob);

    onProgress?.(100);

    // 清理临时文件
    await cleanupFiles(ffmpeg, [...inputNames, listName, outputName]);

    return { blob, duration };
  } catch (error) {
    console.warn('[FastConcat] copy 模式失败，尝试重新编码:', error);
    
    // 清理失败后的临时文件
    await cleanupFiles(ffmpeg, [
      ...inputNames,
      `list_${timestamp}.txt`,
      `concat_${timestamp}.mp4`,
    ]).catch(() => {});
    
    // 降级到重新编码模式
    return encodeConcatVideos(videoFiles, 'medium', onProgress);
  }
}

/**
 * 重新编码拼接视频
 */
async function encodeConcatVideos(
  videoFiles: File[],
  quality: 'medium' | 'high',
  onProgress?: (progress: number) => void
): Promise<{ blob: Blob; duration: number }> {
  const ffmpeg = await getFFmpeg();
  const timestamp = Date.now();

  const inputNames: string[] = [];

  const qualityConfig = {
    medium: { crf: 23, preset: 'superfast' },
    high: { crf: 18, preset: 'slow' },
  };

  const config = qualityConfig[quality];

  try {
    // 写入所有输入文件
    for (let i = 0; i < videoFiles.length; i++) {
      const inputName = `input_${timestamp}_${i}.mp4`;
      const file = videoFiles[i];
      const arrayBuffer = await file.arrayBuffer();
      await ffmpeg.writeFile(inputName, new Uint8Array(arrayBuffer));
      inputNames.push(inputName);
    }

    // 创建 concat 列表文件
    const listContent = inputNames.map(name => `file '${name}'`).join('\n');
    const listName = `list_${timestamp}.txt`;
    await ffmpeg.writeFile(listName, new TextEncoder().encode(listContent));

    const outputName = `encoded_${timestamp}.mp4`;

    onProgress?.(10);

    // 执行重新编码拼接
    await ffmpeg.exec([
      '-f', 'concat',
      '-safe', '0',
      '-i', listName,
      '-c:v', 'libx264',
      '-crf', String(config.crf),
      '-preset', config.preset,
      '-c:a', 'aac',
      '-b:a', '192k',
      '-movflags', '+faststart',
      '-y',
      outputName,
    ]);

    onProgress?.(80);

    // 读取输出文件
    const outputData = await ffmpeg.readFile(outputName);
    const blob = new Blob([outputData as Uint8Array], { type: 'video/mp4' });

    // 获取时长
    const duration = await getVideoDurationFromBlob(blob);

    onProgress?.(100);

    // 清理临时文件
    await cleanupFiles(ffmpeg, [...inputNames, listName, outputName]);

    return { blob, duration };
  } catch (error) {
    await cleanupFiles(ffmpeg, [
      ...inputNames,
      `list_${timestamp}.txt`,
      `encoded_${timestamp}.mp4`,
    ]).catch(() => {});
    throw error;
  }
}

/**
 * 加载素材用于渲染
 */
async function loadMaterialsForRender(
  materials: MaterialInfo[]
): Promise<File[]> {
  const files: File[] = [];

  for (const material of materials) {
    let file: File | null = null;

    // 优先从 OPFS 加载
    try {
      const opfsResult = await loadMaterial(material.id);
      if (opfsResult.video) {
        file = opfsResult.video;
      }
    } catch {
      // OPFS 加载失败
    }

    // 降级到 IndexedDB
    if (!file) {
      try {
        const idbResult = await loadMaterialFromIndexedDB(material.id);
        if (idbResult.video) {
          file = new File([idbResult.video], `${material.id}.mp4`, {
            type: 'video/mp4',
          });
        }
      } catch {
        // IndexedDB 加载失败
      }
    }

    if (!file) {
      throw new Error(`素材未找到: ${material.id}`);
    }

    files.push(file);
  }

  return files;
}

/**
 * 从 Blob 获取视频时长
 */
function getVideoDurationFromBlob(blob: Blob): Promise<number> {
  return new Promise((resolve) => {
    const video = document.createElement('video');
    const url = URL.createObjectURL(blob);

    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(video.duration);
    };

    video.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(0);
    };

    video.src = url;
    video.load();
  });
}

/**
 * 获取已渲染的视频
 */
export async function getRenderedVideo(renderId: string): Promise<string | null> {
  // 优先从 OPFS 加载
  try {
    const file = await loadRender(renderId);
    if (file) {
      return URL.createObjectURL(file);
    }
  } catch {
    // OPFS 加载失败
  }

  // 降级到 IndexedDB
  try {
    const blob = await loadRenderFromIndexedDB(renderId);
    if (blob) {
      return URL.createObjectURL(blob);
    }
  } catch {
    // IndexedDB 加载失败
  }

  return null;
}

/**
 * 释放 Blob URL
 */
export function releaseBlobUrl(url: string): void {
  if (url.startsWith('blob:')) {
    URL.revokeObjectURL(url);
  }
}

/**
 * 清理 FFmpeg 临时文件
 */
async function cleanupFiles(ffmpeg: FFmpeg, fileNames: string[]): Promise<void> {
  for (const fileName of fileNames) {
    try {
      await ffmpeg.deleteFile(fileName);
    } catch {
      // 忽略删除错误
    }
  }
}

/**
 * 批量预渲染（用于提前生成热门组合）
 */
export async function batchPreRender(
  combinations: Combination[],
  options: RenderOptions = {}
): Promise<Map<string, RenderResult>> {
  const results = new Map<string, RenderResult>();

  for (let i = 0; i < combinations.length; i++) {
    const combination = combinations[i];
    console.log(`[ClientRenderer] 预渲染 ${i + 1}/${combinations.length}: ${combination.id}`);

    try {
      const result = await renderPreview(combination, {
        ...options,
        onProgress: (progress, stage) => {
          const overallProgress = (i + progress / 100) / combinations.length * 100;
          options.onProgress?.(overallProgress, `${stage} (${i + 1}/${combinations.length})`);
        },
      });

      results.set(combination.id, result);
    } catch (error) {
      console.error(`[ClientRenderer] 预渲染失败: ${combination.id}`, error);
      // 继续处理下一个
    }
  }

  return results;
}
