/**
 * 视频参数验证模块
 * 检查视频是否需要转码，避免不必要的处理
 */

export interface VideoValidationResult {
  needsTranscode: boolean;
  reasons: string[];
  videoInfo: {
    duration: number;
    width: number;
    height: number;
    codec?: string;
    container?: string;
    frameRate?: number;
    bitrate?: number;
  };
}

// 目标标准参数（宽松标准）
const TARGET_PARAMS = {
  container: ['mp4', 'mov', 'm4v'],
  videoCodec: 'avc1', // H.264
  audioCodec: 'mp4a', // AAC
  minWidth: 360,      // 放宽到 360p
  maxWidth: 1920,     // 放宽到 1080p
  minHeight: 640,     // 放宽到 640p
  maxHeight: 3840,    // 放宽到 4K
  maxBitrate: 20000000, // 放宽到 20 Mbps
};

/**
 * 分析视频文件，判断是否需要转码
 * 宽松标准：只要视频能播放且不太离谱，就跳过转码
 */
export async function analyzeVideo(file: File): Promise<VideoValidationResult> {
  const reasons: string[] = [];

  // 1. 检查文件扩展名/容器格式
  const ext = file.name.split('.').pop()?.toLowerCase() || '';
  const isCompatibleContainer = TARGET_PARAMS.container.includes(ext);
  if (!isCompatibleContainer) {
    reasons.push(`容器格式不支持: ${ext}`);
  }

  // 2. 使用视频元素获取基本信息
  const videoInfo = await getVideoMetadata(file);

  // 3. 检查分辨率（非常宽松）
  if (videoInfo.width < TARGET_PARAMS.minWidth || videoInfo.height < TARGET_PARAMS.minHeight) {
    reasons.push(`分辨率过低: ${videoInfo.width}x${videoInfo.height}`);
  }
  if (videoInfo.width > TARGET_PARAMS.maxWidth || videoInfo.height > TARGET_PARAMS.maxHeight) {
    reasons.push(`分辨率过高: ${videoInfo.width}x${videoInfo.height}`);
  }

  // 4. 检查编码格式（仅检查 MIME type）
  const mimeType = file.type.toLowerCase();
  const hasVideo = mimeType.startsWith('video/');
  if (!hasVideo) {
    reasons.push('不是视频文件');
  }

  // 5. 检查是否是 H.264（从 MIME type）
  // 常见格式: video/mp4; codecs="avc1.42E01E, mp4a.40.2"
  const isH264 = mimeType.includes('avc1') || mimeType.includes('h264');
  const isAAC = mimeType.includes('mp4a') || mimeType.includes('aac');

  // 如果 MIME type 明确说明不是 H.264，需要转码
  if (mimeType.includes('mp4') && !isH264 && mimeType.includes('codecs')) {
    reasons.push('视频编码可能不是 H.264');
  }

  // 6. 检查文件是否损坏（时长为 0 或 NaN）
  if (!videoInfo.duration || videoInfo.duration === 0 || isNaN(videoInfo.duration)) {
    reasons.push('无法读取视频时长，文件可能损坏');
  }

  return {
    needsTranscode: reasons.length > 0,
    reasons,
    videoInfo,
  };
}

/**
 * 获取视频元数据
 */
function getVideoMetadata(file: File): Promise<{
  duration: number;
  width: number;
  height: number;
  bitrate?: number;
}> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    const url = URL.createObjectURL(file);

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
      reject(new Error('无法读取视频元数据'));
    };

    video.src = url;
    video.load();
  });
}

/**
 * 快速检查：仅通过文件扩展名和大小判断
 * 用于 UI 快速反馈
 */
export function quickVideoCheck(file: File): {
  likelyCompatible: boolean;
  suggestions: string[];
} {
  const suggestions: string[] = [];
  const ext = file.name.split('.').pop()?.toLowerCase();

  // 常见兼容格式
  const compatibleExts = ['mp4', 'mov', 'm4v', 'webm'];
  const likelyCompatible = compatibleExts.includes(ext || '');

  if (!likelyCompatible) {
    suggestions.push('建议上传 MP4 格式视频');
  }

  // 文件大小建议
  if (file.size > 500 * 1024 * 1024) {
    suggestions.push('文件较大，处理可能需要更长时间');
  }

  return { likelyCompatible, suggestions };
}

/**
 * 获取视频编码信息的辅助函数
 */
export async function getDetailedVideoInfo(file: File): Promise<{
  codec?: string;
  container?: string;
  frameRate?: number;
  bitrate?: number;
}> {
  return {
    container: file.name.split('.').pop()?.toLowerCase(),
  };
}
