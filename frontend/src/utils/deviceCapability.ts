/**
 * 设备能力检测模块
 * 用于检测浏览器是否支持客户端渲染，以及设备的性能等级
 */

import { checkFFmpegSupport } from './ffmpeg';
import { isOPFSSupported } from './opfs';

/**
 * 设备能力检测结果
 */
export interface DeviceCapability {
  // 是否支持客户端渲染
  canUseClientRendering: boolean;
  // 不支持的原因（如果不支持）
  unsupportedReasons: string[];
  // 设备性能等级
  performanceLevel: 'high' | 'medium' | 'low' | 'unsupported';
  // 最大可处理文件大小（字节）
  maxFileSize: number;
  // 推荐的质量设置
  recommendedQuality: 'high' | 'medium' | 'low';
  // 推荐预设
  recommendedPreset: 'ultrafast' | 'superfast' | 'veryfast' | 'medium';
  // 是否支持 OPFS
  supportsOPFS: boolean;
  // 是否支持 FFmpeg WASM
  supportsFFmpeg: boolean;
  // 是否支持 WebCodecs
  supportsWebCodecs: boolean;
  // 内存大小（GB，如果可用）
  memoryGB: number;
  // CPU 核心数
  cpuCores: number;
  // 是否移动端
  isMobile: boolean;
  // 浏览器信息
  browserInfo: {
    name: string;
    version: string;
    isSafari: boolean;
    isChrome: boolean;
    isFirefox: boolean;
    isEdge: boolean;
  };
}

/**
 * 检测设备能力
 */
export async function detectDeviceCapability(): Promise<DeviceCapability> {
  const unsupportedReasons: string[] = [];

  // 检测 FFmpeg WASM 支持
  const ffmpegSupport = checkFFmpegSupport();
  if (!ffmpegSupport.supported) {
    unsupportedReasons.push(`FFmpeg WASM: ${ffmpegSupport.reason}`);
  }

  // 检测 OPFS 支持
  const opfsSupported = isOPFSSupported();
  if (!opfsSupported) {
    unsupportedReasons.push('OPFS: Not supported');
  }

  // 检测 WebCodecs 支持
  const webCodecsSupported = checkWebCodecsSupport();
  if (!webCodecsSupported.supported) {
    unsupportedReasons.push(`WebCodecs: ${webCodecsSupported.reason}`);
  }

  // 获取设备信息
  const memoryGB = getDeviceMemory();
  const cpuCores = getCPUCores();
  const isMobile = detectMobile();
  const browserInfo = detectBrowser();

  // 检测 SharedArrayBuffer 和跨域隔离（仅作为警告，不阻止使用）
  const crossOriginIsolation = checkCrossOriginIsolation();
  if (!crossOriginIsolation.isolated) {
    // 如果 SharedArrayBuffer 存在，可能只是 crossOriginIsolated 检测时机问题
    if (typeof SharedArrayBuffer !== 'undefined') {
      console.warn('[DeviceCapability] Cross-Origin Isolation 检测失败，但 SharedArrayBuffer 可用');
    } else {
      unsupportedReasons.push(`Cross-Origin Isolation: ${crossOriginIsolation.reason}`);
    }
  }

  // 计算性能等级（即使跨域隔离检测失败，如果 SharedArrayBuffer 存在也继续）
  const actuallySupportsFFmpeg = ffmpegSupport.supported || (typeof SharedArrayBuffer !== 'undefined');
  const performanceLevel = calculatePerformanceLevel({
    memoryGB,
    cpuCores,
    isMobile,
    supportsFFmpeg: actuallySupportsFFmpeg,
    supportsOPFS: opfsSupported,
  });

  // 根据性能等级确定推荐配置
  const config = getRecommendedConfig(performanceLevel, isMobile);

  // 判断是否支持客户端渲染
  const canUseClientRendering =
    actuallySupportsFFmpeg &&
    opfsSupported &&
    performanceLevel !== 'unsupported';

  return {
    canUseClientRendering,
    unsupportedReasons,
    performanceLevel,
    maxFileSize: config.maxFileSize,
    recommendedQuality: config.quality,
    recommendedPreset: config.preset,
    supportsOPFS: opfsSupported,
    supportsFFmpeg: ffmpegSupport.supported,
    supportsWebCodecs: webCodecsSupported.supported,
    memoryGB,
    cpuCores,
    isMobile,
    browserInfo,
  };
}

