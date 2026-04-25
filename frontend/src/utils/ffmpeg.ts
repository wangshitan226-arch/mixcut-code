/**
 * FFmpeg WASM 封装模块
 * 提供浏览器端的视频处理能力
 */

import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile, toBlobURL } from '@ffmpeg/util';

// FFmpeg 实例
let ffmpegInstance: FFmpeg | null = null;
let isLoading = false;
let loadPromise: Promise<FFmpeg> | null = null;

// 加载状态回调
 type LoadProgressCallback = (progress: number) => void;
let loadProgressCallback: LoadProgressCallback | null = null;

/**
 * 获取 FFmpeg 实例（单例模式）
 */
export async function getFFmpeg(): Promise<FFmpeg> {
  if (ffmpegInstance) {
    return ffmpegInstance;
  }

  if (loadPromise) {
    return loadPromise;
  }

  loadPromise = loadFFmpeg();
  return loadPromise;
}

/**
 * 加载 FFmpeg WASM
 * 使用 toBlobURL 方式加载，支持进度跟踪和超时处理
 */
async function loadFFmpeg(): Promise<FFmpeg> {
  if (isLoading) {
    throw new Error('FFmpeg is already loading');
  }

  isLoading = true;
  console.log('[FFmpeg] Starting to load...');

  try {
    const ffmpeg = new FFmpeg();

    // 监听日志
    ffmpeg.on('log', ({ message }) => {
      console.log('[FFmpeg]', message);
    });

    // 监听进度
    ffmpeg.on('progress', ({ progress }) => {
      const percent = Math.round(progress * 100);
      console.log(`[FFmpeg] Progress: ${percent}%`);
      if (loadProgressCallback) {
        loadProgressCallback(percent);
      }
    });

    // 使用 toBlobURL 加载核心文件
    // 这是 0.12 版本推荐的方式，可以更好地处理大文件
    const baseURL = '/ffmpeg';

    console.log('[FFmpeg] Loading core files with toBlobURL...');

    // 加载核心 JS 和 WASM 文件
    const [coreURL, wasmURL] = await Promise.all([
      toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
      toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
    ]);

    console.log('[FFmpeg] Core files loaded, calling ffmpeg.load()...');

    // 加载 FFmpeg
    await ffmpeg.load({
      coreURL,
      wasmURL,
    });

    ffmpegInstance = ffmpeg;
    console.log('[FFmpeg] Loaded successfully');

    return ffmpeg;
  } catch (error) {
    console.error('[FFmpeg] Failed to load:', error);
    throw error;
  } finally {
    isLoading = false;
    loadPromise = null;
  }
}

/**
 * 设置加载进度回调
 */
export function setLoadProgressCallback(callback: LoadProgressCallback): void {
  loadProgressCallback = callback;
}

/**
 * 检查 FFmpeg 是否已加载
 */
export function isFFmpegLoaded(): boolean {
  return ffmpegInstance !== null;
}

/**
 * 终止 FFmpeg 实例
 */
export function terminateFFmpeg(): void {
  if (ffmpegInstance) {
    ffmpegInstance.terminate();
    ffmpegInstance = null;
    console.log('[FFmpeg] Terminated');
  }
}

/**
 * 将文件写入 FFmpeg 虚拟文件系统
 */
export async function writeFileToFFmpeg(
  ffmpeg: FFmpeg,
  fileName: string,
  file: File | Blob | ArrayBuffer
): Promise<void> {
  const data = file instanceof ArrayBuffer ? new Uint8Array(file) : await fetchFile(file);
  await ffmpeg.writeFile(fileName, data);
}

/**
 * 从 FFmpeg 虚拟文件系统读取文件
 */
export async function readFileFromFFmpeg(
  ffmpeg: FFmpeg,
  fileName: string
): Promise<Uint8Array> {
  return await ffmpeg.readFile(fileName) as Uint8Array;
}

/**
 * 执行 FFmpeg 命令
 */
export async function execFFmpeg(
  ffmpeg: FFmpeg,
  args: string[]
): Promise<void> {
  const exitCode = await ffmpeg.exec(args);
  if (exitCode !== 0) {
    throw new Error(`FFmpeg exited with code ${exitCode}`);
  }
}

/**
 * 转码视频为统一格式
 * @param inputFile 输入文件
 * @param quality 质量设置: 'low' | 'medium' | 'high'
 */
