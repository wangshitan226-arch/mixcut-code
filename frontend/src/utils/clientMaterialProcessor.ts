/**
 * 客户端素材处理模块
 * 在浏览器端完成素材转码、缩略图生成和本地存储
 */

import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile } from '@ffmpeg/util';
import { getFFmpeg, getVideoInfo } from './ffmpeg';
import { saveMaterial, hasMaterial, checkStorageSpace } from './opfs';
import { saveMaterialToIndexedDB, hasMaterialInIndexedDB } from './indexedDB';
import { detectDeviceCapability } from './deviceCapability';
import { analyzeVideo, quickVideoCheck } from './videoValidator';
import { transcodeFast, isFastTranscodeSupported } from './webcodecsTranscoder';

// 处理进度回调
type ProgressCallback = (progress: number, stage: string) => void;

// 处理结果
export interface ProcessedMaterial {
  id: string;
  duration: number;
  width: number;
  height: number;
  size: number;
  thumbnailUrl: string;
  videoBlob: Blob;
  thumbnailBlob: Blob;
}

// 处理选项
export interface ProcessOptions {
  quality?: 'low' | 'medium' | 'high';
  generateThumbnail?: boolean;
  thumbnailTime?: number;
  onProgress?: ProgressCallback;
}

/**
 * 处理素材（转码 + 缩略图 + 本地存储）
 */
