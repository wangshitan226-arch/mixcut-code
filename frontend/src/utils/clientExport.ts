/**
 * 客户端导出模块
 * 将本地拼接的视频导出为高清版本并上传到 OSS
 */

import { getFFmpeg } from './ffmpeg';
import { saveRender } from './opfs';

export interface ExportOptions {
  quality?: 'preview' | 'hd' | '4k';
  onProgress?: (progress: number, stage: string) => void;
}

export interface ExportResult {
  blob: Blob;
  blobUrl: string;
  duration: number;
  size: number;
}

/**
 * 快速导出视频（使用已有拼接结果）
 * 如果已有拼接好的视频，直接返回，不重新编码
 */
export async function exportCombination(
  videoFiles: File[],
  options: ExportOptions & { existingBlob?: Blob } = {}
): Promise<ExportResult> {
  const { quality = 'hd', onProgress, existingBlob } = options;

  // 如果提供了已有的拼接结果，直接返回（秒级）
  if (existingBlob) {
    console.log('[Export] 使用已有拼接结果，跳过重新编码');
    onProgress?.(100, 'completed');
    
    return {
      blob: existingBlob,
      blobUrl: URL.createObjectURL(existingBlob),
      duration: await getVideoDurationFromBlob(existingBlob),
      size: existingBlob.size,
    };
  }

  console.log('[Export] 开始导出:', quality);
  const startTime = performance.now();

  const ffmpeg = await getFFmpeg();
  const timestamp = Date.now();
  const inputNames: string[] = [];

  try {
    onProgress?.(10, 'preparing');

    // 写入所有输入文件
    for (let i = 0; i < videoFiles.length; i++) {
      const inputName = `export_in_${timestamp}_${i}.mp4`;
      const arrayBuffer = await videoFiles[i].arrayBuffer();
      await ffmpeg.writeFile(inputName, new Uint8Array(arrayBuffer));
      inputNames.push(inputName);
    }

    // 创建 concat 列表
    const listContent = inputNames.map(name => `file '${name}'`).join('\n');
    const listName = `export_list_${timestamp}.txt`;
    await ffmpeg.writeFile(listName, new TextEncoder().encode(listContent));

    const outputName = `export_${timestamp}.mp4`;

    onProgress?.(20, 'encoding');

    // 质量配置
    const qualityConfig = {
      preview: { crf: 28, preset: 'ultrafast', scale: '720:1280' },
      hd: { crf: 18, preset: 'medium', scale: '1080:1920' },
      '4k': { crf: 16, preset: 'slow', scale: '2160:3840' },
    };

    const config = qualityConfig[quality];

    // 重新编码拼接（质量优先）
    await ffmpeg.exec([
      '-f', 'concat',
      '-safe', '0',
      '-i', listName,
      '-vf', `scale=${config.scale}:force_original_aspect_ratio=decrease,pad=${config.scale}:(ow-iw)/2:(oh-ih)/2,fps=30`,
      '-c:v', 'libx264',
      '-crf', String(config.crf),
      '-preset', config.preset,
      '-c:a', 'aac',
      '-b:a', '192k',
      '-movflags', '+faststart',
      '-pix_fmt', 'yuv420p',
      '-y',
      outputName,
    ]);

    onProgress?.(80, 'finalizing');

    // 读取输出文件
    const outputData = await ffmpeg.readFile(outputName);
    const blob = new Blob([outputData as Uint8Array], { type: 'video/mp4' });

    // 获取时长
    const duration = await getVideoDurationFromBlob(blob);

    // 清理临时文件
    await cleanupFiles(ffmpeg, [...inputNames, listName, outputName]);

    const totalTime = performance.now() - startTime;
    console.log(`[Export] 导出完成，耗时: ${totalTime.toFixed(0)}ms, 大小: ${(blob.size / 1024 / 1024).toFixed(2)}MB`);

    onProgress?.(100, 'completed');

    return {
      blob,
      blobUrl: URL.createObjectURL(blob),
      duration,
      size: blob.size,
    };
  } catch (error) {
    await cleanupFiles(ffmpeg, [...inputNames, `export_list_${timestamp}.txt`, `export_${timestamp}.mp4`]).catch(() => {});
    throw error;
  }
}

/**
 * 获取视频时长
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
 * 清理 FFmpeg 临时文件
 */
async function cleanupFiles(ffmpeg: any, fileNames: string[]): Promise<void> {
  for (const fileName of fileNames) {
    try {
      await ffmpeg.deleteFile(fileName);
    } catch {
      // 忽略删除错误
    }
  }
}

/**
 * 模拟上传到 OSS（实际项目中替换为真实上传逻辑）
 */
export async function uploadToOSS(
  blob: Blob,
  filename: string,
  onProgress?: (progress: number) => void
): Promise<{ url: string; success: boolean }> {
  console.log('[Export] 上传到 OSS:', filename, `(${(blob.size / 1024 / 1024).toFixed(2)}MB)`);

  // 模拟上传进度
  for (let i = 0; i <= 100; i += 10) {
    onProgress?.(i);
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  // 模拟返回 URL
  const mockUrl = `https://mixcut-oss.example.com/exports/${filename}`;

  return {
    url: mockUrl,
    success: true,
  };
}

// 兼容性导出（供旧组件使用）
export const exportVideoToOSS = uploadToOSS;

/**
 * 下载视频到本地
 */
export function downloadVideo(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * 生成导出文件名
 */
export function generateExportFilename(combinationId: string, quality: string): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  return `mixcut_${combinationId}_${quality}_${timestamp}.mp4`;
}
