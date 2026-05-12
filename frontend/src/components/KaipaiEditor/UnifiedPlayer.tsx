import { useEffect, useState, useCallback, useRef, forwardRef, useImperativeHandle } from 'react';
import { getVideo, hasVideoInLocal } from '../../utils/videoStorage';
import { isWebCodecsSupported, logBrowserCapabilities } from '../../utils/webcodecs';
import WebCodecsPlayer from './WebCodecsPlayer';
import FallbackPlayer from './FallbackPlayer';

interface Segment {
  id: string;
  beginTime: number;
  endTime: number;
}

interface UnifiedPlayerProps {
  videoId: string;
  videoUrl: string;
  segments: Segment[];
  removedIds: Set<string>;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: string | null) => void;
  onEnded?: () => void;
}

export interface UnifiedPlayerRef {
  seekTo: (timeMs: number) => void;
  play: () => void;
  pause: () => void;
}

type PlayerType = 'webcodecs' | 'fallback' | 'loading';

/**
 * 统一播放器组件
 * 
 * 功能：
 * 1. 自动检测浏览器能力
 * 2. 自动选择最佳播放器（WebCodecs 或 Fallback）
 * 3. 管理本地视频缓存
 * 4. 提供统一的播放接口
 */
const UnifiedPlayer = forwardRef<UnifiedPlayerRef, UnifiedPlayerProps>(function UnifiedPlayer(
  props,
  ref
) {
  const {
    videoId,
    videoUrl,
    segments,
    removedIds,
    onTimeUpdate,
    onSegmentChange,
    onEnded,
  } = props;
  const [playerType, setPlayerType] = useState<PlayerType>('loading');
  const [localFile, setLocalFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 播放器 ref
  const webcodecsPlayerRef = useRef<{ seekTo: (timeMs: number) => void }>(null);
  const fallbackPlayerRef = useRef<{ seekTo: (timeMs: number) => void }>(null);

  // 初始化：检测浏览器能力和本地缓存
  useEffect(() => {
    const init = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // 打印浏览器能力报告
        logBrowserCapabilities();

        // 检查本地是否有缓存
        const hasLocal = await hasVideoInLocal(videoId);

        if (hasLocal) {
          // 从本地获取视频
          console.log('[UnifiedPlayer] 从本地缓存加载视频:', videoId);
          const file = await getVideo(videoId);

          if (file) {
            setLocalFile(file);

            // 检测是否支持 WebCodecs
            if (isWebCodecsSupported()) {
              console.log('[UnifiedPlayer] 使用 WebCodecs 播放器');
              setPlayerType('webcodecs');
            } else {
              console.log('[UnifiedPlayer] WebCodecs 不支持，使用降级播放器');
              setPlayerType('fallback');
            }
          } else {
            // 本地获取失败，回退到远程
            console.warn('[UnifiedPlayer] 本地获取失败，使用远程视频');
            setPlayerType('fallback');
          }
        } else {
          // 没有本地缓存，使用远程视频
          console.log('[UnifiedPlayer] 无本地缓存，使用远程视频');
          setPlayerType('fallback');
        }
      } catch (err) {
        console.error('[UnifiedPlayer] 初始化失败:', err);
        setError('播放器初始化失败');
        setPlayerType('fallback');
      } finally {
        setIsLoading(false);
      }
    };

    init();
  }, [videoId]);

  // 缓存视频到本地（供外部调用）
  const cacheVideo = useCallback(async (file: File): Promise<boolean> => {
    try {
      const { saveVideo } = await import('../../utils/videoStorage');
      await saveVideo(videoId, file);
      console.log('[UnifiedPlayer] 视频已缓存到本地:', videoId);
      return true;
    } catch (err) {
      console.error('[UnifiedPlayer] 缓存视频失败:', err);
      return false;
    }
  }, [videoId]);

  // 切换播放器类型（调试用）
  const switchPlayer = useCallback((type: 'webcodecs' | 'fallback') => {
    if (type === 'webcodecs' && !isWebCodecsSupported()) {
      console.warn('[UnifiedPlayer] 当前浏览器不支持 WebCodecs');
      return;
    }
    setPlayerType(type);
  }, []);

  // 暴露方法给父组件
  useImperativeHandle(ref, () => ({
    seekTo: (timeMs: number) => {
      console.log('[UnifiedPlayer] seekTo:', timeMs);
      if (playerType === 'webcodecs' && webcodecsPlayerRef.current) {
        webcodecsPlayerRef.current.seekTo(timeMs);
      } else if (playerType === 'fallback' && fallbackPlayerRef.current) {
        fallbackPlayerRef.current.seekTo(timeMs);
      }
    },
    play: () => {
      console.log('[UnifiedPlayer] play');
      // 播放控制由子组件内部管理
    },
    pause: () => {
      console.log('[UnifiedPlayer] pause');
      // 暂停控制由子组件内部管理
    },
  }), [playerType]);

  // 渲染加载状态
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-white">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-sm text-gray-400">初始化播放器...</p>
        </div>
      </div>
    );
  }

  // 渲染错误状态
  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-white">
        <div className="text-center">
          <p className="text-red-400 mb-2">错误</p>
          <p className="text-sm text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  // 渲染播放器
  return (
    <div className="relative w-full h-full">
      {/* WebCodecs 播放器 */}
      {playerType === 'webcodecs' && localFile && (
        <WebCodecsPlayer
          ref={webcodecsPlayerRef}
          videoFile={localFile}
          segments={segments}
          removedIds={removedIds}
          onTimeUpdate={onTimeUpdate}
          onSegmentChange={onSegmentChange}
          onEnded={onEnded}
        />
      )}

      {/* 降级播放器 */}
      {playerType === 'fallback' && (
        <FallbackPlayer
          ref={fallbackPlayerRef}
          videoUrl={videoUrl}
          segments={segments}
          removedIds={removedIds}
          onTimeUpdate={onTimeUpdate}
          onSegmentChange={onSegmentChange}
          onEnded={onEnded}
        />
      )}

      {/* 调试信息（开发环境显示） */}
      {(import.meta as any).env?.DEV && (
        <div className="absolute top-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
          {playerType === 'webcodecs' ? '🚀 WebCodecs' : '📺 Fallback'}
          {localFile && ' (Local)'}
        </div>
      )}
    </div>
  );
});

// 导出工具函数
export { isWebCodecsSupported, getBrowserCapabilities } from '../../utils/webcodecs';
export default UnifiedPlayer;