/**
 * 检查 WebCodecs API 支持
 */
function checkWebCodecsSupport(): { supported: boolean; reason?: string } {
  if (typeof window === 'undefined') {
    return { supported: false, reason: 'Not in browser environment' };
  }

  if (!('VideoDecoder' in window)) {
    return { supported: false, reason: 'VideoDecoder not available' };
  }

  if (!('VideoEncoder' in window)) {
    return { supported: false, reason: 'VideoEncoder not available' };
  }

  // 检查配置支持
  try {
    const config: VideoDecoderConfig = {
      codec: 'avc1.42001E', // H.264 baseline
    };
    const support = (VideoDecoder as any).isConfigSupported(config);
    if (!support.supported) {
      return { supported: false, reason: 'H.264 decoding not supported' };
    }
  } catch {
    // isConfigSupported 可能不存在，继续检查
  }

  return { supported: true };
}

/**
 * 获取设备内存大小（GB）
 */
function getDeviceMemory(): number {
  if (typeof navigator === 'undefined') return 4;

  // @ts-ignore - deviceMemory 是非标准属性
  const memory = navigator.deviceMemory;

  if (typeof memory === 'number') {
    return memory;
  }

  // 根据 UA 估算
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes('iphone') || ua.includes('ipad')) {
    // iOS 设备通常内存较小
    return 4;
  }

  // 默认假设 4GB
  return 4;
}

/**
 * 获取 CPU 核心数
 */
function getCPUCores(): number {
  if (typeof navigator === 'undefined') return 2;
  return navigator.hardwareConcurrency || 2;
}

/**
 * 检测是否为移动设备
 */
function detectMobile(): boolean {
  if (typeof navigator === 'undefined') return false;

  const ua = navigator.userAgent;
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
}

/**
 * 检测浏览器信息
 */
function detectBrowser(): {
  name: string;
  version: string;
  isSafari: boolean;
  isChrome: boolean;
  isFirefox: boolean;
  isEdge: boolean;
} {
  if (typeof navigator === 'undefined') {
    return {
      name: 'unknown',
      version: 'unknown',
      isSafari: false,
      isChrome: false,
      isFirefox: false,
      isEdge: false,
    };
  }

  const ua = navigator.userAgent;

  const isEdge = /Edg\/|Edge\//.test(ua);
  const isChrome = !isEdge && /Chrome\//.test(ua);
  const isSafari = !isChrome && !isEdge && /Safari\//.test(ua);
  const isFirefox = /Firefox\//.test(ua);

  let name = 'unknown';
  let version = 'unknown';

  if (isEdge) {
    name = 'Edge';
    const match = ua.match(/Edg\/(\d+)/) || ua.match(/Edge\/(\d+)/);
    version = match ? match[1] : 'unknown';
  } else if (isChrome) {
    name = 'Chrome';
    const match = ua.match(/Chrome\/(\d+)/);
    version = match ? match[1] : 'unknown';
  } else if (isSafari) {
    name = 'Safari';
    const match = ua.match(/Version\/(\d+)/);
    version = match ? match[1] : 'unknown';
  } else if (isFirefox) {
    name = 'Firefox';
    const match = ua.match(/Firefox\/(\d+)/);
    version = match ? match[1] : 'unknown';
  }

  return { name, version, isSafari, isChrome, isFirefox, isEdge };
}

/**
 * 检查跨域隔离状态
 */
function checkCrossOriginIsolation(): { isolated: boolean; reason?: string } {
  if (typeof window === 'undefined') {
    return { isolated: false, reason: 'Not in browser environment' };
  }

  // @ts-ignore - crossOriginIsolated 可能不存在于旧浏览器
  if (window.crossOriginIsolated === true) {
    return { isolated: true };
  }

  // 检查 SharedArrayBuffer 是否可用（需要跨域隔离）
  if (typeof SharedArrayBuffer === 'undefined') {
    return {
      isolated: false,
      reason: 'SharedArrayBuffer not available (requires COOP/COEP headers)',
    };
  }

  return { isolated: true };
}

/**
 * 计算设备性能等级
 */
