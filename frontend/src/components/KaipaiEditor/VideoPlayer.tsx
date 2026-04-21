import React, { useRef, useCallback, useEffect, useState } from 'react';
import type { VideoPlayerProps } from './types';

export default function VideoPlayer({
  videoUrl,
  currentTime,
  isPlaying,
  subtitle,
  progressPercent,
  totalDuration,
  allAsrSegments,
  removedIds,
  onTogglePlay,
  onTimeUpdate,
  onEnded,
  onSeek,
  onSubtitleChange,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const progressBarRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);
  const [internalTime, setInternalTime] = useState(0);

  // 获取被删除的时间段列表
  const getRemovedTimeRanges = useCallback(() => {
    const removedSegments = allAsrSegments.filter((s) => removedIds.has(s.id));
    return removedSegments.map((s) => ({
      beginTime: s.beginTime,
      endTime: s.endTime,
    }));
  }, [allAsrSegments, removedIds]);

  // 获取下一个有效时间（跳过被删除的部分）
  const getNextValidTime = useCallback(
    (currentTimeMs: number) => {
      const removedRanges = getRemovedTimeRanges().sort(
        (a, b) => a.beginTime - b.beginTime
      );

      for (const range of removedRanges) {
        if (
          currentTimeMs >= range.beginTime &&
          currentTimeMs < range.endTime
        ) {
          return range.endTime;
        }
        if (currentTimeMs < range.beginTime) {
          break;
        }
      }
      return null;
    },
    [getRemovedTimeRanges]
  );

  // 根据视频时间获取当前字幕和片段ID
  const getCurrentSubtitleInfo = useCallback(
    (videoTimeMs: number) => {
      // 计算实际播放时间（减去被删除片段的时长）
      const removedRanges = getRemovedTimeRanges().sort(
        (a, b) => a.beginTime - b.beginTime
      );

      let actualTimeMs = videoTimeMs;
      let removedDuration = 0;

      for (const range of removedRanges) {
        if (videoTimeMs > range.endTime) {
          // 已经经过了整个被删除的片段
          removedDuration += range.endTime - range.beginTime;
        } else if (videoTimeMs > range.beginTime) {
          // 在被删除的片段内部（这种情况不应该发生，因为会跳转）
          removedDuration += videoTimeMs - range.beginTime;
          break;
        } else {
          // 还没到被删除的片段
          break;
        }
      }

      actualTimeMs = videoTimeMs - removedDuration;

      // 在保留的片段中查找当前字幕
      const activeSegments = allAsrSegments.filter(
        (s) => !removedIds.has(s.id)
      );
      const current = activeSegments.find(
        (s) =>
          actualTimeMs >= s.beginTime - removedDuration &&
          actualTimeMs <= s.endTime - removedDuration
      );

      return {
        text: current?.text || '',
        segmentId: current?.id || null,
      };
    },
    [allAsrSegments, removedIds, getRemovedTimeRanges]
  );

  // 视频时间更新 - 检查是否需要跳过被删除的部分
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      const videoTimeMs = videoRef.current.currentTime * 1000;

      // 检查是否需要跳过被删除的部分
      const nextValidTime = getNextValidTime(videoTimeMs);
      if (nextValidTime !== null) {
        videoRef.current.currentTime = nextValidTime / 1000;
        return;
      }

      setInternalTime(videoRef.current.currentTime);
      onTimeUpdate(videoRef.current.currentTime);

      // 更新字幕
      const { text, segmentId } = getCurrentSubtitleInfo(videoTimeMs);
      onSubtitleChange(text, segmentId);
    }
  }, [getNextValidTime, getCurrentSubtitleInfo, onTimeUpdate, onSubtitleChange]);

  // 当外部传入的 currentTime 变化时，同步更新视频时间
  useEffect(() => {
    if (
      videoRef.current &&
      Math.abs(videoRef.current.currentTime - currentTime) > 0.5
    ) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  // 当 isPlaying 状态变化时，同步播放/暂停视频
  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play().catch(() => {
          // 自动播放被阻止，不处理
        });
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs
      .toString()
      .padStart(2, '0')}`;
  };

  // 进度条拖拽处理
  const handleProgressMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault();
      isDraggingRef.current = true;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        if (!progressBarRef.current || !isDraggingRef.current) return;

        const rect = progressBarRef.current.getBoundingClientRect();
        const percent = Math.max(
          0,
          Math.min(1, (moveEvent.clientX - rect.left) / rect.width)
        );
        const newTime = percent * totalDuration;
        if (videoRef.current) {
          videoRef.current.currentTime = newTime;
        }
      };

      const handleMouseUp = () => {
        isDraggingRef.current = false;
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    [totalDuration]
  );

  // 触摸设备进度条拖拽
  const handleProgressTouchStart = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      isDraggingRef.current = true;

      const handleTouchMove = (moveEvent: TouchEvent) => {
        if (!progressBarRef.current || !isDraggingRef.current) return;

        const touch = moveEvent.touches[0];
        const rect = progressBarRef.current.getBoundingClientRect();
        const percent = Math.max(
          0,
          Math.min(1, (touch.clientX - rect.left) / rect.width)
        );
        const newTime = percent * totalDuration;
        if (videoRef.current) {
          videoRef.current.currentTime = newTime;
        }
      };

      const handleTouchEnd = () => {
        isDraggingRef.current = false;
        document.removeEventListener('touchmove', handleTouchMove);
        document.removeEventListener('touchend', handleTouchEnd);
      };

      document.addEventListener('touchmove', handleTouchMove);
      document.addEventListener('touchend', handleTouchEnd);
    },
    [totalDuration]
  );

  return (
    <div
      className="shrink-0 bg-gray-100 flex items-center justify-center overflow-hidden"
      style={{ height: '30vh' }}
    >
      <div className="relative h-full aspect-[9/16] bg-black shadow-lg rounded-sm overflow-hidden">
        {videoUrl && (
          <video
            ref={videoRef}
            src={videoUrl}
            className="w-full h-full object-contain"
            playsInline
            onTimeUpdate={handleTimeUpdate}
            onEnded={onEnded}
            onClick={onTogglePlay}
          />
        )}

        {/* 播放状态指示器 */}
        {!isPlaying && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-16 h-16 bg-black/50 rounded-full flex items-center justify-center">
              <div className="w-0 h-0 border-t-8 border-t-transparent border-l-12 border-l-white border-b-8 border-b-transparent ml-1" />
            </div>
          </div>
        )}

        {/* 字幕显示 */}
        <div className="absolute bottom-16 left-0 right-0 text-center px-4 pointer-events-none">
          <p className="inline-block text-white text-sm font-bold drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)] bg-black/30 px-2 py-1 rounded">
            {subtitle}
          </p>
        </div>

        {/* 自定义进度条 */}
        <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/80 to-transparent">
          <div className="flex items-center gap-3">
            <span className="text-xs text-white/90 font-mono w-12">
              {formatTime(internalTime)}
            </span>
            <div
              ref={progressBarRef}
              className="flex-1 h-1 bg-white/30 rounded-full overflow-hidden cursor-pointer"
              onMouseDown={handleProgressMouseDown}
              onTouchStart={handleProgressTouchStart}
            >
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-100"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <span className="text-xs text-white/90 font-mono w-12">
              {formatTime(totalDuration)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
