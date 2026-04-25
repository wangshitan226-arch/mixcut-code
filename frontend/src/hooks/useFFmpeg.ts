/**
 * FFmpeg WASM Hook
 * 管理 FFmpeg 实例的生命周期和状态
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { getFFmpeg, isFFmpegLoaded, terminateFFmpeg } from '../utils/ffmpeg';

interface UseFFmpegReturn {
  ffmpeg: FFmpeg | null;
  isLoaded: boolean;
  isLoading: boolean;
  error: Error | null;
  loadProgress: number;
  load: () => Promise<void>;
  terminate: () => void;
}

/**
 * FFmpeg WASM Hook
 */
export function useFFmpeg(): UseFFmpegReturn {
  const [ffmpeg, setFfmpeg] = useState<FFmpeg | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [loadProgress, setLoadProgress] = useState(0);

  const isMounted = useRef(true);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    if (isLoading || isLoaded) return;

    setIsLoading(true);
    setError(null);
    setLoadProgress(0);

    let progressInterval: ReturnType<typeof setInterval> | null = null;

    try {
      // 检查是否已加载
      if (isFFmpegLoaded()) {
        const instance = await getFFmpeg();
        if (isMounted.current) {
          setFfmpeg(instance);
          setIsLoaded(true);
          setLoadProgress(100);
        }
        return;
      }

      // 模拟进度（实际加载没有细粒度进度）
      progressInterval = setInterval(() => {
        setLoadProgress(prev => {
          if (prev >= 90) return prev;
          return prev + Math.random() * 15;
        });
      }, 500);

      const instance = await getFFmpeg();

      if (progressInterval) {
        clearInterval(progressInterval);
      }

      if (isMounted.current) {
        setFfmpeg(instance);
        setIsLoaded(true);
        setLoadProgress(100);
      }
    } catch (err) {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      console.error('[useFFmpeg] 加载失败:', err);
      if (isMounted.current) {
        setError(err instanceof Error ? err : new Error('FFmpeg 加载失败'));
      }
    } finally {
      if (isMounted.current) {
        setIsLoading(false);
      }
    }
  }, [isLoading, isLoaded]);

  const terminate = useCallback(() => {
    terminateFFmpeg();
    setFfmpeg(null);
    setIsLoaded(false);
    setLoadProgress(0);
  }, []);

  return {
    ffmpeg,
    isLoaded,
    isLoading,
    error,
    loadProgress,
    load,
    terminate,
  };
}
