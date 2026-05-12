import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import * as MP4Box from 'mp4box';

interface Segment {
  id: string;
  beginTime: number;
  endTime: number;
}

interface WebCodecsPlayerProps {
  videoFile: File;
  segments: Segment[];
  removedIds: Set<string>;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: string | null) => void;
  onEnded?: () => void;
}

export interface WebCodecsPlayerRef {
  seekTo: (timeMs: number) => void;
}

const WebCodecsPlayer = forwardRef<WebCodecsPlayerRef, WebCodecsPlayerProps>(function WebCodecsPlayer({
  videoFile,
  segments,
  removedIds,
  onTimeUpdate,
  onSegmentChange,
  onEnded,
}, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const decoderRef = useRef<VideoDecoder | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const frameQueueRef = useRef<VideoFrame[]>([]);
  const animationRef = useRef<number>();
  const videoInfoRef = useRef<{ width: number; height: number } | null>(null);
  
  // 用于跳转的 ref
  const seekTargetRef = useRef<number | null>(null);

  // 计算保留的时间段
  const keepSegments = segments.filter((s) => !removedIds.has(s.id));

  // 计算虚拟时长（只计算保留片段的总时长）
  useEffect(() => {
    const virtualDuration = keepSegments.reduce(
      (sum, seg) => sum + (seg.endTime - seg.beginTime),
      0
    );
    setDuration(virtualDuration);
  }, [keepSegments]);

  // 初始化解码器
  const initDecoder = useCallback(async () => {
    try {
      setError(null);
      const buffer = await videoFile.arrayBuffer();

      const mp4box = MP4Box.createFile();

      mp4box.onReady = (info) => {
        const track = info.videoTracks[0];
        if (!track) {
          setError('未找到视频轨道');
          return;
        }

        videoInfoRef.current = {
          width: track.track_width,
          height: track.track_height,
        };

        // 设置 canvas 尺寸
        if (canvasRef.current) {
          canvasRef.current.width = track.track_width;
          canvasRef.current.height = track.track_height;
        }

        decoderRef.current = new VideoDecoder({
          output: (frame) => {
            frameQueueRef.current.push(frame);
          },
          error: (e) => {
            console.error('解码错误:', e);
            setError(`解码错误: ${e.message}`);
          },
        });

        decoderRef.current.configure({
          codec: track.codec,
          description: (track as any).description,
          hardwareAcceleration: 'prefer-hardware',
        });

        mp4box.setExtractionOptions(track.id);
        mp4box.start();
        setIsReady(true);
      };

      mp4box.onSamples = (trackId, ref, samples) => {
        for (const sample of samples) {
          const chunk = new EncodedVideoChunk({
            type: sample.is_sync ? 'key' : 'delta',
            timestamp: sample.cts,
            data: sample.data,
          });
          decoderRef.current?.decode(chunk);
        }
      };

      const arrayBuffer = new Uint8Array(buffer);
      (arrayBuffer as any).fileStart = 0;
      (mp4box as any).appendBuffer(arrayBuffer);
    } catch (err) {
      console.error('初始化解码器失败:', err);
      setError('初始化解码器失败');
    }
  }, [videoFile]);

  useEffect(() => {
    initDecoder();
    return () => {
      decoderRef.current?.close();
      cancelAnimationFrame(animationRef.current);
    };
  }, [initDecoder]);

  // 将原始时间映射到虚拟时间
  const originalToVirtualTime = useCallback(
    (originalTimeMs: number): number => {
      let virtualTime = 0;
      for (const seg of keepSegments) {
        if (originalTimeMs >= seg.beginTime && originalTimeMs <= seg.endTime) {
          // 在保留片段内
          return virtualTime + (originalTimeMs - seg.beginTime);
        } else if (originalTimeMs > seg.endTime) {
          // 已经过了这个片段
          virtualTime += seg.endTime - seg.beginTime;
        } else {
          // 还没到
          break;
        }
      }
      return virtualTime;
    },
    [keepSegments]
  );

  // 将虚拟时间映射到原始时间
  const virtualToOriginalTime = useCallback(
    (virtualTimeMs: number): number => {
      let currentVirtual = 0;
      for (const seg of keepSegments) {
        const segDuration = seg.endTime - seg.beginTime;
        if (virtualTimeMs <= currentVirtual + segDuration) {
          // 在这个片段内
          return seg.beginTime + (virtualTimeMs - currentVirtual);
        }
        currentVirtual += segDuration;
      }
      return keepSegments[keepSegments.length - 1]?.endTime || 0;
    },
    [keepSegments]
  );

  // 检查原始时间是否在保留片段内
  const isInKeepSegment = useCallback(
    (originalTimeMs: number): boolean => {
      return keepSegments.some(
        (seg) => originalTimeMs >= seg.beginTime && originalTimeMs <= seg.endTime
      );
    },
    [keepSegments]
  );

  // 获取当前片段ID
  const getCurrentSegmentId = useCallback(
    (originalTimeMs: number): string | null => {
      const seg = segments.find(
        (s) => originalTimeMs >= s.beginTime && originalTimeMs <= s.endTime
      );
      return seg?.id || null;
    },
    [segments]
  );

  // 渲染循环
  const renderLoop = useCallback(() => {
    if (!canvasRef.current) {
      animationRef.current = requestAnimationFrame(renderLoop);
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      animationRef.current = requestAnimationFrame(renderLoop);
      return;
    }

    // 获取当前应该显示的帧
    const frame = frameQueueRef.current.shift();

    if (frame) {
      const timestamp = frame.timestamp / 1000; // 转换为毫秒

      // 检查是否在保留时间段内
      if (isInKeepSegment(timestamp)) {
        // 渲染帧
        ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);

        // 更新虚拟时间
        const virtualTime = originalToVirtualTime(timestamp);
        setCurrentTime(virtualTime);
        onTimeUpdate?.(virtualTime);

        // 通知当前片段
        const segmentId = getCurrentSegmentId(timestamp);
        onSegmentChange?.(segmentId);

        // 检查是否结束
        if (virtualTime >= duration - 100) {
          setIsPlaying(false);
          onEnded?.();
        }
      }

      frame.close(); // 必须释放
    }

    animationRef.current = requestAnimationFrame(renderLoop);
  }, [
    isInKeepSegment,
    originalToVirtualTime,
    getCurrentSegmentId,
    duration,
    onTimeUpdate,
    onSegmentChange,
    onEnded,
  ]);

  useEffect(() => {
    animationRef.current = requestAnimationFrame(renderLoop);
    return () => cancelAnimationFrame(animationRef.current);
  }, [renderLoop]);

  // 播放控制
  const togglePlay = () => setIsPlaying(!isPlaying);

  // Seek 到指定虚拟时间
  const seekTo = useCallback(
    (virtualTimeMs: number) => {
      console.log('[WebCodecsPlayer] seekTo:', virtualTimeMs);
      // 找到对应原始时间
      const originalTime = virtualToOriginalTime(virtualTimeMs);
      
      // 记录跳转目标
      seekTargetRef.current = originalTime;

      // 更新当前时间显示
      setCurrentTime(virtualTimeMs);
      onTimeUpdate?.(virtualTimeMs);
      
      // 注意：WebCodecs 的精确跳转需要重新解码，这里简化处理
      // 实际项目中应该找到最近的关键帧并重新解码
    },
    [virtualToOriginalTime, onTimeUpdate]
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

  if (!isReady) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-white">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-sm text-gray-400">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-black">
      <canvas
        ref={canvasRef}
        className="w-full h-full object-contain"
        onClick={togglePlay}
      />

      {/* 播放状态指示器 */}
      {!isPlaying && (
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
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
            {/* 进度条 */}
            <div className="mt-2 h-1 bg-white/30 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-100"
                style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

export default WebCodecsPlayer;