export async function transcodeVideo(
  inputFile: File,
  quality: 'low' | 'medium' | 'high' = 'medium'
): Promise<Blob> {
  const ffmpeg = await getFFmpeg();

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
    await writeFileToFFmpeg(ffmpeg, inputName, inputFile);

    // 执行转码
    await execFFmpeg(ffmpeg, [
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

    // 读取输出文件
    const data = await readFileFromFFmpeg(ffmpeg, outputName);

    // 清理临时文件
    await cleanupFiles(ffmpeg, [inputName, outputName]);

    return new Blob([data.buffer], { type: 'video/mp4' });
  } catch (error) {
    // 发生错误时也要清理
    await cleanupFiles(ffmpeg, [inputName, outputName]).catch(() => {});
    throw error;
  }
}

/**
 * 拼接多个视频（copy 模式，秒级）
 */
export async function concatVideos(
  videoFiles: File[],
  reencode: boolean = false
): Promise<Blob> {
  const ffmpeg = await getFFmpeg();

  const inputNames: string[] = [];
  const timestamp = Date.now();

  try {
    // 写入所有输入文件
    for (let i = 0; i < videoFiles.length; i++) {
      const inputName = `input_${timestamp}_${i}.mp4`;
      await writeFileToFFmpeg(ffmpeg, inputName, videoFiles[i]);
      inputNames.push(inputName);
    }

    // 创建 concat 列表文件
    const listContent = inputNames.map(name => `file '${name}'`).join('\n');
    const listName = `list_${timestamp}.txt`;
    await ffmpeg.writeFile(listName, new TextEncoder().encode(listContent));

    const outputName = `concat_${timestamp}.mp4`;

    // 执行拼接
    const args = reencode
      ? [
          '-f', 'concat',
          '-safe', '0',
          '-i', listName,
          '-c:v', 'libx264',
          '-crf', '23',
          '-preset', 'superfast',
          '-c:a', 'aac',
          '-b:a', '128k',
          '-movflags', '+faststart',
          '-y',
          outputName,
        ]
      : [
          '-f', 'concat',
          '-safe', '0',
          '-i', listName,
          '-c:v', 'copy',
          '-c:a', 'copy',
          '-movflags', '+faststart',
          '-y',
          outputName,
        ];

    await execFFmpeg(ffmpeg, args);

    // 读取输出文件
    const data = await readFileFromFFmpeg(ffmpeg, outputName);

    // 清理临时文件
    await cleanupFiles(ffmpeg, [...inputNames, listName, outputName]);

    return new Blob([data.buffer], { type: 'video/mp4' });
  } catch (error) {
    // 发生错误时也要清理
    await cleanupFiles(ffmpeg, [...inputNames, `list_${timestamp}.txt`, `concat_${timestamp}.mp4`]).catch(() => {});
    throw error;
  }
}

/**
 * 生成视频缩略图
 */
export async function generateThumbnail(
  videoFile: File,
  time: number = 1,
  width: number = 300,
  height: number = 400
): Promise<Blob> {
  const ffmpeg = await getFFmpeg();

  const inputName = `thumb_input_${Date.now()}`;
  const outputName = `thumb_${Date.now()}.jpg`;

  try {
    // 写入输入文件
    await writeFileToFFmpeg(ffmpeg, inputName, videoFile);

    // 提取缩略图
    await execFFmpeg(ffmpeg, [
      '-i', inputName,
      '-ss', String(time),
      '-vframes', '1',
      '-vf', `scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2`,
      '-q:v', '2',
      '-y',
      outputName,
    ]);

    // 读取输出文件
    const data = await readFileFromFFmpeg(ffmpeg, outputName);

    // 清理临时文件
    await cleanupFiles(ffmpeg, [inputName, outputName]);

    return new Blob([data.buffer], { type: 'image/jpeg' });
  } catch (error) {
    await cleanupFiles(ffmpeg, [inputName, outputName]).catch(() => {});
    throw error;
  }
}

/**
 * 获取视频信息（时长、分辨率等）
 */
export function getVideoInfo(videoFile: File): Promise<{
  duration: number;
  width: number;
  height: number;
}> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    const url = URL.createObjectURL(videoFile);

    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve({
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
      });
    };

    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load video metadata'));
    };

    video.src = url;
    video.load();
  });
}

/**
 * 清理 FFmpeg 虚拟文件系统中的文件
 */
async function cleanupFiles(ffmpeg: FFmpeg, fileNames: string[]): Promise<void> {
  for (const fileName of fileNames) {
    try {
      await ffmpeg.deleteFile(fileName);
    } catch {
      // 文件可能不存在，忽略错误
    }
  }
}

/**
 * 检查 FFmpeg 是否支持当前环境
 */
export function checkFFmpegSupport(): {
  supported: boolean;
  reason?: string;
} {
  // 检查 WebAssembly 支持
  if (typeof WebAssembly === 'undefined') {
    return { supported: false, reason: 'WebAssembly not supported' };
  }

  // 检查 SharedArrayBuffer 支持（FFmpeg 需要）
  if (typeof SharedArrayBuffer === 'undefined') {
    return { supported: false, reason: 'SharedArrayBuffer not supported' };
  }

  // 检查跨域隔离（SharedArrayBuffer 需要）
  // 注意：实际部署时需要配置 COOP/COEP headers

  return { supported: true };
}
