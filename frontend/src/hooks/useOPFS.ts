/**
 * OPFS Storage Hook
 * 管理 OPFS 存储状态和操作
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  isOPFSSupported,
  getStorageQuota,
  checkStorageSpace,
  getTotalStorageSize,
  listMaterials,
  listRenders,
} from '../utils/opfs';

interface StorageInfo {
  usage: number;
  quota: number;
  usageRatio: number;
  materialCount: number;
  renderCount: number;
  isSupported: boolean;
}

interface UseOPFSReturn {
  storageInfo: StorageInfo;
  isChecking: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  checkSpace: (requiredBytes: number) => Promise<{ sufficient: boolean; available: number }>;
}

const DEFAULT_STORAGE_INFO: StorageInfo = {
  usage: 0,
  quota: 0,
  usageRatio: 0,
  materialCount: 0,
  renderCount: 0,
  isSupported: false,
};

/**
 * OPFS Storage Hook
 */
export function useOPFS(): UseOPFSReturn {
  const [storageInfo, setStorageInfo] = useState<StorageInfo>(DEFAULT_STORAGE_INFO);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const isMounted = useRef(true);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (isChecking) return;

    setIsChecking(true);
    setError(null);

    try {
      // 检查 OPFS 支持
      const supported = isOPFSSupported();

      if (!supported) {
        if (isMounted.current) {
          setStorageInfo({
            ...DEFAULT_STORAGE_INFO,
            isSupported: false,
          });
        }
        return;
      }

      // 获取配额信息
      let usage = 0;
      let quota = 0;
      try {
        const quotaInfo = await getStorageQuota();
        usage = quotaInfo.usage;
        quota = quotaInfo.quota;
      } catch {
        // 配额信息获取失败，使用估算
      }

      // 获取素材和渲染数量
      let materialCount = 0;
      let renderCount = 0;
      try {
        const [materials, renders] = await Promise.all([
          listMaterials(),
          listRenders(),
        ]);
        materialCount = materials.length;
        renderCount = renders.length;
      } catch {
        // 列表获取失败
      }

      if (isMounted.current) {
        setStorageInfo({
          usage,
          quota,
          usageRatio: quota > 0 ? usage / quota : 0,
          materialCount,
          renderCount,
          isSupported: true,
        });
      }
    } catch (err) {
      console.error('[useOPFS] 刷新失败:', err);
      if (isMounted.current) {
        setError(err instanceof Error ? err : new Error('存储信息获取失败'));
      }
    } finally {
      if (isMounted.current) {
        setIsChecking(false);
      }
    }
  }, [isChecking]);

  const checkSpace = useCallback(async (requiredBytes: number) => {
    try {
      const result = await checkStorageSpace(requiredBytes);
      return result;
    } catch {
      // 检查失败，假设空间充足
      return { sufficient: true, available: Infinity };
    }
  }, []);

  // 初始加载
  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    storageInfo,
    isChecking,
    error,
    refresh,
    checkSpace,
  };
}
