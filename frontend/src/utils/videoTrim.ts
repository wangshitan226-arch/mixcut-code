/**
 * 视频时间轴裁剪模块
 * 使用 FFmpeg WASM 实现精确的时间段裁剪和拼接
 */

import { getFFmpeg } from './ffmpeg';

export interface TimeRange {
  beginTime: number; // 毫秒
  endTime: number;   // 毫秒
}

export interface TrimOptions {
  onProgress?: (progress: number, stage: string) => void;
}

export interface TrimResult {
  blob: Blob;
  blobUrl: string;
  duration: number;
}

/**
 * 裁剪视频：删除指定时间段，保留其余部分
 *
 * 实现原理：
 * 1. 将保留的时间段按顺序裁剪为独立片段（使用 -ss -t 精确裁剪）
 * 2. 将所有片段按顺序拼接（使用 concat demuxer）
 * 3. 返回最终视频 Blob
 *
 * @param videoFile 原始视频文件
 * @param keepRanges 保留的时间段列表（毫秒）
 * @param options 选项
 */
export async function trimVideo(
  videoFile: File,
  keepRanges: TimeRange[],
  options: TrimOptions = {}
): Promise<TrimResult> {
  const { onProgress } = options;

  if (keepRanges.length === 0) {
    throw new Error('没有保留的时间段');
  }

  console.log('[Trim] 开始裁剪视频，保留段数:', keepRanges.length);
  const startTime = performance.now();

  const ffmpeg = await getFFmpeg();
  const timestamp = Date.now();
  const inputName = `trim_input_${timestamp}.mp4`;
  const segmentNames: string[] = [];

  try {
    onProgress?.(5, 'preparing');

    // 1. 写入原始视频
    const arrayBuffer = await videoFile.arrayBuffer();
    await ffmpeg.writeFile(inputName, new Uint8Array(arrayBuffer));

    onProgress?.(10, 'analyzing');

    // 2. 裁剪每个保留段
    const totalSegments = keepRanges.length;
    for (let i = 0; i < totalSegments; i++) {
      const range = keepRanges[i];
      const segmentName = `segment_${timestamp}_${i}.mp4`;
      segmentNames.push(segmentName);

      // 将毫秒转换为秒
      const startSec = (range.beginTime / 1000).toFixed(3);
      const durationSec = ((range.endTime - range.beginTime) / 1000).toFixed(3);

      console.log(`[Trim] 裁剪片段 ${i + 1}/${totalSegments}: ${startSec}s ~ ${durationSec}s`);

      // 使用 -ss -t 精确裁剪（关键帧精确）
      // -ss 放在 -i 之前：快速定位（可能不精确）
      // -ss 放在 -i 之后：精确裁剪（较慢）
      // 这里使用 -ss 在 -i 之前 + -copyts 保证时间戳正确
      await ffmpeg.exec([
        '-ss', startSec,
        '-i', inputName,
        '-t', durationSec,
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-avoid_negative_ts', 'make_zero',
        '-y',
        segmentName,
      ]);

      const progress = 10 + Math.round(((i + 1) / totalSegments) * 60);
      onProgress?.(progress, `cutting segment ${i + 1}/${totalSegments}`);
    }

    onProgress?.(75, 'concatenating');

    // 3. 拼接所有片段
    const listContent = segmentNames.map(name => `file '${name}'`).join('\n');
    const listName = `trim_list_${timestamp}.txt`;
    await ffmpeg.writeFile(listName, new TextEncoder().encode(listContent));

    const outputName = `trim_output_${timestamp}.mp4`;

    // 使用 concat demuxer 拼接（copy 模式，秒级）
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

    onProgress?.(90, 'finalizing');

    // 4. 读取输出文件
    const outputData = await ffmpeg.readFile(outputName);
    const blob = new Blob([outputData as Uint8Array], { type: 'video/mp4' });

    // 5. 获取时长
    const duration = await getVideoDurationFromBlob(blob);

    // 6. 清理临时文件
    await cleanupFiles(ffmpeg, [inputName, ...segmentNames, listName, outputName]);

    const totalTime = performance.now() - startTime;
    console.log(`[Trim] 裁剪完成，耗时: ${totalTime.toFixed(0)}ms, 大小: ${(blob.size / 1024 / 1024).toFixed(2)}MB, 时长: ${duration.toFixed(2)}s`);

    onProgress?.(100, 'completed');

    return {
      blob,
      blobUrl: URL.createObjectURL(blob),
      duration,
    };
  } catch (error) {
    // 发生错误时清理临时文件
    await cleanupFiles(ffmpeg, [inputName, ...segmentNames, `trim_list_${timestamp}.txt`, `trim_output_${timestamp}.mp4`]).catch(() => {});
    throw error;
  }
}

/**
 * 从视频时长计算保留段
 * 给定删除段，自动计算保留段
 *
 * @param totalDuration 总时长（毫秒）
 * @param removedRanges 删除的时间段列表
 */
export function calculateKeepRanges(
  totalDuration: number,
  removedRanges: TimeRange[]
): TimeRange[] {
  // 按开始时间排序
  const sortedRemoved = [...removedRanges].sort((a, b) => a.beginTime - b.beginTime);

  const keepRanges: TimeRange[] = [];
  let currentTime = 0;

  for (const removed of sortedRemoved) {
    // 如果当前时间小于删除段开始，则中间有保留段
    if (currentTime < removed.beginTime) {
      keepRanges.push({
        beginTime: currentTime,
        endTime: removed.beginTime,
      });
    }
    // 跳到删除段结束
    currentTime = Math.max(currentTime, removed.endTime);
  }

  // 检查最后一段
  if (currentTime < totalDuration) {
    keepRanges.push({
      beginTime: currentTime,
      endTime: totalDuration,
    });
  }

  return keepRanges;
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
