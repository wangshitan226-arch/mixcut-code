import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  ChevronLeft,
  Check,
  VolumeX,
  Zap,
  Trash2,
  RotateCcw,
  Loader2,
  AlertCircle,
  Undo2,
  Download,
} from 'lucide-react';
import SegmentItem from './SegmentItem';
import EditModal from './EditModal';
import VideoPlayer from './VideoPlayer';
import type { Segment } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3002';

interface KaipaiEditorProps {
  editId: string;
  videoUrl: string;
  onBack: () => void;
  onSave?: () => void;
}

export default function KaipaiEditor({
  editId,
  videoUrl,
  onBack,
  onSave,
}: KaipaiEditorProps) {
  const [loading, setLoading] = useState(true);
  const [loadingText, setLoadingText] = useState('正在准备剪辑...');
  const [segments, setSegments] = useState<Segment[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [totalDuration, setTotalDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState('');
  const [historyCount, setHistoryCount] = useState(0);
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [outputUrl, setOutputUrl] = useState<string | null>(null);

  // 编辑弹窗状态
  const [editingSegment, setEditingSegment] = useState<Segment | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // 原始视频URL（从草稿获取）
  const [originalVideoUrl, setOriginalVideoUrl] = useState<string>('');

  // 存储完整的ASR结果（包含被删除的片段）用于跳转判断
  const [allAsrSegments, setAllAsrSegments] = useState<Segment[]>([]);
  // 存储被删除的片段ID
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());

  const videoRef = useRef<HTMLVideoElement>(null);

  // 获取草稿详情
  useEffect(() => {
    const loadDraft = async () => {
      try {
        const draftResponse = await fetch(
          `${API_BASE_URL}/api/kaipai/${editId}`
        );
        if (!draftResponse.ok) {
          throw new Error('获取草稿失败');
        }
        const draftData = await draftResponse.json();

        // 保存原始视频URL
        if (draftData.original_video_url) {
          setOriginalVideoUrl(draftData.original_video_url);
        }

        // 加载ASR结果
        if (draftData.asr_result && draftData.asr_result.sentences) {
          const allSegments = draftData.asr_result.sentences.map(
            (s: Segment) => ({
              ...s,
              selected: false,
              expanded: false,
            })
          );

          // 保存完整的ASR结果（用于跳转判断）
          setAllAsrSegments(allSegments);

          // 恢复已删除的片段ID
          const removedIdsSet = new Set(
            (draftData.edit_params?.removed_segments || []).map(
              (s: any) => s.id
            )
          );
          setRemovedIds(removedIdsSet);

          // 只显示未删除的片段
          const activeSegments = allSegments.filter(
            (s: Segment) => !removedIdsSet.has(s.id)
          );

          setSegments(activeSegments);

          // 计算总时长（只计算保留的片段）
          const total = activeSegments.reduce(
            (sum: number, s: Segment) => sum + (s.endTime - s.beginTime),
            0
          );
          setTotalDuration(total / 1000);

          setLoading(false);

          if (draftData.edit_history) {
            setHistoryCount(draftData.edit_history.length);
          }

          if (draftData.output_video_url) {
            setOutputUrl(draftData.output_video_url);
          }

          return;
        }

        // 如果没有ASR结果，启动语音识别
        startTranscription();
      } catch (err: any) {
        setLoading(false);
        setError(err.message || '加载失败');
        setLoadingText('加载失败');
      }
    };

    loadDraft();
  }, [editId]);

  // 启动语音识别
  const startTranscription = async () => {
    try {
      const startResponse = await fetch(
        `${API_BASE_URL}/api/kaipai/${editId}/transcribe`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      if (!startResponse.ok) {
        const errorData = await startResponse.json();
        throw new Error(errorData.error || '启动识别失败');
      }

      // 开始轮询状态
      pollTranscriptionStatus();
    } catch (err: any) {
      setLoading(false);
      setError(err.message || '启动识别失败');
      setLoadingText('启动识别失败');
    }
  };

  // 轮询语音识别状态
  const pollTranscriptionStatus = () => {
    const checkStatus = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/kaipai/${editId}/transcribe/status`
        );
        const data = await response.json();

        if (data.status === 'completed') {
          // 重新加载草稿获取ASR结果
          const draftResponse = await fetch(
            `${API_BASE_URL}/api/kaipai/${editId}`
          );
          const draftData = await draftResponse.json();

          if (draftData.original_video_url) {
            setOriginalVideoUrl(draftData.original_video_url);
          }

          if (draftData.asr_result?.sentences) {
            const allSegments = draftData.asr_result.sentences.map(
              (s: Segment) => ({
                ...s,
                selected: false,
                expanded: false,
              })
            );

            // 保存完整的ASR结果
            setAllAsrSegments(allSegments);

            const removedIdsSet = new Set(
              (draftData.edit_params?.removed_segments || []).map(
                (s: any) => s.id
              )
            );
            setRemovedIds(removedIdsSet);

            const activeSegments = allSegments.filter(
              (s: Segment) => !removedIdsSet.has(s.id)
            );

            setSegments(activeSegments);
            const total = activeSegments.reduce(
              (sum: number, s: Segment) => sum + (s.endTime - s.beginTime),
              0
            );
            setTotalDuration(total / 1000);
          }

          setLoading(false);
        } else if (data.status === 'failed') {
          setError('语音识别失败: ' + (data.error || '未知错误'));
          setLoading(false);
        } else {
          // 继续轮询
          setTimeout(checkStatus, 1000);
        }
      } catch (err) {
        setTimeout(checkStatus, 1000);
      }
    };

    checkStatus();
  };

  // 获取被删除的时间段列表
  const getRemovedTimeRanges = useCallback(() => {
    // 从完整的ASR结果中找出被删除的片段
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
          // 当前时间在被删除范围内，跳转到结束时间
          return range.endTime;
        }
        if (currentTimeMs < range.beginTime) {
          // 在当前时间之后有被删除的部分，但还没到，继续播放
          break;
        }
      }

      return null; // 不需要跳转
    },
    [getRemovedTimeRanges]
  );

  // 视频播放结束
  const handleVideoEnded = useCallback(() => {
    setIsPlaying(false);
  }, []);

  // 播放/暂停
  const togglePlay = useCallback(() => {
    console.log('[KaipaiEditor] togglePlay called, current isPlaying:', isPlaying);
    // 只切换状态，实际的播放/暂停由 VideoPlayer 组件处理
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  // 跳转到指定时间
  const jumpToTime = useCallback(
    (targetTimeMs: number) => {
      console.log('[KaipaiEditor] jumpToTime called:', targetTimeMs);
      // 检查目标时间是否在被删除的范围内，如果是，跳转到该范围的结束
      const nextValidTime = getNextValidTime(targetTimeMs);
      const finalTime =
        nextValidTime !== null ? nextValidTime : targetTimeMs;

      console.log('[KaipaiEditor] Jumping to:', finalTime, 'isPlaying will be set to true');
      // 只更新状态，实际的跳转和播放由 VideoPlayer 组件处理
      setCurrentTime(finalTime / 1000);
      setIsPlaying(true);
    },
    [getNextValidTime]
  );

  // 切换选中状态
  const toggleSelect = useCallback((id: string) => {
    setSegments((prev) =>
      prev.map((s) => (s.id === id ? { ...s, selected: !s.selected } : s))
    );
  }, []);

  // 切换展开状态
  const toggleExpand = useCallback((id: string) => {
    setSegments((prev) =>
      prev.map((s) => (s.id === id ? { ...s, expanded: !s.expanded } : s))
    );
  }, []);

  // 编辑字
  const editWord = useCallback(
    (segmentId: string, wordBeginTime: number, newText: string) => {
      setSegments((prev) =>
        prev.map((s) => {
          if (s.id !== segmentId) return s;
          return {
            ...s,
            words: s.words?.map((w) =>
              w.beginTime === wordBeginTime ? { ...w, text: newText } : w
            ),
          };
        })
      );
      // 同时更新完整ASR结果
      setAllAsrSegments((prev) =>
        prev.map((s) => {
          if (s.id !== segmentId) return s;
          return {
            ...s,
            words: s.words?.map((w) =>
              w.beginTime === wordBeginTime ? { ...w, text: newText } : w
            ),
          };
        })
      );
    },
    []
  );

  // 编辑片段字幕
  const handleEditSegment = useCallback((segment: Segment) => {
    console.log('[KaipaiEditor] Opening edit modal for segment:', segment.id, segment.text);
    setEditingSegment(segment);
    setIsEditModalOpen(true);
  }, []);

  // 保存字幕修改
  const handleSaveSegmentText = useCallback(
    async (segmentId: string, newText: string) => {
      // 更新前端状态
      setSegments((prev) =>
        prev.map((s) => (s.id === segmentId ? { ...s, text: newText } : s))
      );
      // 同时更新完整ASR结果
      setAllAsrSegments((prev) =>
        prev.map((s) => (s.id === segmentId ? { ...s, text: newText } : s))
      );

      // 保存到后端
      try {
        await fetch(`${API_BASE_URL}/api/kaipai/${editId}/subtitle`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            segment_id: segmentId,
            text: newText,
          }),
        });
      } catch (err) {
        console.error('保存字幕失败:', err);
      }
    },
    [editId]
  );

  // 选中所有静音片段
  const selectAllSilence = useCallback(() => {
    setSegments((prev) =>
      prev.map((s) => (s.type === 'silence' ? { ...s, selected: true } : s))
    );
  }, []);

  // 选中所有含语气词的片段
  const selectAllWithFiller = useCallback(() => {
    setSegments((prev) =>
      prev.map((s) => (s.hasFiller ? { ...s, selected: true } : s))
    );
  }, []);

  // 清除所有选中
  const clearSelection = useCallback(() => {
    setSegments((prev) => prev.map((s) => ({ ...s, selected: false })));
  }, []);

  // 删除选中的片段
  const deleteSelected = useCallback(async () => {
    const selectedSegments = segments.filter((s) => s.selected);
    if (selectedSegments.length === 0) return;

    if (!confirm(`确定要删除选中的 ${selectedSegments.length} 个片段吗？`))
      return;

    const selectedIds = new Set(selectedSegments.map((s) => s.id));

    try {
      // 保存到后端
      const removedSegments = selectedSegments.map((s) => ({
        id: s.id,
        beginTime: s.beginTime,
        endTime: s.endTime,
      }));

      await fetch(`${API_BASE_URL}/api/kaipai/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          removed_segments: removedSegments,
        }),
      });

      // 更新本地状态
      const newSegments = segments.filter((s) => !selectedIds.has(s.id));
      setSegments(newSegments);

      // 更新被删除的ID列表
      const newRemovedIds = new Set([...removedIds, ...selectedIds]);
      setRemovedIds(newRemovedIds);

      // 重新计算总时长
      const total = newSegments.reduce(
        (sum, s) => sum + (s.endTime - s.beginTime),
        0
      );
      setTotalDuration(total / 1000);

      // 重置播放位置
      setCurrentTime(0);
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
      }

      setHistoryCount((c) => c + 1);
    } catch (err) {
      alert('删除失败');
    }
  }, [segments, editId, removedIds]);

  // 撤回删除操作
  const handleUndo = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/kaipai/${editId}/undo`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      if (!response.ok) {
        throw new Error('撤回失败');
      }

      // 重新加载草稿
      const draftResponse = await fetch(
        `${API_BASE_URL}/api/kaipai/${editId}`
      );
      const draftData = await draftResponse.json();

      if (draftData.asr_result?.sentences) {
        const allSegments = draftData.asr_result.sentences.map(
          (s: Segment) => ({
            ...s,
            selected: false,
            expanded: false,
          })
        );

        // 保存完整的ASR结果
        setAllAsrSegments(allSegments);

        const removedIdsSet = new Set(
          (draftData.edit_params?.removed_segments || []).map(
            (s: any) => s.id
          )
        );
        setRemovedIds(removedIdsSet);

        const activeSegments = allSegments.filter(
          (s: Segment) => !removedIdsSet.has(s.id)
        );
        setSegments(activeSegments);

        const total = activeSegments.reduce(
          (sum: number, s: Segment) => sum + (s.endTime - s.beginTime),
          0
        );
        setTotalDuration(total / 1000);
      }

      setCurrentTime(0);
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
      }
      setHistoryCount(draftData.edit_history?.length || 0);
    } catch (err) {
      alert('撤回失败');
    }
  }, [editId]);

  // 导出最终视频
  const exportVideo = useCallback(async () => {
    if (segments.length === 0) {
      alert('没有可导出的内容');
      return;
    }

    setIsExporting(true);
    setExportProgress(0);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/kaipai/${editId}/render`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      const data = await response.json();
      const taskId = data.task_id;

      const checkStatus = setInterval(async () => {
        const statusResponse = await fetch(
          `${API_BASE_URL}/api/kaipai/render/${taskId}/status`
        );
        const statusData = await statusResponse.json();

        setExportProgress(statusData.progress || 0);

        if (statusData.status === 'completed') {
          clearInterval(checkStatus);
          setOutputUrl(statusData.output_url);
          setIsExporting(false);
          alert('视频导出完成！');
        } else if (statusData.status === 'failed') {
          clearInterval(checkStatus);
          alert('导出失败：' + statusData.error);
          setIsExporting(false);
        }
      }, 1000);
    } catch (err) {
      alert('导出失败');
      setIsExporting(false);
    }
  }, [editId, segments.length]);

  // 字幕状态
  const [currentSubtitle, setCurrentSubtitle] = useState('');
  const [activeSegmentId, setActiveSegmentId] = useState<string | null>(null);

  // 处理字幕变化
  const handleSubtitleChange = useCallback((text: string, segmentId: string | null) => {
    setCurrentSubtitle(text);
    setActiveSegmentId(segmentId);
  }, []);

  // 处理时间更新
  const handleTimeUpdate = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  // 保存编辑
  const handleSave = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/kaipai/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          removed_segments: [],
          subtitle_style: {},
          bgm: {},
          template: {},
        }),
      });

      if (!response.ok) {
        throw new Error('保存失败');
      }

      alert('保存成功！');
      onSave?.();
    } catch (err) {
      alert('保存失败：' + (err instanceof Error ? err.message : '请重试'));
    }
  };

  const selectedCount = segments.filter((s) => s.selected).length;
  const progressPercent =
    totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0;

  return (
    <motion.div
      initial={{ y: '100%' }}
      animate={{ y: 0 }}
      exit={{ y: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="fixed inset-0 z-[100] bg-white flex flex-col overflow-hidden"
    >
      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button
          onClick={onBack}
          className="p-2 text-gray-700 hover:bg-gray-100 rounded-full"
        >
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900">网感剪辑</h1>
        <div className="flex items-center gap-2">
          {historyCount > 0 && (
            <button
              onClick={handleUndo}
              className="p-2 text-gray-600 hover:bg-gray-100 rounded-full"
              title="撤回删除"
            >
              <Undo2 size={20} />
            </button>
          )}
          <button
            onClick={handleSave}
            className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded-full font-bold"
          >
            保存
          </button>
        </div>
      </header>

      {/* Video Player */}
      <VideoPlayer
        videoUrl={originalVideoUrl}
        currentTime={currentTime}
        isPlaying={isPlaying}
        subtitle={currentSubtitle}
        progressPercent={progressPercent}
        totalDuration={totalDuration}
        allAsrSegments={allAsrSegments}
        removedIds={removedIds}
        onTogglePlay={togglePlay}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleVideoEnded}
        onSeek={jumpToTime}
        onSubtitleChange={handleSubtitleChange}
      />

      {/* 操作栏 */}
      <div className="bg-white border-b border-gray-100 px-4 py-2 flex items-center justify-between">
        <div className="text-sm text-gray-600">
          {isExporting ? (
            <span className="flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" />
              导出中... {exportProgress}%
            </span>
          ) : (
            <span>
              共 {segments.length} 段，时长 {Math.floor(totalDuration / 60)}:
              {Math.floor(totalDuration % 60).toString().padStart(2, '0')}
            </span>
          )}
        </div>
        <button
          onClick={exportVideo}
          disabled={isExporting || segments.length === 0}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium ${
            segments.length > 0 && !isExporting
              ? 'bg-green-600 text-white'
              : 'bg-gray-200 text-gray-400'
          }`}
        >
          <Download size={14} />
          导出视频
        </button>
      </div>

      {/* 输出视频链接 */}
      {outputUrl && (
        <div className="bg-green-50 border-b border-green-100 px-4 py-2 flex items-center justify-between">
          <span className="text-sm text-green-700">视频已导出</span>
          <a
            href={outputUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-green-600 underline"
          >
            下载视频
          </a>
        </div>
      )}

      {/* Segments List */}
      <div className="flex-1 bg-gray-50 rounded-t-[24px] relative flex flex-col overflow-hidden border-t border-gray-200/50">
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="flex gap-2 items-end h-16 mb-4">
              {[...Array(12)].map((_, i) => (
                <motion.div
                  key={i}
                  animate={{ height: [8, 48, 12, 36, 8] }}
                  transition={{
                    repeat: Infinity,
                    duration: 1,
                    delay: i * 0.08,
                  }}
                  className="w-1.5 bg-blue-500 rounded-full"
                />
              ))}
            </div>
            <h3 className="text-gray-800 text-lg font-bold">{loadingText}</h3>
            {error && (
              <div className="mt-4 flex items-center gap-2 text-red-500 text-sm">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <AlertCircle size={48} className="text-red-400 mb-4" />
            <h3 className="text-gray-800 text-lg font-bold mb-2">出错了</h3>
            <p className="text-gray-500 text-sm">{error}</p>
            <button
              onClick={onBack}
              className="mt-4 px-6 py-2 bg-gray-100 text-gray-700 rounded-full text-sm font-medium"
            >
              返回
            </button>
          </div>
        ) : (
          <>
            {/* Toolbar */}
            <div className="px-4 py-3 bg-white border-b border-gray-100 flex items-center justify-between">
              <div>
                <p className="text-gray-800 text-sm font-bold">文字快剪</p>
                <p className="text-gray-400 text-[10px]">
                  选中 {selectedCount} 段，点击删除按钮删除
                </p>
              </div>
              <button
                onClick={clearSelection}
                className="text-gray-500 text-xs flex items-center gap-1 bg-gray-100 px-3 py-1.5 rounded-full"
              >
                <RotateCcw size={14} /> 清除选中
              </button>
            </div>

            {/* Segments */}
            <div className="flex-1 overflow-y-auto px-4 py-4 scrollbar-hide pb-32">
              {segments.map((segment) => (
                <SegmentItem
                  key={segment.id}
                  segment={segment}
                  isSelected={!!segment.selected}
                  onToggle={toggleSelect}
                  onJump={jumpToTime}
                  onEdit={handleEditSegment}
                  onToggleExpand={toggleExpand}
                  onWordEdit={editWord}
                />
              ))}
            </div>

            {/* Bottom Actions */}
            <div className="absolute bottom-4 inset-x-4 flex items-stretch gap-2">
              <button
                onClick={selectAllSilence}
                className="flex-1 bg-white border border-gray-200 rounded-xl py-3 flex flex-col items-center gap-1 hover:bg-gray-50"
              >
                <VolumeX size={18} className="text-gray-500" />
                <span className="text-[10px] text-gray-600">选静音</span>
              </button>
              <button
                onClick={selectAllWithFiller}
                className="flex-1 bg-white border border-gray-200 rounded-xl py-3 flex flex-col items-center gap-1 hover:bg-gray-50"
              >
                <Zap size={18} className="text-gray-500" />
                <span className="text-[10px] text-gray-600">选语气词</span>
              </button>
              <button
                onClick={deleteSelected}
                disabled={selectedCount === 0}
                className={`flex-[2] rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all ${
                  selectedCount > 0
                    ? 'bg-red-600 text-white'
                    : 'bg-gray-200 text-gray-400'
                }`}
              >
                <Trash2 size={18} /> 删除 ({selectedCount})
              </button>
            </div>
          </>
        )}
      </div>

      {/* Edit Modal */}
      <EditModal
        isOpen={isEditModalOpen}
        segment={editingSegment}
        onClose={() => setIsEditModalOpen(false)}
        onSave={handleSaveSegmentText}
      />
    </motion.div>
  );
}
