/**
 * 客户端渲染结果屏幕
 * 支持本地视频拼接和 Blob URL 播放
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ChevronLeft, CheckCircle2, Circle, Clock, Download, Play, Loader2, Pause, Square, Scissors, Monitor } from 'lucide-react';
import KaipaiEditor from './KaipaiEditor';
import OptimizedVideoPlayer from './OptimizedVideoPlayer';
import { renderPreview, renderHD, RenderResult, releaseBlobUrl } from '../utils/clientRenderer';
import { exportVideoToOSS, downloadVideo, generateExportFilename } from '../utils/clientExport';
import { detectDeviceCapability } from '../utils/deviceCapability';
import type { Combination as ComboType } from '../utils/combinationGenerator';

interface Material {
  id: string;
  type: 'video' | 'image';
  url: string;
  thumbnail: string;
  duration?: string;
  name: string;
}

interface Combination {
  id: string;
  index: number;
  materials: Material[];
  thumbnail: string;
  duration: string;
  duration_seconds: number;
  tag: string;
  preview_status?: 'pending' | 'processing' | 'completed' | 'failed';
  preview_url?: string;
}

interface ResultItem {
  id: string;
  index: number;
  tag: string;
  duration: string;
  selected: boolean;
  thumbnail: string;
  materials: Material[];
  preview_status: 'pending' | 'processing' | 'completed' | 'failed';
  preview_url?: string;
}

const FILTERS = ['全部', '完全不重复', '极低重复率', '普通'];
const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

interface ClientResultsScreenProps {
  onBack: () => void;
  combinations?: Combination[];
  defaultQuality?: 'low' | 'medium' | 'high' | 'ultra';
}

export default function ClientResultsScreen({
  onBack,
  combinations: initialCombinations,
  defaultQuality = 'medium'
}: ClientResultsScreenProps) {
  const [results, setResults] = useState<ResultItem[]>([]);
  const [activeFilter, setActiveFilter] = useState(FILTERS[0]);
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set());
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [previewProgress, setPreviewProgress] = useState({ completed: 0, total: 0 });

  // Kaipai Editor state
  const [showKaipaiEditor, setShowKaipaiEditor] = useState(false);
  const [kaipaiEditId, setKaipaiEditId] = useState<string>('');
  const [kaipaiVideoUrl, setKaipaiVideoUrl] = useState<string>('');
  const [kaipaiLoadingId, setKaipaiLoadingId] = useState<string | null>(null);

  // Client rendering state
  const [useClientRendering, setUseClientRendering] = useState<boolean | null>(null);
  const [renderingItems, setRenderingItems] = useState<Map<string, { progress: number; stage: string }>>(new Map());
  const [localVideos, setLocalVideos] = useState<Map<string, string>>(new Map());
  const blobUrlsRef = useRef<Set<string>>(new Set());

  // Initialize
  useEffect(() => {
    checkClientRenderingSupport();
  }, []);

  // Initialize results from props
  useEffect(() => {
    if (initialCombinations && initialCombinations.length > 0) {
      const items: ResultItem[] = initialCombinations.map(combo => ({
        id: combo.id,
        index: combo.index,
        tag: combo.tag,
        duration: combo.duration,
        selected: false,
        thumbnail: combo.thumbnail,
        materials: combo.materials,
        preview_status: combo.preview_status || 'pending',
        preview_url: combo.preview_url
      }));
      setResults(items);
      setPreviewProgress({ completed: 0, total: items.length });
    }
  }, [initialCombinations]);

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      blobUrlsRef.current.forEach(url => releaseBlobUrl(url));
      blobUrlsRef.current.clear();
    };
  }, []);

  const checkClientRenderingSupport = async () => {
    try {
      const capability = await detectDeviceCapability();
      setUseClientRendering(capability.canUseClientRendering);
    } catch {
      setUseClientRendering(false);
    }
  };

  const selectedCount = results.filter(r => r.selected).length;
  const allSelected = selectedCount === results.length && results.length > 0;

  const toggleSelectAll = () => {
    setResults(results.map(r => ({ ...r, selected: !allSelected })));
  };

  const toggleSelect = (id: string) => {
    setResults(results.map(r => r.id === id ? { ...r, selected: !r.selected } : r));
  };

  // Client-side render a combination
  const clientRender = async (item: ResultItem): Promise<string | null> => {
    if (!useClientRendering) return null;

    try {
      setRenderingItems(prev => new Map(prev).set(item.id, { progress: 0, stage: '准备中...' }));

      // Build combination for client renderer
      const combo = {
        id: item.id,
        materials: item.materials.map(m => ({
          id: m.id,
          duration: parseDuration(m.duration) || 3,
        })),
      };

      const result = await renderPreview(combo, {
        onProgress: (progress, stage) => {
          setRenderingItems(prev => new Map(prev).set(item.id, {
            progress: Math.round(progress),
            stage: getStageLabel(stage),
          }));
        },
      });

      if (result) {
        // Store blob URL
        blobUrlsRef.current.add(result.blobUrl);
        setLocalVideos(prev => new Map(prev).set(item.id, result.blobUrl));

        setResults(prev => prev.map(r =>
          r.id === item.id ? { ...r, preview_status: 'completed', preview_url: result.blobUrl } : r
        ));

        return result.blobUrl;
      }

      return null;
    } catch (error) {
      console.error('[ClientResults] 本地渲染失败:', error);
      setResults(prev => prev.map(r =>
        r.id === item.id ? { ...r, preview_status: 'failed' } : r
      ));
      return null;
    } finally {
      setRenderingItems(prev => {
        const next = new Map(prev);
        next.delete(item.id);
        return next;
      });
    }
  };

  // Server-side render (fallback)
  const serverRender = async (item: ResultItem): Promise<string | null> => {
    try {
      setResults(prev => prev.map(r =>
        r.id === item.id ? { ...r, preview_status: 'processing' } : r
      ));

      const response = await fetch(`${API_BASE_URL}/api/combinations/${item.id}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) throw new Error('启动拼接失败');

      const data = await response.json();

      if (data.status === 'completed') {
        setResults(prev => prev.map(r =>
          r.id === item.id ? { ...r, preview_status: 'completed', preview_url: data.video_url } : r
        ));
        return data.video_url;
      } else if (data.status === 'processing') {
        return await waitForServerRender(data.task_id, item.id);
      }

      return null;
    } catch (error) {
      console.error('服务器渲染失败:', error);
      setResults(prev => prev.map(r =>
        r.id === item.id ? { ...r, preview_status: 'failed' } : r
      ));
      return null;
    }
  };

  const waitForServerRender = async (taskId: string, itemId: string): Promise<string | null> => {
    return new Promise((resolve) => {
      const checkInterval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/status`);
          const data = await response.json();

          if (data.status === 'completed') {
            clearInterval(checkInterval);
            setResults(prev => prev.map(r =>
              r.id === itemId ? { ...r, preview_status: 'completed', preview_url: data.video_url } : r
            ));
            resolve(data.video_url);
          } else if (data.status === 'failed') {
            clearInterval(checkInterval);
            setResults(prev => prev.map(r =>
              r.id === itemId ? { ...r, preview_status: 'failed' } : r
            ));
            resolve(null);
          }
        } catch (error) {
          console.error('查询渲染状态失败:', error);
        }
      }, 500);

      setTimeout(() => {
        clearInterval(checkInterval);
        resolve(null);
      }, 30000);
    });
  };

  // Auto-render: try client first, fallback to server
  const autoRender = async (item: ResultItem): Promise<string | null> => {
    // Try client rendering first
    if (useClientRendering) {
      const clientUrl = await clientRender(item);
      if (clientUrl) return clientUrl;
    }

    // Fallback to server rendering
    return await serverRender(item);
  };

  const handlePlay = useCallback(async (item: ResultItem) => {
    if (playingId === item.id) {
      setPlayingId(null);
      return;
    }

    // If already has video URL, play directly
    if (item.preview_status === 'completed' && item.preview_url) {
      setPlayingId(item.id);
      return;
    }

    // For pending items: show player immediately, generate in background
    if (item.preview_status === 'pending' || item.preview_status === 'failed') {
      setPlayingId(item.id);

      const videoUrl = await autoRender(item);
      if (!videoUrl) {
        setPlayingId(null);
      }
    }
  }, [playingId, useClientRendering]);

  const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
    e.stopPropagation();

    let videoUrl = item.preview_url;

    // If video not ready, render first
    if (item.preview_status !== 'completed' || !videoUrl) {
      videoUrl = await autoRender(item);
      if (!videoUrl) {
        alert('视频渲染失败，请重试');
        return;
      }
    }

    setDownloadingIds(prev => new Set(prev).add(item.id));

    try {
      if (videoUrl.startsWith('blob:')) {
        // Local blob - download directly
        const response = await fetch(videoUrl);
        const blob = await response.blob();
        downloadVideo(blob, generateExportFilename(item.id, 'hd'));
      } else {
        // Server URL - use existing download logic
        await downloadFromUrl(videoUrl, `mixcut_${item.id}.mp4`);
      }
    } catch (error) {
      console.error('下载失败:', error);
      alert('下载失败：' + (error instanceof Error ? error.message : '请重试'));
    } finally {
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  }, [useClientRendering]);

  const downloadFromUrl = async (url: string, filename: string) => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('获取视频失败');
    const blob = await response.blob();
    downloadVideo(blob, filename);
  };

  const handleBatchDownload = useCallback(async () => {
    const selectedItems = results.filter(r => r.selected);
    if (selectedItems.length === 0) {
      alert('请先选择要下载的视频');
      return;
    }

    for (const item of selectedItems) {
      try {
        let videoUrl = item.preview_url;

        if (item.preview_status !== 'completed' || !videoUrl) {
          videoUrl = await autoRender(item);
        }

        if (videoUrl) {
          if (videoUrl.startsWith('blob:')) {
            const response = await fetch(videoUrl);
            const blob = await response.blob();
            downloadVideo(blob, generateExportFilename(item.id, 'hd'));
          } else {
            await downloadFromUrl(videoUrl, `mixcut_${item.id}.mp4`);
          }
        }

        await new Promise(resolve => setTimeout(resolve, 1000));
      } catch (error) {
        console.error('批量下载失败:', error);
      }
    }
  }, [results, useClientRendering]);

  const handleOpenKaipai = useCallback(async () => {
    const selectedItems = results.filter(r => r.selected);
    if (selectedItems.length === 0) {
      alert('请先选择一个视频');
      return;
    }
    if (selectedItems.length > 1) {
      alert('请只选择一个视频进行文字快剪');
      return;
    }

    const item = selectedItems[0];

    let videoUrl = item.preview_url;
    if (item.preview_status !== 'completed' || !videoUrl) {
      setKaipaiLoadingId(item.id);
      videoUrl = await autoRender(item);
      setKaipaiLoadingId(null);
      if (!videoUrl) {
        alert('视频合成失败，请重试');
        return;
      }
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/renders/${item.id}/kaipai/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '创建剪辑任务失败');
      }

      const data = await response.json();
      setKaipaiEditId(data.edit_id);
      setKaipaiVideoUrl(data.video_url);
      setShowKaipaiEditor(true);
    } catch (error: any) {
      alert('创建剪辑任务失败：' + error.message);
    }
  }, [results, useClientRendering]);

  const handleCloseKaipai = () => {
    setShowKaipaiEditor(false);
    setKaipaiEditId('');
    setKaipaiVideoUrl('');
  };

  const getStageLabel = (stage: string): string => {
    const labels: Record<string, string> = {
      loading_materials: '加载素材...',
      concatenating: '拼接中...',
      saving: '保存中...',
      completed: '完成',
    };
    return labels[stage] || stage;
  };

  const filteredResults = activeFilter === '全部'
    ? results
    : results.filter(r => r.tag === activeFilter);

  const getTagColor = (tag: string) => {
    switch (tag) {
      case '完全不重复': return 'bg-green-500';
      case '极低重复率': return 'bg-purple-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusDisplay = (status: string, itemId: string) => {
    const rendering = renderingItems.get(itemId);
    if (rendering) {
      return { text: `${rendering.stage} ${rendering.progress}%`, color: 'text-blue-400' };
    }

    switch (status) {
      case 'completed': return { text: '可播放', color: 'text-green-400' };
      case 'processing': return { text: '生成中...', color: 'text-yellow-400' };
      case 'failed': return { text: '失败', color: 'text-red-400' };
      default: return { text: '等待中', color: 'text-gray-400' };
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 z-10 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <button onClick={onBack} className="p-1 -ml-1 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
            <ChevronLeft size={24} />
          </button>
          <h1 className="font-semibold text-gray-900 text-base">混剪结果</h1>
        </div>
        <div className="flex items-center gap-2">
          {useClientRendering !== null && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1 ${
              useClientRendering ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
            }`}>
              <Monitor size={10} />
              {useClientRendering ? '本地渲染' : '云端渲染'}
            </span>
          )}
          <span className="text-xs text-gray-500 flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              预览生成中 {previewProgress.completed}/{previewProgress.total}
            </span>
          </span>
        </div>
      </header>

      {/* Filters */}
      <div className="bg-white py-2 px-3 shrink-0 border-b border-gray-100">
        <div className="flex gap-2 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] pb-1">
          {FILTERS.map(filter => {
            const count = filter === '全部'
              ? results.length
              : results.filter(r => r.tag === filter).length;
            return (
              <button
                key={filter}
                onClick={() => setActiveFilter(filter)}
                className={`whitespace-nowrap px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  activeFilter === filter
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {filter}({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Video Grid */}
      <div className="flex-1 overflow-y-auto p-2 pb-24">
        {results.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Clock size={48} className="mb-4 opacity-50" />
            <p className="text-sm">暂无混剪结果</p>
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-2">
            {filteredResults.map((item) => {
              const statusDisplay = getStatusDisplay(item.preview_status, item.id);
              const isPlaying = playingId === item.id;
              const isRendering = renderingItems.has(item.id);

              return (
                <div
                  key={item.id}
                  className={`relative bg-black rounded-lg overflow-hidden ${
                    item.selected ? 'ring-2 ring-blue-500' : ''
                  }`}
                >
                  <div className="relative w-full" style={{ paddingBottom: '177.78%' }}>
                    {isPlaying ? (
                      <div className="absolute inset-0 bg-black">
                        {item.preview_url ? (
                          <OptimizedVideoPlayer
                            itemId={item.id}
                            videoUrl={item.preview_url}
                            isCached={item.preview_url.startsWith('blob:')}
                            apiBaseUrl={API_BASE_URL}
                          />
                        ) : (
                          <div className="absolute inset-0 flex flex-col items-center justify-center text-white">
                            <Loader2 size={32} className="animate-spin mb-2" />
                            <span className="text-xs text-gray-400">加载中...</span>
                          </div>
                        )}
                        <button
                          onClick={() => setPlayingId(null)}
                          className="absolute top-1 right-1 w-6 h-6 bg-black/50 rounded-full flex items-center justify-center text-white z-10"
                        >
                          <Square size={12} fill="currentColor" />
                        </button>
                      </div>
                    ) : (
                      <div className="absolute inset-0 bg-black">
                        <img
                          src={`${API_BASE_URL}${item.thumbnail}`}
                          alt="cover"
                          className="w-full h-full object-cover"
                        />

                        {/* Play Button */}
                        <button
                          onClick={() => handlePlay(item)}
                          disabled={isRendering}
                          className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/50 transition-colors disabled:opacity-50"
                        >
                          {isRendering ? (
                            <div className="flex flex-col items-center text-white">
                              <Loader2 size={24} className="animate-spin mb-1" />
                              <span className="text-[10px]">
                                {renderingItems.get(item.id)?.progress}%
                              </span>
                            </div>
                          ) : (
                            <div className="w-10 h-10 bg-white/90 rounded-full flex items-center justify-center">
                              <Play size={18} className="text-blue-600 ml-0.5" fill="currentColor" />
                            </div>
                          )}
                        </button>

                        {/* Downloading Overlay */}
                        {downloadingIds.has(item.id) && (
                          <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center text-white">
                            <Loader2 size={20} className="animate-spin mb-1" />
                            <span className="text-[10px]">下载中...</span>
                          </div>
                        )}

                        {/* Selection Checkbox */}
                        <div
                          className="absolute top-1 left-1 z-10"
                          onClick={(e) => { e.stopPropagation(); toggleSelect(item.id); }}
                        >
                          {item.selected ? (
                            <CheckCircle2 size={16} className="text-blue-500 fill-white" />
                          ) : (
                            <Circle size={16} className="text-white/80 drop-shadow-md" />
                          )}
                        </div>

                        {/* Tag */}
                        <div className="absolute top-1 right-1">
                          <span className={`text-[9px] px-1 py-0.5 rounded text-white font-medium ${getTagColor(item.tag)}`}>
                            {item.tag}
                          </span>
                        </div>

                        {/* Duration */}
                        <div className="absolute bottom-1 right-1 flex items-center gap-0.5 bg-black/60 text-white text-[9px] px-1 py-0.5 rounded">
                          <Clock size={8} />
                          {item.duration}
                        </div>

                        {/* Download Button */}
                        <button
                          onClick={(e) => handleDownload(item, e)}
                          disabled={downloadingIds.has(item.id) || isRendering}
                          className="absolute bottom-1 left-1 w-6 h-6 bg-blue-600 rounded-full flex items-center justify-center text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
                        >
                          <Download size={12} />
                        </button>

                        {/* Status indicator */}
                        <div className="absolute bottom-1 left-1/2 transform -translate-x-1/2">
                          <span className={`text-[8px] px-1 py-0.5 rounded bg-black/60 ${statusDisplay.color}`}>
                            {statusDisplay.text}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom Action Bar */}
      {results.length > 0 && (
        <div className="absolute bottom-16 left-0 right-0 bg-white border-t border-gray-200 p-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button onClick={toggleSelectAll} className="flex items-center gap-1 text-gray-700">
              {allSelected ? <CheckCircle2 size={18} className="text-blue-600" /> : <Circle size={18} className="text-gray-400" />}
              <span className="text-xs font-medium">全选</span>
            </button>
            <span className="text-xs text-gray-500">已选 <strong className="text-blue-600">{selectedCount}</strong></span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleOpenKaipai}
              disabled={selectedCount !== 1 || kaipaiLoadingId !== null}
              className={`flex items-center gap-1 px-4 py-2 rounded-full font-medium text-xs ${
                selectedCount === 1 && !kaipaiLoadingId
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              {kaipaiLoadingId ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Scissors size={14} />
              )}
              文字快剪
            </button>
            <button
              onClick={handleBatchDownload}
              disabled={selectedCount === 0}
              className={`flex items-center gap-1 px-4 py-2 rounded-full font-medium text-xs ${
                selectedCount > 0
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              <Download size={14} />
              下载选中 ({selectedCount})
            </button>
          </div>
        </div>
      )}

      {/* Kaipai Editor Modal */}
      {showKaipaiEditor && kaipaiEditId && (
        <KaipaiEditor
          editId={kaipaiEditId}
          videoUrl={kaipaiVideoUrl}
          onBack={handleCloseKaipai}
          onSave={handleCloseKaipai}
        />
      )}
    </div>
  );
}

// Parse duration string
function parseDuration(durationStr?: string): number {
  if (!durationStr) return 0;
  const parts = durationStr.split(':').map(Number);
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return Number(durationStr) || 0;
}