export async function processMaterial(
  file: File,
  options: ProcessOptions & { materialId?: string } = {}
): Promise<ProcessedMaterial> {
  const {
    quality = 'medium',
    generateThumbnail = true,
    thumbnailTime = 1,
    onProgress,
    materialId: customMaterialId,
  } = options;

  const materialId = customMaterialId || generateMaterialId();

  try {
    onProgress?.(0, 'initializing');

    // 检测设备能力
    const capability = await detectDeviceCapability();
    const actualQuality = capability.canUseClientRendering
      ? quality
      : 'low';

    // 检查文件大小
    if (file.size > capability.maxFileSize) {
      throw new Error(
        `文件过大: ${(file.size / 1024 / 1024).toFixed(2)}MB, ` +
        `最大允许: ${(capability.maxFileSize / 1024 / 1024).toFixed(2)}MB`
      );
    }

    // 检查存储空间
    const spaceCheck = await checkStorageSpace(file.size * 2); // 预留转码后空间
    if (!spaceCheck.sufficient) {
      throw new Error('存储空间不足');
    }

    onProgress?.(5, 'loading_ffmpeg');

    // 获取 FFmpeg 实例
    const ffmpeg = await getFFmpeg();

    onProgress?.(10, 'analyzing');

    // 获取视频信息
    const videoInfo = await getVideoInfo(file);

    // 分析视频是否需要转码
    onProgress?.(12, 'checking_format');
    const validation = await analyzeVideo(file);
    console.log('[MaterialProcessor] 视频检查结果:', {
      needsTranscode: validation.needsTranscode,
      reasons: validation.reasons,
      videoInfo: validation.videoInfo,
    });

    // 为了秒级拼接，所有素材必须统一为完全相同的编码参数
    // 策略：使用 WebCodecs 快速解码，然后用 FFmpeg 统一编码为标准 MP4/H.264/AAC
    
    let videoBlob: Blob;
    let outputName: string;
    
    // 优先使用 WebCodecs 快速转码（Chrome/Edge）
    let useFastTranscode = isFastTranscodeSupported();
    
    if (useFastTranscode) {
      console.log('[MaterialProcessor] 使用 WebCodecs 快速转码');
      onProgress?.(15, 'fast_transcoding');
      
      try {
        const result = await transcodeFast(file, {
          width: 1080,
          height: 1920,
          bitrate: actualQuality === 'low' ? 2_000_000 : actualQuality === 'high' ? 8_000_000 : 5_000_000,
          framerate: 30,
          onProgress: (progress, stage) => {
            const scaledProgress = 15 + progress * 0.55;
            onProgress?.(scaledProgress, stage);
          },
        });
        
        // WebCodecs 输出可能是 WebM 格式，需要用 FFmpeg 统一封装为 MP4
        console.log('[MaterialProcessor] WebCodecs 转码完成，统一封装为 MP4');
        onProgress?.(70, 'remuxing');
        
        // 使用 FFmpeg 重新封装为标准 MP4（不解码，只封装）
        const remuxedBlob = await remuxToStandardMP4(ffmpeg, result.blob, materialId);
        videoBlob = remuxedBlob;
        outputName = `${materialId}.mp4`;
        
        console.log('[MaterialProcessor] 快速转码+封装完成:', {
          width: result.width,
          height: result.height,
          duration: result.duration,
        });
      } catch (fastError) {
        console.warn('[MaterialProcessor] 快速转码失败，降级到 FFmpeg:', fastError);
        useFastTranscode = false;
      }
    }
    
    // 降级到 FFmpeg WASM 转码
    if (!useFastTranscode) {
      console.log('[MaterialProcessor] 使用 FFmpeg WASM 转码');
      onProgress?.(15, 'transcoding');

      const result = await transcodeVideo(
        ffmpeg,
        file,
        actualQuality,
        (progress) => {
          // 转码进度 15% -> 70%
          const scaledProgress = 15 + progress * 0.55;
          onProgress?.(scaledProgress, 'transcoding');
        }
      );
      videoBlob = result.videoBlob;
      outputName = result.outputName;
    }

    let thumbnailBlob: Blob;

    if (generateThumbnail) {
      onProgress?.(75, 'generating_thumbnail');

      // 优先使用 Canvas 生成缩略图（更快更可靠）
      try {
        thumbnailBlob = await generateThumbnailWithCanvas(videoBlob, thumbnailTime);
      } catch (canvasError) {
        console.warn('[MaterialProcessor] Canvas 缩略图失败，尝试 FFmpeg:', canvasError);
        // 降级到 FFmpeg 生成
        thumbnailBlob = await generateThumbnailFromVideo(
          ffmpeg,
          outputName,
          thumbnailTime
        );
      }
    } else {
      // 使用默认占位缩略图
      thumbnailBlob = await createPlaceholderThumbnail();
    }

    onProgress?.(90, 'saving');

    // 保存到本地存储
    await saveToStorage(materialId, videoBlob, thumbnailBlob);

    onProgress?.(100, 'completed');

    // 生成缩略图 URL
    const thumbnailUrl = URL.createObjectURL(thumbnailBlob);

    return {
      id: materialId,
      duration: videoInfo.duration,
      width: videoInfo.width,
      height: videoInfo.height,
      size: videoBlob.size,
      thumbnailUrl,
      videoBlob,
      thumbnailBlob,
    };
  } catch (error) {
    console.error('[MaterialProcessor] 处理失败:', error);
    throw error;
  }
}

/**
 * 转码视频
 */
