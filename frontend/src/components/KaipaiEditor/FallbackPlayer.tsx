import { useRef, useEffect, useState, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react';

interface Segment {
  id: string;
  beginTime: number;
  endTime: number;
}

interface FallbackPlayerProps {
  videoUrl: string;
  segments: Segment[];
  removedIds: Set<string>;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: string | null) => void;
  onEnded?: () => void;
}

export interface FallbackPlayerRef {
  seekTo: (timeMs: number) => void;
}

/**
 * 虚拟时间轴映射器
 * 处理原始时间到虚拟时间的映射
 */
class VirtualTimelineMapper {
  private keepSegments: Segment[];

  constructor(segments: Segment[], removedIds: Set<string>) {
    this.keepSegments = segments.filter((s) => !removedIds.has(s.id));
  }

  /**
   * 原始时间 -> 虚拟时间
   */
  originalToVirtual(originalTimeMs: number): number | null {
    let virtualTime = 0;
    for (const seg of this.keepSegments) {
      if (originalTimeMs >= seg.beginTime && originalTimeMs <= seg.endTime) {
        return virtualTime + (originalTimeMs - seg.beginTime);
      } else if (originalTimeMs > seg.endTime) {
        virtualTime += seg.endTime - seg.beginTime;
      } else {
        break;
      }
    }
    return null;
  }

  /**
   * 虚拟时间 -> 原始时间
   */
  virtualToOriginal(virtualTimeMs: number): number {
    let currentVirtual = 0;
    for (const seg of this.keepSegments) {
      const segDuration = seg.endTime - seg.beginTime;
      if (virtualTimeMs <= currentVirtual + segDuration) {
        return seg.beginTime + (virtualTimeMs - currentVirtual);
      }
      currentVirtual += segDuration;
    }
    return this.keepSegments[this.keepSegments.length - 1]?.endTime || 0;
  }

  /**
   * 获取下一个有效时间（跳过被删除的片段）
   */
  getNextValidTime(originalTimeMs: number): number | null {
    for (const seg of this.keepSegments) {
      if (originalTimeMs < seg.beginTime) {
        return seg.beginTime;
      } else if (originalTimeMs >= seg.beginTime && originalTimeMs <= seg.endTime) {
        return null; // 当前就在有效片段内
      }
    }
    return null; // 没有下一个有效时间
  }

  /**
   * 获取虚拟总时长
   */
  getVirtualDuration(): number {
    return this.keepSegments.reduce((sum, seg) => sum + (seg.endTime - seg.beginTime), 0);
  }

  /**
   * 获取当前片段ID
   */
  getCurrentSegmentId(originalTimeMs: number, allSegments: Segment[]): string | null {
    const seg = allSegments.find(
      (s) => originalTimeMs >= s.beginTime && originalTimeMs <= s.endTime
    );
    return seg?.id || null;
  }

  /**
   * 检查原始时间是否在保留片段内
   */
  isInKeepSegment(originalTimeMs: number): boolean {
    return this.keepSegments.some(
      (seg) => originalTimeMs >= seg.beginTime && originalTimeMs <= seg.endTime
    );
  }
}

