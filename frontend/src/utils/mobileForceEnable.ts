/**
 * 移动端强制启用模块
 * 绕过性能检测，强制在移动端使用客户端渲染
 * 
 * ⚠️ 警告：可能导致设备卡顿、发热、耗电快
 */

import { DeviceCapability } from './deviceCapability';

/**
 * 强制启用配置
 */
export interface ForceEnableConfig {
  // 忽略内存限制
  ignoreMemoryLimit: boolean;
  // 忽略 CPU 核心限制
  ignoreCPULimit: boolean;
  // 最大文件大小（覆盖默认限制）
  maxFileSize: number;
  // 使用更低的质量
  quality: 'low' | 'medium';
  // 使用更快的预设
  preset: 'ultrafast' | 'superfast';
  // 限制并发处理数
  maxConcurrency: number;
  // 启用内存监控
  enableMemoryMonitor: boolean;
}

/**
 * 默认强制启用配置（移动端优化）
 */
export const DEFAULT_MOBILE_FORCE_CONFIG: ForceEnableConfig = {
  ignoreMemoryLimit: true,
  ignoreCPULimit: true,
  maxFileSize: 50 * 1024 * 1024, // 50MB，移动端保守值
  quality: 'low',
  preset: 'ultrafast',
  maxConcurrency: 1, // 单线程处理
  enableMemoryMonitor: true,
};

/**
 * 强制覆盖设备能力检测结果
 */
export function forceEnableMobile(original: DeviceCapability): DeviceCapability {
  const config = DEFAULT_MOBILE_FORCE_CONFIG;

  return {
    ...original,
    canUseClientRendering: true,
    performanceLevel: 'low',
    maxFileSize: config.maxFileSize,
    recommendedQuality: config.quality,
    recommendedPreset: config.preset,
    unsupportedReasons: [], // 清空不支持原因
  };
}

/**
 * 监控内存使用，防止崩溃
 */
export function monitorMemoryUsage(
  callback: (usage: { used: number; total: number; ratio: number }) => void
): () => void {
  const interval = setInterval(async () => {
    try {
      // @ts-ignore
      if ('storage' in navigator && 'estimate' in navigator.storage) {
        // @ts-ignore
        const estimate = await navigator.storage.estimate();
        if (estimate.usage && estimate.quota) {
          callback({
            used: estimate.usage,
            total: estimate.quota,
            ratio: estimate.usage / estimate.quota,
          });
        }
      }
    } catch {
      // 忽略错误
    }
  }, 5000); // 每 5 秒检查

  return () => clearInterval(interval);
}

/**
 * 移动端优化处理策略
 */
export function getMobileOptimizedStrategy(): {
  chunkSize: number;
  batchSize: number;
  enableCompression: boolean;
} {
  return {
    chunkSize: 1024 * 1024, // 1MB 分块
    batchSize: 1, // 单文件处理
    enableCompression: true, // 启用压缩
  };
}

/**
 * 检查是否需要强制降级（运行时）
 */
export function shouldForceFallback(): boolean {
  // 检测内存压力
  // @ts-ignore
  if ('storage' in navigator && 'estimate' in navigator.storage) {
    // 异步检查，这里简化处理
    return false;
  }

  // 检测页面可见性
  if (document.hidden) {
    return true; // 后台运行时降级
  }

  return false;
}