async function transcodeVideo(
  ffmpeg: FFmpeg,
  file: File,
  quality: 'low' | 'medium' | 'high',
  onProgress?: (progress: number) => void
): Promise<{ videoBlob: Blob; outputName: string }> {
  const inputName = `input_${Date.now()}`;
  const outputName = `output_${Date.now()}.mp4`;

  // 质量配置
  const qualityConfig = {
    low: { crf: 28, preset: 'ultrafast', scale: '720:1280' },
    medium: { crf: 23, preset: 'superfast', scale: '1080:1920' },
    high: { crf: 18, preset: 'medium', scale: '1080:1920' },
  };

  const config = qualityConfig[quality];

  try {
    // 写入输入文件
    const data = await fetchFile(file);
    await ffmpeg.writeFile(inputName, data);

    // 设置进度监听
    const handleProgress = ({ progress }: { progress: number }) => {
      onProgress?.(Math.min(progress * 100, 99));
    };
    ffmpeg.on('progress', handleProgress);

    // 执行转码
    await ffmpeg.exec([
      '-i', inputName,
      '-vf', `scale=${config.scale}:force_original_aspect_ratio=decrease,pad=${config.scale}:(ow-iw)/2:(oh-ih)/2,fps=30`,
      '-c:v', 'libx264',
      '-crf', String(config.crf),
      '-preset', config.preset,
      '-c:a', 'aac',
      '-b:a', '128k',
      '-movflags', '+faststart',
      '-y',
      outputName,
    ]);

    // 移除进度监听
    ffmpeg.off('progress', handleProgress);

    // 读取输出文件
    const outputData = await ffmpeg.readFile(outputName);
    const videoBlob = new Blob([outputData as Uint8Array], { type: 'video/mp4' });

    // 清理临时文件
    await cleanupFiles(ffmpeg, [inputName, outputName]);

    return { videoBlob, outputName };
  } catch (error) {
    // 发生错误时也要清理
    await cleanupFiles(ffmpeg, [inputName, outputName]).catch(() => {});
    throw error;
  }
}

/**
 * 从视频中生成缩略图
 */
async function generateThumbnailFromVideo(
  ffmpeg: FFmpeg,
  videoName: string,
  time: number = 1
): Promise<Blob> {
  const outputName = `thumb_${Date.now()}.jpg`;

  try {
    await ffmpeg.exec([
      '-i', videoName,
      '-ss', String(time),
      '-vframes', '1',
      '-vf', 'scale=300:400:force_original_aspect_ratio=decrease,pad=300:400:(ow-iw)/2:(oh-ih)/2',
      '-q:v', '2',
      '-y',
      outputName,
    ]);

    const data = await ffmpeg.readFile(outputName);
    await ffmpeg.deleteFile(outputName);

    return new Blob([data as Uint8Array], { type: 'image/jpeg' });
  } catch (error) {
    console.warn('[MaterialProcessor] 缩略图生成失败，使用占位图:', error);
    return createPlaceholderThumbnail();
  }
}

/**
 * 使用 Canvas 生成缩略图（备用方案）
 */
export async function generateThumbnailWithCanvas(
  videoBlob: Blob,
  time: number = 1,
  width: number = 300,
  height: number = 400
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    const url = URL.createObjectURL(videoBlob);

    video.onloadedmetadata = () => {
      video.currentTime = Math.min(time, video.duration / 2);
    };

    video.onseeked = () => {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d')!;

      // 计算居中裁剪
      const videoRatio = video.videoWidth / video.videoHeight;
      const canvasRatio = width / height;

      let drawWidth, drawHeight, offsetX, offsetY;

      if (videoRatio > canvasRatio) {
        drawHeight = height;
        drawWidth = height * videoRatio;
        offsetX = (width - drawWidth) / 2;
        offsetY = 0;
      } else {
        drawWidth = width;
        drawHeight = width / videoRatio;
        offsetX = 0;
        offsetY = (height - drawHeight) / 2;
      }

      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, width, height);
      ctx.drawImage(video, offsetX, offsetY, drawWidth, drawHeight);

      canvas.toBlob(
        (blob) => {
          URL.revokeObjectURL(url);
          if (blob) {
            resolve(blob);
          } else {
            reject(new Error('Canvas toBlob failed'));
          }
        },
        'image/jpeg',
        0.85
      );
    };

    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Video load failed'));
    };

    video.src = url;
    video.load();
  });
}

/**
 * 创建占位缩略图
 */
async function createPlaceholderThumbnail(): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = 300;
  canvas.height = 400;
  const ctx = canvas.getContext('2d')!;

  // 绘制渐变背景
  const gradient = ctx.createLinearGradient(0, 0, 300, 400);
  gradient.addColorStop(0, '#1a1a2e');
  gradient.addColorStop(1, '#16213e');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 300, 400);

  // 绘制视频图标
  ctx.fillStyle = '#e94560';
  ctx.beginPath();
  ctx.moveTo(120, 160);
  ctx.lineTo(120, 240);
  ctx.lineTo(200, 200);
  ctx.closePath();
  ctx.fill();

  // 绘制文字
  ctx.fillStyle = '#fff';
  ctx.font = '14px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Video', 150, 280);

  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob!), 'image/jpeg', 0.8);
  });
}