const FallbackPlayer = forwardRef<FallbackPlayerRef, FallbackPlayerProps>(function FallbackPlayer({
  videoUrl,
  segments,
  removedIds,
  onTimeUpdate,
  onSegmentChange,
  onEnded,
}, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [virtualTime, setVirtualTime] = useState(0);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 创建时间轴映射器
  const timeMapper = useMemo(() => {
    return new VirtualTimelineMapper(segments, removedIds);
  }, [segments, removedIds]);

  // 虚拟总时长
  const virtualDuration = useMemo(() => {
    return timeMapper.getVirtualDuration();
  }, [timeMapper]);

  // 视频加载完成
  const handleLoadedMetadata = useCallback(() => {
    setIsReady(true);
  }, []);

  // 视频错误
  const handleError = useCallback(() => {
    setError('视频加载失败');
  }, []);

  // 播放循环（检测并跳过删除段）
  useEffect(() => {
    if (!isPlaying || !videoRef.current) return;

    let animationFrameId: number;
    let lastOriginalTime = 0;

    const loop = () => {
      const video = videoRef.current;
      if (!video) return;

      const originalTime = video.currentTime * 1000;

      // 检测是否需要跳转
      if (!timeMapper.isInKeepSegment(originalTime)) {
        const nextValid = timeMapper.getNextValidTime(originalTime);
        if (nextValid !== null) {
          video.currentTime = nextValid / 1000;
          lastOriginalTime = nextValid;
        } else {
          // 没有有效时间了，结束播放
          setIsPlaying(false);
          video.pause();
          onEnded?.();
          return;
        }
      } else {
        // 在有效片段内，更新虚拟时间
        const newVirtualTime = timeMapper.originalToVirtual(originalTime);
        if (newVirtualTime !== null) {
          setVirtualTime(newVirtualTime);
          onTimeUpdate?.(newVirtualTime);

          // 通知当前片段
          const segmentId = timeMapper.getCurrentSegmentId(originalTime, segments);
          onSegmentChange?.(segmentId);

          // 检查是否结束
          if (newVirtualTime >= virtualDuration - 100) {
            setIsPlaying(false);
            video.pause();
            onEnded?.();
            return;
          }
        }
        lastOriginalTime = originalTime;
      }

      animationFrameId = requestAnimationFrame(loop);
    };

    animationFrameId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animationFrameId);
  }, [
    isPlaying,
    timeMapper,
    virtualDuration,
    segments,
    onTimeUpdate,
    onSegmentChange,
    onEnded,
  ]);

  // 播放/暂停控制
  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;

    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      // 检查是否已经在结尾，如果是则从头开始
      const currentOriginalTime = videoRef.current.currentTime * 1000;
      const currentVirtualTime = timeMapper.originalToVirtual(currentOriginalTime);
      
      if (currentVirtualTime !== null && currentVirtualTime >= virtualDuration - 500) {
        // 已经在结尾，跳转到开头
        console.log('[FallbackPlayer] 已在结尾，从头开始播放');
        const firstSegment = timeMapper['keepSegments'][0];
        if (firstSegment) {
          videoRef.current.currentTime = firstSegment.beginTime / 1000;
        }
      }
      
      videoRef.current.play().catch((err) => {
        console.error('播放失败:', err);
        setError('播放失败');
      });
      setIsPlaying(true);
    }
  }, [isPlaying, timeMapper, virtualDuration]);

  // Seek 到指定虚拟时间
  const seekTo = useCallback(
    (virtualTimeMs: number) => {
      console.log('[FallbackPlayer] seekTo:', virtualTimeMs);
      if (!videoRef.current) return;

      const originalTime = timeMapper.virtualToOriginal(virtualTimeMs);
      videoRef.current.currentTime = originalTime / 1000;
      setVirtualTime(virtualTimeMs);
      onTimeUpdate?.(virtualTimeMs);
    },
    [timeMapper, onTimeUpdate]
  );

  // 暴露方法给父组件
  useImperativeHandle(ref, () => ({
    seekTo,
  }), [seekTo]);

  // 格式化时间
  const formatTime = (ms: number): string => {
    const seconds = Math.floor(ms / 1000);
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-white">
        <div className="text-center">
          <p className="text-red-400 mb-2">播放错误</p>
          <p className="text-sm text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-black">
      <video
        ref={videoRef}
        src={videoUrl}
        className="w-full h-full object-contain"
        playsInline
        onLoadedMetadata={handleLoadedMetadata}
        onError={handleError}
        onClick={togglePlay}
      />

      {/* 加载中 */}
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-sm text-gray-400">加载中...</p>
          </div>
        </div>
      )}

      {/* 播放状态指示器 */}
      {isReady && !isPlaying && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-16 h-16 bg-black/50 rounded-full flex items-center justify-center">
            <svg
              className="w-8 h-8 text-white ml-1"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      )}

      {/* 播放控制UI */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex items-center gap-4">
          <button
            onClick={togglePlay}
            className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center text-white hover:bg-white/30 transition-colors"
          >
            {isPlaying ? (
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              </svg>
            ) : (
              <svg
                className="w-6 h-6 ml-1"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>

          <div className="flex-1">
            <div className="text-white text-sm">
              {formatTime(virtualTime)} / {formatTime(virtualDuration)}
            </div>
            {/* 进度条 */}
            <div className="mt-2 h-1 bg-white/30 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-100"
                style={{
                  width: `${virtualDuration > 0 ? (virtualTime / virtualDuration) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

export default FallbackPlayer;