function calculatePerformanceLevel(params: {
  memoryGB: number;
  cpuCores: number;
  isMobile: boolean;
  supportsFFmpeg: boolean;
  supportsOPFS: boolean;
}): 'high' | 'medium' | 'low' | 'unsupported' {
  const { memoryGB, cpuCores, isMobile, supportsFFmpeg, supportsOPFS } = params;

  // 基本要求
  if (!supportsFFmpeg || !supportsOPFS) {
    return 'unsupported';
  }

  // 移动端降级
  if (isMobile) {
    if (memoryGB >= 6 && cpuCores >= 6) {
      return 'medium';
    }
    if (memoryGB >= 4 && cpuCores >= 4) {
      return 'low';
    }
    return 'unsupported';
  }

  // 桌面端
  if (memoryGB >= 16 && cpuCores >= 8) {
    return 'high';
  }
  if (memoryGB >= 8 && cpuCores >= 4) {
    return 'medium';
  }
  if (memoryGB >= 4 && cpuCores >= 2) {
    return 'low';
  }

  return 'unsupported';
}

/**
 * 获取推荐配置
 */
function getRecommendedConfig(
  performanceLevel: 'high' | 'medium' | 'low' | 'unsupported',
  isMobile: boolean,
  forceEnable = false
): {
  maxFileSize: number;
  quality: 'high' | 'medium' | 'low';
  preset: 'ultrafast' | 'superfast' | 'veryfast' | 'medium';
} {
  const configs = {
    high: {
      maxFileSize: 500 * 1024 * 1024, // 500MB
      quality: 'high' as const,
      preset: 'medium' as const,
    },
    medium: {
      maxFileSize: 200 * 1024 * 1024, // 200MB
      quality: 'medium' as const,
      preset: 'superfast' as const,
    },
    low: {
      maxFileSize: 100 * 1024 * 1024, // 100MB
      quality: 'low' as const,
      preset: 'ultrafast' as const,
    },
    unsupported: {
      maxFileSize: 50 * 1024 * 1024, // 50MB，即使不支持也允许小文件
      quality: 'low' as const,
      preset: 'ultrafast' as const,
    },
  };

  const config = configs[performanceLevel];

  // 移动端进一步限制
  if (isMobile && performanceLevel !== 'unsupported') {
    // 如果强制启用，放宽限制但仍保持保守
    if (forceEnable) {
      return {
        maxFileSize: 50 * 1024 * 1024, // 强制启用时最大50MB
        quality: 'low',
        preset: 'ultrafast',
      };
    }
    
    return {
      maxFileSize: Math.min(config.maxFileSize, 100 * 1024 * 1024), // 移动端最大100MB
      quality: config.quality === 'high' ? 'medium' : 'low',
      preset: 'ultrafast',
    };
  }

  return config;
}

/**
 * 快速检查是否支持客户端渲染
 */
export function quickCheckSupport(): boolean {
  // 快速检查关键特性
  if (typeof WebAssembly === 'undefined') return false;
  if (typeof SharedArrayBuffer === 'undefined') return false;
  if (!isOPFSSupported()) return false;

  return true;
}

/**
 * 获取不支持时的降级建议
 */
export function getFallbackAdvice(capability: DeviceCapability): string {
  if (capability.canUseClientRendering) {
    return 'Your device fully supports client-side rendering.';
  }

  const reasons = capability.unsupportedReasons;

  if (reasons.some(r => r.includes('SharedArrayBuffer'))) {
    return 'Please ensure the site is served with COOP/COEP headers for full functionality.';
  }

  if (reasons.some(r => r.includes('OPFS'))) {
    return 'Your browser does not support OPFS. Please use Chrome, Edge, or Safari 16.4+';
  }

  if (capability.performanceLevel === 'unsupported') {
    return 'Your device does not meet the minimum requirements. The system will use server-side processing instead.';
  }

  return 'Some features may be limited. The system will use fallback mode.';
}

/**
 * 监听设备能力变化（如内存压力）
 */
export function watchDevicePerformance(
  callback: (capability: Partial<DeviceCapability>) => void
): () => void {
  // 监听内存压力（如果支持）
  // @ts-ignore
  if ('storage' in navigator && 'estimate' in navigator.storage) {
    const checkMemory = async () => {
      try {
        // @ts-ignore
        const estimate = await navigator.storage.estimate();
        if (estimate.usage && estimate.quota) {
          const usageRatio = estimate.usage / estimate.quota;
          if (usageRatio > 0.9) {
            callback({ performanceLevel: 'low' });
          }
        }
      } catch {
        // 忽略错误
      }
    };

    const interval = setInterval(checkMemory, 30000); // 每30秒检查一次

    return () => clearInterval(interval);
  }

  return () => {};
}
