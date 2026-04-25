/**
 * WebCodecs API 检测和工具函数
 * 
 * 功能：
 * 1. 检测浏览器是否支持 WebCodecs
 * 2. 检测 OPFS 支持
 * 3. 获取推荐播放器类型
 * 4. 视频格式检测
 */

/**
 * 检测 WebCodecs 是否支持
 */
export function isWebCodecsSupported(): boolean {
  return (
    typeof VideoDecoder !== 'undefined' &&
    typeof VideoEncoder !== 'undefined' &&
    typeof EncodedVideoChunk !== 'undefined' &&
    typeof VideoFrame !== 'undefined'
  );
}

/**
 * 检测 OPFS (Origin Private File System) 是否支持
 */
export function isOPFSSupported(): boolean {
  return typeof navigator.storage?.getDirectory === 'function';
}

/**
 * 检测 Cache API 是否支持
 */
export function isCacheAPISupported(): boolean {
  return typeof caches !== 'undefined';
}

/**
 * 获取推荐的播放器类型
 * @returns 'webcodecs' | 'fallback'
 */
export function getRecommendedPlayer(): 'webcodecs' | 'fallback' {
  if (isWebCodecsSupported()) {
    return 'webcodecs';
  }
  return 'fallback';
}

/**
 * 获取浏览器能力报告
 */
export function getBrowserCapabilities() {
  return {
    webcodecs: isWebCodecsSupported(),
    opfs: isOPFSSupported(),
    cacheAPI: isCacheAPISupported(),
    recommendedPlayer: getRecommendedPlayer(),
    userAgent: navigator.userAgent,
  };
}

/**
 * 检测视频格式是否受支持
 * @param mimeType MIME 类型，如 'video/mp4; codecs="avc1.42E01E"'
 */
export async function isVideoFormatSupported(mimeType: string): Promise<boolean> {
  if (!isWebCodecsSupported()) {
    return false;
  }

  try {
    const support = await VideoDecoder.isConfigSupported({
      codec: mimeType,
    });
    return support.supported;
  } catch {
    return false;
  }
}

/**
 * 常见的视频编码格式检测
 */
export async function checkCommonCodecs() {
  const codecs = [
    { name: 'H.264 Baseline', codec: 'avc1.42E01E' },
    { name: 'H.264 Main', codec: 'avc1.4D401E' },
    { name: 'H.264 High', codec: 'avc1.64001E' },
    { name: 'H.265', codec: 'hev1.1.6.L93.B0' },
    { name: 'VP9', codec: 'vp09.00.10.08' },
    { name: 'AV1', codec: 'av01.0.04M.08' },
  ];

  const results: Record<string, boolean> = {};

  for (const { name, codec } of codecs) {
    results[name] = await isVideoFormatSupported(codec);
  }

  return results;
}

/**
 * 打印浏览器能力报告到控制台
 */
export function logBrowserCapabilities() {
  const caps = getBrowserCapabilities();

  console.group('🎬 MixCut 浏览器能力检测');
  console.log('WebCodecs 支持:', caps.webcodecs ? '✅' : '❌');
  console.log('OPFS 支持:', caps.opfs ? '✅' : '❌');
  console.log('Cache API 支持:', caps.cacheAPI ? '✅' : '❌');
  console.log('推荐播放器:', caps.recommendedPlayer === 'webcodecs' ? 'WebCodecs' : '降级方案');
  console.groupEnd();

  return caps;
}

/**
 * 从 MP4 容器中提取编解码器信息
 * 注意：这个函数需要 MP4Box 库支持
 */
export function extractCodecFromMP4(arrayBuffer: ArrayBuffer): string | null {
  // 简化的 MP4 解析，提取 avcC 或 hvcC box
  const data = new Uint8Array(arrayBuffer);

  // 查找 ftyp box
  let offset = 0;
  while (offset < data.length - 8) {
    const size =
      (data[offset] << 24) |
      (data[offset + 1] << 16) |
      (data[offset + 2] << 8) |
      data[offset + 3];
    const type =
      String.fromCharCode(data[offset + 4]) +
      String.fromCharCode(data[offset + 5]) +
      String.fromCharCode(data[offset + 6]) +
      String.fromCharCode(data[offset + 7]);

    if (type === 'avcC' && offset + 19 < data.length) {
      // 提取 H.264 profile 和 level
      const profile = data[offset + 8 + 1];
      const level = data[offset + 8 + 3];
      return `avc1.${profile.toString(16).padStart(2, '0')}00${level.toString(16).padStart(2, '0')}`;
    }

    if (type === 'hvcC' && offset + 23 < data.length) {
      // H.265
      return 'hev1.1.6.L93.B0';
    }

    if (size === 0) break;
    offset += size;
  }

  return null;
}
