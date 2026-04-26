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
  LayoutTemplate,
  X,
  Cpu,
} from 'lucide-react';
import SegmentItem from './SegmentItem';
import EditModal from './EditModal';
import UnifiedPlayer, { type UnifiedPlayerRef } from './UnifiedPlayer';
import { saveVideo, getVideo } from '../../utils/videoStorage';
import type { Segment } from './types';
import { useClientRendering } from '../../hooks/useClientRendering';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

// 模板类型定义
interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  preview_url?: string;
}

interface KaipaiEditorProps {
  editId: string;
  videoUrl: string;          // 视频①：服务器高质量视频URL（用于ASR/导出）
  clientVideoUrl?: string;   // 视频②：客户端预览视频URL（用于编辑器预览播放）
  onBack: () => void;
  onSave?: () => void;
}

export default function KaipaiEditor({
  editId,
  videoUrl,
  clientVideoUrl,
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

  // 模板相关状态
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  
  // 当前激活的标签页: 'edit' | 'template'
  const [activeTab, setActiveTab] = useState<'edit' | 'template'>('edit');

  // 原始视频URL（从草稿获取）
  const [originalVideoUrl, setOriginalVideoUrl] = useState<string>('');

  // 预览视频URL（优先使用导出的视频，如果没有则使用原始视频）
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string>('');

  // 视频ID（用于本地缓存）
  const [videoId, setVideoId] = useState<string>('');

  // 存储完整的ASR结果（包含被删除的片段）用于跳转判断
  const [allAsrSegments, setAllAsrSegments] = useState<Segment[]>([]);
  // 存储被删除的片段ID
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());
  // 是否已缓存到本地
  const [isVideoCached, setIsVideoCached] = useState(false);
  // 是否正在下载中（防止重复下载）
  const isDownloadingRef = useRef(false);

  // UnifiedPlayer ref 用于调用播放器方法
  const unifiedPlayerRef = useRef<UnifiedPlayerRef>(null);

  const videoRef = useRef<HTMLVideoElement>(null);

  // 客户端渲染状态
  const { state: clientRenderState } = useClientRendering();
  const [showClientRenderPanel, setShowClientRenderPanel] = useState(false);
  const [clientExportBlob, setClientExportBlob] = useState<Blob | null>(null);

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

        // 保存原始视频URL（视频①：服务器高质量视频，用于ASR/导出）
        if (draftData.original_video_url) {
          setOriginalVideoUrl(draftData.original_video_url);
          
          // ========== 双轨制：预览视频URL选择 ==========
          // 优先级：1. 已导出视频 2. 视频②（客户端预览视频）3. 视频①（服务器高质量视频）
          const exportedUrl = draftData.output_video_url || draftData.output_url;
          if (exportedUrl) {
            setPreviewVideoUrl(exportedUrl);
            setOutputUrl(exportedUrl);
            console.log('[预览] 使用已导出的视频:', exportedUrl);
          } else if (clientVideoUrl) {
            // 使用视频②（客户端预览视频）进行预览播放
            setPreviewVideoUrl(clientVideoUrl);
            console.log('[预览] 使用视频②（客户端预览视频）:', clientVideoUrl);
          } else {
            // 降级使用视频①（服务器高质量视频）
            setPreviewVideoUrl(draftData.original_video_url);
            console.log('[预览] 使用视频①（服务器高质量视频）:', draftData.original_video_url);
          }

          // 设置视频ID - 使用 editId 作为唯一标识
          setVideoId(editId);

          // 尝试缓存视频到本地（用于WebCodecs播放）
          // 优先缓存视频②（如果有），因为预览时播放的是视频②
          const cacheUrl = clientVideoUrl || draftData.original_video_url;
          cacheVideoToLocal(editId, cacheUrl);
        }

        // 加载ASR结果
        if (draftData.asr_result && draftData.asr_result.sentences) {
          // 输出DeepSeek提取状态（从缓存加载时）
          console.log('[DeepSeek] 从缓存加载，提取状态:', draftData.extract_status);
          if (draftData.extracted_title) {
            console.log('[DeepSeek] 已提取标题:', draftData.extracted_title);
          }
          if (draftData.extracted_keywords) {
            console.log('[DeepSeek] 已提取关键词:', draftData.extracted_keywords);
          }

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

          // 恢复已选择的模板
          if (draftData.template) {
            setSelectedTemplate(draftData.template);
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

  // 缓存视频到本地存储
  const cacheVideoToLocal = async (vid: string, videoUrl: string) => {
    // 防止重复下载
    if (isDownloadingRef.current) {
      console.log('[缓存] 下载正在进行中，跳过重复请求');
      return;
    }

    try {
      // 检查是否已缓存
      const { hasVideoInLocal } = await import('../../utils/videoStorage');
      const hasLocal = await hasVideoInLocal(vid);

      if (hasLocal) {
        console.log('[缓存] 视频已在本地:', vid);
        setIsVideoCached(true);
        return;
      }

      // 标记开始下载
      isDownloadingRef.current = true;

      // 判断视频URL类型
      const isOSSUrl = videoUrl.includes('aliyuncs.com') || videoUrl.includes('oss-');
      
      // 如果是OSS链接，使用后端代理接口避免CORS
      const downloadUrl = isOSSUrl 
        ? `${API_BASE_URL}/api/kaipai/${editId}/video`
        : videoUrl;
      
      console.log('[缓存] 开始下载视频:', isOSSUrl ? '通过后端代理' : '直接下载');
      const response = await fetch(downloadUrl);
      if (!response.ok) {
        throw new Error('下载视频失败');
      }

      const blob = await response.blob();
      const file = new File([blob], `${vid}.mp4`, { type: 'video/mp4' });

      // 保存到本地
      await saveVideo(vid, file);
      console.log('[缓存] 视频已缓存到本地:', vid, '大小:', (file.size / 1024 / 1024).toFixed(2), 'MB');
      setIsVideoCached(true);
    } catch (err) {
      console.error('[缓存] 缓存视频失败:', err);
      setIsVideoCached(false);
    } finally {
      // 标记下载结束
      isDownloadingRef.current = false;
    }
  };

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
          // 输出DeepSeek提取状态到控制台
          console.log('[DeepSeek] ASR完成，提取状态:', data.extract_status);
          console.log('[DeepSeek] 完整响应:', data);
          
          if (data.extract_status === 'completed') {
            console.log('[DeepSeek] ✅ 提取完成:');
            console.log('  标题:', data.extracted_title);
            console.log('  关键词:', data.extracted_keywords);
          } else if (data.extract_status === 'failed') {
            console.error('[DeepSeek] ❌ 提取失败:', data.extract_error);
          } else if (data.extract_status === 'timeout') {
            console.warn('[DeepSeek] ⏱️ 提取超时');
          } else if (data.extract_status === 'processing') {
            console.log('[DeepSeek] ⏳ 正在提取中...');
          } else if (data.extract_status === 'unknown') {
            console.warn('[DeepSeek] ⚠️ 提取状态未知');
          }

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
          
          // 如果DeepSeek还在处理中，继续轮询
          if (data.extract_status === 'processing') {
            setTimeout(checkStatus, 2000);
            return;
          }
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
        // 检查当前时间是否在被删除范围内（包含边界）
        if (
          currentTimeMs >= range.beginTime &&
          currentTimeMs <= range.endTime
        ) {
          // 当前时间在被删除范围内，跳转到结束时间的下一秒
          // 这样可以确保跳转到被删除片段之后的有效内容
          console.log('[getNextValidTime] 时间', currentTimeMs, '在被删除范围内', range, '跳转到', range.endTime + 100);
          return range.endTime + 100; // 加100ms确保跳过
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
      
      // 调用播放器的跳转方法
      if (unifiedPlayerRef.current) {
        unifiedPlayerRef.current.seekTo(finalTime);
      }
      
      // 更新状态
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

  // 加载模板列表
  const loadTemplates = useCallback(async () => {
    if (templates.length > 0) return; // 已加载过
    setLoadingTemplates(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/kaipai/templates`);
      if (response.ok) {
        const data = await response.json();
        setTemplates(data.templates || []);
      }
    } catch (err) {
      console.error('加载模板失败:', err);
    } finally {
      setLoadingTemplates(false);
    }
  }, [templates.length]);

  // 切换到模板标签时加载模板
  useEffect(() => {
    if (activeTab === 'template') {
      loadTemplates();
    }
  }, [activeTab, loadTemplates]);

  // 选择模板
  const selectTemplate = useCallback(async (template: Template | null) => {
    try {
      // 如果点击的是当前已选中的模板，则取消选择
      if (template && selectedTemplate?.id === template.id) {
        template = null;
      }
      
      // 保存到后端
      const response = await fetch(`${API_BASE_URL}/api/kaipai/${editId}/template`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: template?.id || null
        }),
      });

      if (response.ok) {
        setSelectedTemplate(template);
      } else {
        alert('选择模板失败');
      }
    } catch (err) {
      console.error('选择模板失败:', err);
      alert('选择模板失败');
    }
  }, [editId, selectedTemplate]);

  // 导出最终视频（调用服务器接口）
  const exportVideo = useCallback(async () => {
    if (segments.length === 0) {
      alert('没有可导出的内容');
      return;
    }

    setIsExporting(true);
    setExportProgress(0);

    // 调用服务器渲染接口
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/kaipai/${editId}/export`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      const data = await response.json();
      const taskId = data.task_id;

      const checkStatus = setInterval(async () => {
        const statusResponse = await fetch(
          `${API_BASE_URL}/api/kaipai/render/${taskId}/status?edit_id=${editId}`
        );
        const statusData = await statusResponse.json();

        setExportProgress(statusData.progress || 0);

        if (statusData.status === 'completed') {
          clearInterval(checkStatus);
          setOutputUrl(statusData.output_url);
          // 更新预览视频为导出的视频
          setPreviewVideoUrl(statusData.output_url);
          console.log('[预览] 导出完成，更新预览视频:', statusData.output_url);
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
          {/* 客户端渲染状态指示 */}
          {clientRenderState.isEnabled && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-[10px] rounded-full">
              <Cpu size={10} />
              客户端
            </span>
          )}
          <button
            onClick={() => setShowClientRenderPanel(!showClientRenderPanel)}
            className={`p-1.5 rounded-full transition-colors ${clientRenderState.isEnabled ? 'text-green-600 bg-green-50' : 'text-gray-400 hover:text-gray-600'}`}
            title="客户端渲染设置"
          >
            <Cpu size={16} />
          </button>
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

      {/* 客户端渲染面板 */}
      {showClientRenderPanel && (
        <div className="bg-white border-b border-gray-200 p-3 mx-2 mt-2 rounded-xl shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Cpu size={16} className={clientRenderState.isEnabled ? 'text-green-600' : 'text-gray-500'} />
              <span className="font-medium text-sm text-gray-900">客户端渲染</span>
              {clientRenderState.isEnabled && (
                <span className="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] rounded-full">已启用</span>
              )}
            </div>
          </div>
          {clientRenderState.capability ? (
            <div className="space-y-1 text-xs text-gray-600">
              <div>性能等级: {clientRenderState.capability.performanceLevel}</div>
              <div className="flex gap-1">
                <span className={`px-1.5 py-0.5 rounded ${clientRenderState.capability.supportsFFmpeg ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  FFmpeg
                </span>
                <span className={`px-1.5 py-0.5 rounded ${clientRenderState.capability.supportsOPFS ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  OPFS
                </span>
                <span className={`px-1.5 py-0.5 rounded ${clientRenderState.capability.supportsWebCodecs ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  WebCodecs
                </span>
              </div>
              <div className="text-[10px] text-gray-500">
                客户端导出将在浏览器本地完成视频裁剪，速度更快
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-500">检测设备能力...</div>
          )}
        </div>
      )}

      {/* 主内容区 - 视频预览 */}
      <div className="flex-1 flex flex-col min-h-0">
        {videoId && previewVideoUrl ? (
          <UnifiedPlayer
            ref={unifiedPlayerRef}
            videoId={videoId}
            videoUrl={previewVideoUrl}
            segments={allAsrSegments}
            removedIds={removedIds}
            onTimeUpdate={handleTimeUpdate}
            onSegmentChange={handleSubtitleChange}
            onEnded={handleVideoEnded}
          />
        ) : (
          <div className="flex items-center justify-center h-full bg-gray-900 text-white">
            <div className="text-center">
              <Loader2 size={32} className="animate-spin mx-auto mb-2" />
              <p className="text-sm text-gray-400">加载视频...</p>
            </div>
          </div>
        )}
      </div>

      {/* 操作栏 */}
      <div className="bg-white border-t border-gray-100 px-4 py-2 flex items-center justify-between shrink-0">
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
        <div className="flex items-center gap-2">
          {/* 单个切换按钮 */}
          <button
            onClick={() => setActiveTab(activeTab === 'edit' ? 'template' : 'edit')}
            className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
              activeTab === 'template'
                ? 'bg-purple-600 text-white'
                : 'bg-blue-600 text-white'
            }`}
          >
            {activeTab === 'edit' ? '网感模板' : '文字快剪'}
          </button>
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
            导出
          </button>
        </div>
      </div>

      {/* 输出视频链接 */}
      {outputUrl && (
        <div className="bg-green-50 border-t border-green-100 px-4 py-2 flex items-center justify-between shrink-0">
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

      {/* 下栏区域 - 动态高度 */}
      <div 
        className={`bg-gray-50 relative flex flex-col overflow-hidden border-t border-gray-200/50 transition-all duration-300 shrink-0 ${
          activeTab === 'template' ? 'h-[180px]' : 'h-[45%] min-h-[300px]'
        }`}
      >
        {/* 文字快剪内容 */}
        {activeTab === 'edit' && (
          <>
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
                {/* Toolbar - 简化版 */}
                <div className="px-4 py-2 bg-white border-b border-gray-100 flex items-center justify-between">
                  <p className="text-gray-400 text-[10px]">
                    选中 {selectedCount} 段
                  </p>
                  <button
                    onClick={clearSelection}
                    className="text-gray-500 text-xs flex items-center gap-1 bg-gray-100 px-3 py-1.5 rounded-full"
                  >
                    <RotateCcw size={14} /> 清除选中
                  </button>
                </div>

                {/* Segments */}
                <div className="flex-1 overflow-y-auto px-4 py-4 scrollbar-hide pb-28">
                  {segments.map((segment, index) => (
                    <SegmentItem
                      key={index}
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
                <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-3 flex items-stretch gap-2">
                  <button
                    onClick={selectAllSilence}
                    className="flex-1 bg-gray-50 border border-gray-200 rounded-xl py-2.5 flex flex-col items-center gap-0.5 hover:bg-gray-100"
                  >
                    <VolumeX size={16} className="text-gray-500" />
                    <span className="text-[10px] text-gray-600">选静音</span>
                  </button>
                  <button
                    onClick={selectAllWithFiller}
                    className="flex-1 bg-gray-50 border border-gray-200 rounded-xl py-2.5 flex flex-col items-center gap-0.5 hover:bg-gray-100"
                  >
                    <Zap size={16} className="text-gray-500" />
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
                    <Trash2 size={16} /> 删除 ({selectedCount})
                  </button>
                </div>
              </>
            )}
          </>
        )}

        {/* 网感模板内容 */}
        {activeTab === 'template' && (
          <div className="flex-1 flex flex-col">
            {/* 模板列表 - 横向滑动 */}
            <div className="flex-1 overflow-x-auto overflow-y-hidden py-4 px-4">
              {loadingTemplates ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 size={24} className="animate-spin text-blue-500" />
                </div>
              ) : (
                <div className="flex gap-4 h-full items-center">
                  {/* 模板封面列表 */}
                  {templates.map((template) => {
                    const isNoTemplate = template.name === '无模板' || template.category === 'none';
                    const isSelected = selectedTemplate?.id === template.id;
                    
                    return (
                    <button
                      key={template.id}
                      onClick={() => selectTemplate(template)}
                      className={`relative shrink-0 w-[100px] flex flex-col items-center gap-2 transition-all ${
                        isSelected ? 'scale-105' : ''
                      }`}
                    >
                      {/* 封面图 - 占满整个框 */}
                      <div 
                        className={`w-[100px] h-[130px] rounded-xl overflow-hidden border-2 transition-all ${
                          isSelected
                            ? isNoTemplate 
                              ? 'border-gray-400 shadow-lg' 
                              : 'border-purple-500 shadow-lg'
                            : 'border-gray-200'
                        }`}
                      >
                        {template.preview_url && !isNoTemplate ? (
                          <img 
                            src={template.preview_url} 
                            alt={template.name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className={`w-full h-full flex items-center justify-center ${
                            isNoTemplate 
                              ? 'bg-gradient-to-br from-gray-100 to-gray-200' 
                              : 'bg-gradient-to-br from-purple-100 to-blue-100'
                          }`}>
                            {isNoTemplate ? (
                              <X size={32} className="text-gray-400" />
                            ) : (
                              <LayoutTemplate size={32} className="text-purple-300" />
                            )}
                          </div>
                        )}
                      </div>
                      {/* 模板名称 - 下方 */}
                      <span className={`text-[11px] text-center font-medium leading-tight ${
                        isSelected 
                          ? isNoTemplate ? 'text-gray-600' : 'text-purple-600'
                          : 'text-gray-700'
                      }`}>
                        {template.name}
                      </span>
                      {/* 选中标记 */}
                      {isSelected && (
                        <div className={`absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center shadow-md ${
                          isNoTemplate ? 'bg-gray-500' : 'bg-purple-500'
                        }`}>
                          <Check size={12} className="text-white" />
                        </div>
                      )}
                    </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
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