/**
 * 保存到本地存储（优先 OPFS，降级 IndexedDB）
 */
async function saveToStorage(
  materialId: string,
  videoBlob: Blob,
  thumbnailBlob: Blob
): Promise<void> {
  // 优先尝试 OPFS
  try {
    await saveMaterial(materialId, videoBlob, thumbnailBlob);
    console.log('[MaterialProcessor] 已保存到 OPFS:', materialId);
    return;
  } catch (error) {
    console.warn('[MaterialProcessor] OPFS 保存失败，降级到 IndexedDB:', error);
  }

  // 降级到 IndexedDB
  try {
    await saveMaterialToIndexedDB(materialId, videoBlob, thumbnailBlob);
    console.log('[MaterialProcessor] 已保存到 IndexedDB:', materialId);
  } catch (error) {
    console.error('[MaterialProcessor] IndexedDB 保存失败:', error);
    throw new Error('本地存储失败');
  }
}

/**
 * 检查素材是否已存在于本地
 */
export async function isMaterialProcessed(materialId: string): Promise<boolean> {
  // 检查 OPFS
  const opfsExists = await hasMaterial(materialId).catch(() => false);
  if (opfsExists) return true;

  // 检查 IndexedDB
  return await hasMaterialInIndexedDB(materialId);
}

/**
 * 生成素材唯一ID
 */
function generateMaterialId(): string {
  return `mat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * 使用 FFmpeg 重新封装为标准 MP4/H.264/AAC
 * 不解码，只改变容器格式和统一参数
 */
async function remuxToStandardMP4(
  ffmpeg: FFmpeg,
  inputBlob: Blob,
  materialId: string
): Promise<Blob> {
  const inputName = `remux_in_${materialId}`;
  const outputName = `remux_out_${materialId}.mp4`;

  try {
    // 写入输入文件
    const arrayBuffer = await inputBlob.arrayBuffer();
    await ffmpeg.writeFile(inputName, new Uint8Array(arrayBuffer));

    // 重新封装为标准 MP4
    // -c:v copy -c:a copy 表示不解码，只复制流
    // 但会统一容器格式、时间戳等元数据
    await ffmpeg.exec([
      '-i', inputName,
      '-c:v', 'copy',
      '-c:a', 'copy',
      '-movflags', '+faststart',
      '-y',
      outputName,
    ]);

    // 读取输出文件
    const outputData = await ffmpeg.readFile(outputName);
    const outputBlob = new Blob([outputData as Uint8Array], { type: 'video/mp4' });

    // 清理临时文件
    await cleanupFiles(ffmpeg, [inputName, outputName]);

    return outputBlob;
  } catch (error) {
    // 清理临时文件
    await cleanupFiles(ffmpeg, [inputName, outputName]).catch(() => {});
    throw error;
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
 * 批量处理素材
 */
export async function processMaterials(
  files: File[],
  options: ProcessOptions = {}
): Promise<ProcessedMaterial[]> {
  const results: ProcessedMaterial[] = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    console.log(`[MaterialProcessor] 处理素材 ${i + 1}/${files.length}: ${file.name}`);

    try {
      const material = await processMaterial(file, {
        ...options,
        onProgress: (progress, stage) => {
          // 计算总体进度
          const overallProgress = (i + progress / 100) / files.length * 100;
          options.onProgress?.(overallProgress, `${stage} (${i + 1}/${files.length})`);
        },
      });

      results.push(material);
    } catch (error) {
      console.error(`[MaterialProcessor] 处理失败: ${file.name}`, error);
      // 继续处理下一个
    }
  }

  return results;
}
