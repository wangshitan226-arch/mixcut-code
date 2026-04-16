import React, { useState, useEffect, useCallback } from 'react';
import { ChevronLeft, CheckCircle2, Circle, Clock, Download, Play, Loader2, Pause, Square } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3002';

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

interface ResultsScreenProps {
  onBack: () => void;
  combinations?: Combination[];
  projectId?: number;
  defaultQuality?: 'low' | 'medium' | 'high' | 'ultra';
}

export default function ResultsScreen({ 
  onBack, 
  combinations: initialCombinations, 
  projectId,
  defaultQuality = 'medium' 
}: ResultsScreenProps) {
  const [results, setResults] = useState<ResultItem[]>([]);
  const [activeFilter, setActiveFilter] = useState(FILTERS[0]);
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set());
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [previewProgress, setPreviewProgress] = useState({ completed: 0, total: 0 });

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

  // Poll for preview status updates
  useEffect(() => {
    if (!projectId) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/previews/status`);
        const data = await response.json();
        
        if (data.statuses) {
          setResults(prev => prev.map(item => {
            const status = data.statuses.find((s: any) => s.combo_id === item.id);
            if (status) {
              return {
                ...item,
                preview_status: status.status,
                preview_url: status.preview_url
              };
            }
            return item;
          }));
          
          setPreviewProgress({
            completed: data.completed,
            total: data.total
          });
        }
      } catch (error) {
        console.error('Failed to fetch preview status:', error);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [projectId]);

  const selectedCount = results.filter(r => r.selected).length;
  const allSelected = selectedCount === results.length && results.length > 0;

  const toggleSelectAll = () => {
    setResults(results.map(r => ({ ...r, selected: !allSelected })));
  };

  const toggleSelect = (id: string) => {
    setResults(results.map(r => r.id === id ? { ...r, selected: !r.selected } : r));
  };

  const handlePlay = useCallback((item: ResultItem) => {
    if (item.preview_status === 'completed' && item.preview_url) {
      setPlayingId(playingId === item.id ? null : item.id);
    }
  }, [playingId]);

  const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloadingIds(prev => new Set(prev).add(item.id));
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/combinations/${item.id}/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality: defaultQuality })
      });

      if (!response.ok) throw new Error('下载失败');

      const data = await response.json();
      const taskId = data.task_id;

      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/status`);
        const statusData = await statusResponse.json();

        if (statusData.status === 'completed') {
          clearInterval(pollInterval);
          setDownloadingIds(prev => {
            const newSet = new Set(prev);
            newSet.delete(item.id);
            return newSet;
          });
          
          const downloadUrl = `${API_BASE_URL}${statusData.video_url}`;
          const link = document.createElement('a');
          link.href = downloadUrl;
          link.download = `mixcut_${item.id}.mp4`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } else if (statusData.status === 'failed') {
          clearInterval(pollInterval);
          setDownloadingIds(prev => {
            const newSet = new Set(prev);
            newSet.delete(item.id);
            return newSet;
          });
          alert('视频生成失败：' + (statusData.error || '未知错误'));
        }
      }, 1000);

    } catch (error) {
      console.error('下载失败:', error);
      setDownloadingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(item.id);
        return newSet;
      });
      alert('下载失败，请重试');
    }
  }, [defaultQuality]);

  const handleBatchDownload = useCallback(async () => {
    const selectedItems = results.filter(r => r.selected);
    if (selectedItems.length === 0) return;
    
    for (const item of selectedItems) {
      await handleDownload(item, { stopPropagation: () => {} } as React.MouseEvent);
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }, [results, handleDownload]);

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

  const getStatusDisplay = (status: string) => {
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
        <div className="text-xs text-gray-500 flex items-center gap-2">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
            预览生成中 {previewProgress.completed}/{previewProgress.total}
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
              const statusDisplay = getStatusDisplay(item.preview_status);
              const isPlaying = playingId === item.id;
              
              return (
                <div 
                  key={item.id} 
                  className={`relative bg-black rounded-lg overflow-hidden ${
                    item.selected ? 'ring-2 ring-blue-500' : ''
                  }`}
                >
                  <div className="relative w-full" style={{ paddingBottom: '177.78%' }}>
                    {isPlaying && item.preview_url ? (
                      // Playing state - show video
                      <div className="absolute inset-0 bg-black">
                        <video
                          src={`${API_BASE_URL}${item.preview_url}`}
                          className="w-full h-full object-contain"
                          controls
                          autoPlay
                          playsInline
                        />
                        <button
                          onClick={() => setPlayingId(null)}
                          className="absolute top-1 right-1 w-6 h-6 bg-black/50 rounded-full flex items-center justify-center text-white"
                        >
                          <Square size={12} fill="currentColor" />
                        </button>
                      </div>
                    ) : (
                      // Thumbnail state
                      <div className="absolute inset-0 bg-black">
                        <img 
                          src={`${API_BASE_URL}${item.thumbnail}`} 
                          alt="cover"
                          className="w-full h-full object-cover"
                        />
                        
                        {/* Status Overlay */}
                        {item.preview_status !== 'completed' && (
                          <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center text-white">
                            {item.preview_status === 'processing' ? (
                              <Loader2 size={24} className="animate-spin mb-1" />
                            ) : (
                              <Clock size={24} className="mb-1 opacity-50" />
                            )}
                            <span className={`text-[10px] ${statusDisplay.color}`}>
                              {statusDisplay.text}
                            </span>
                          </div>
                        )}
                        
                        {/* Play Button - only for completed previews */}
                        {item.preview_status === 'completed' && !downloadingIds.has(item.id) && (
                          <button
                            onClick={() => handlePlay(item)}
                            className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/50 transition-colors"
                          >
                            <div className="w-10 h-10 bg-white/90 rounded-full flex items-center justify-center">
                              <Play size={18} className="text-blue-600 ml-0.5" fill="currentColor" />
                            </div>
                          </button>
                        )}
                        
                        {/* Downloading Overlay */}
                        {downloadingIds.has(item.id) && (
                          <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center text-white">
                            <Loader2 size={20} className="animate-spin mb-1" />
                            <span className="text-[10px]">生成中...</span>
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
                          disabled={downloadingIds.has(item.id)}
                          className="absolute bottom-1 left-1 w-6 h-6 bg-blue-600 rounded-full flex items-center justify-center text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
                        >
                          <Download size={12} />
                        </button>
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
      )}
    </div>
  );
}
