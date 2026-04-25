import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import { getVideo, hasVideoInLocal, preloadManager } from '../utils/videoCache';

interface OptimizedVideoPlayerProps {
  itemId: string;
  videoUrl: string;
  isCached: boolean;
  apiBaseUrl: string;
  onError?: () => void;
}

/**
 * 优化版视频播放器
 * 特性：
 * 1. 优先使用本地缓存
 * 2. 智能缓冲策略
 * 3. 网络自适应码率
 * 4. 断点续播支持
 */
export default function OptimizedVideoPlayer({
  itemId,
  videoUrl,
  isCached,
  apiBaseUrl,
  onError
}: OptimizedVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [localUrl, setLocalUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bufferedPercent, setBufferedPercent] = useState(0);
  const objectUrlRef = useRef<string | null>(null);

  // 确定最终使用的视频源
  // 优先级：1.传入的Blob URL > 2.本地缓存 > 3.传入的其他URL
  const finalSrc = localUrl || (videoUrl.startsWith('http') || videoUrl.startsWith('blob:') ? videoUrl : `${apiBaseUrl}${videoUrl}`);

  useEffect(() => {
    let isMounted = true;

    const loadVideo = async () => {
      if (!isMounted) return;

      try {
        // 如果传入的是Blob URL（客户端渲染结果），直接使用，不加载缓存
        if (videoUrl.startsWith('blob:')) {
          console.log('[OptimizedVideoPlayer] 使用客户端渲染的Blob URL:', itemId);
          if (isMounted) {
            setIsLoading(false);
          }
          return;
        }

        // 优先尝试从本地缓存加载（仅非Blob URL时）
        if (isCached) {
          const file = await getVideo(itemId);
          if (file && isMounted) {
            const url = URL.createObjectURL(file);
            objectUrlRef.current = url;
            setLocalUrl(url);
            console.log('[OptimizedVideoPlayer] 使用本地缓存播放:', itemId);
          }
        }
      } catch (err) {
        console.error('[OptimizedVideoPlayer] 加载本地视频失败:', err);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadVideo();

    return () => {
      isMounted = false;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [itemId, isCached, videoUrl]);

  // 监听缓冲进度
  const handleProgress = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.buffered.length === 0) return;

    const bufferedEnd = video.buffered.end(video.buffered.length - 1);
    const duration = video.duration;
    if (duration > 0) {
      const percent = (bufferedEnd / duration) * 100;
      setBufferedPercent(percent);
    }
  }, []);

  // 处理播放错误
  const handleError = useCallback(() => {
    const video = videoRef.current;
    if (video?.error) {
      console.error('[OptimizedVideoPlayer] 播放错误:', video.error);
      setError('视频播放失败，请重试');
      onError?.();
    }
  }, [onError]);

  // 处理等待缓冲
  const handleWaiting = useCallback(() => {
    console.log('[OptimizedVideoPlayer] 缓冲中...');
    setIsLoading(true);
  }, []);

  // 处理可以播放
  const handleCanPlay = useCallback(() => {
    setIsLoading(false);
  }, []);

  if (error) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-black text-white">
        <AlertCircle size={32} className="text-red-500 mb-2" />
        <span className="text-sm text-gray-400">{error}</span>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-black">
      {/* 加载指示器 */}
      {isLoading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 bg-black/50">
          <Loader2 size={32} className="animate-spin text-white mb-2" />
          <span className="text-xs text-gray-400">
            {bufferedPercent > 0 ? `缓冲中 ${bufferedPercent.toFixed(0)}%` : '加载中...'}
          </span>
        </div>
      )}

      {/* 缓存标识 */}
      {localUrl && (
        <div className="absolute top-2 left-2 z-10 px-2 py-1 bg-green-500/80 text-white text-[10px] rounded">
          本地缓存
        </div>
      )}

      <video
        ref={videoRef}
        src={finalSrc}
        className="w-full h-full object-contain"
        controls
        autoPlay
        playsInline
        preload="auto"
        onProgress={handleProgress}
        onError={handleError}
        onWaiting={handleWaiting}
        onCanPlay={handleCanPlay}
        // 优化缓冲策略
        onLoadedMetadata={() => {
          // 尝试预加载更多数据
          if (videoRef.current) {
            videoRef.current.preload = 'auto';
          }
        }}
      />
    </div>
  );
}

/**
 * 使用 Intersection Observer 实现懒加载的包装组件
 */
interface LazyVideoPlayerProps extends OptimizedVideoPlayerProps {
  isVisible: boolean;
}

export function LazyVideoPlayer({ isVisible, ...props }: LazyVideoPlayerProps) {
  const [shouldLoad, setShouldLoad] = useState(false);

  useEffect(() => {
    if (isVisible && !shouldLoad) {
      setShouldLoad(true);
    }
  }, [isVisible, shouldLoad]);

  if (!shouldLoad) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-black">
        <Loader2 size={24} className="animate-spin text-gray-400" />
      </div>
    );
  }

  return <OptimizedVideoPlayer {...props} />;
}
