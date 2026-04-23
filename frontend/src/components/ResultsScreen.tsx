import React, { useState, useEffect, useCallback } from 'react';
import { ChevronLeft, CheckCircle2, Circle, Clock, Download, Play, Loader2, Pause, Square, Scissors } from 'lucide-react';
import KaipaiEditor from './KaipaiEditor';

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
  defaultQuality?: 'low' | 'medium' | 'high' | 'ultra';
}

export default function ResultsScreen({ 
  onBack, 
  combinations: initialCombinations,
  defaultQuality = 'medium' 
}: ResultsScreenProps) {
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



  const selectedCount = results.filter(r => r.selected).length;
  const allSelected = selectedCount === results.length && results.length > 0;

  const toggleSelectAll = () => {
    setResults(results.map(r => ({ ...r, selected: !allSelected })));
  };

  const toggleSelect = (id: string) => {
    setResults(results.map(r => r.id === id ? { ...r, selected: !r.selected } : r));
  };

  // Trigger fast concat for a combination
  const triggerConcat = async (item: ResultItem) => {
    try {
      // Update status to processing
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
        // Already exists, update and play
        setResults(prev => prev.map(r => 
          r.id === item.id ? { ...r, preview_status: 'completed', preview_url: data.video_url } : r
        ));
        return data.video_url;
      } else if (data.status === 'processing') {
        // Wait for completion
        const taskId = data.task_id;
        return await waitForConcat(taskId, item.id);
      }
    } catch (error) {
      console.error('拼接失败:', error);
      setResults(prev => prev.map(r => 
        r.id === item.id ? { ...r, preview_status: 'failed' } : r
      ));
      return null;
    }
  };
  
  // Poll for concat completion
  const waitForConcat = async (taskId: string, itemId: string): Promise<string | null> => {
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
          // Continue polling if processing
        } catch (error) {
          console.error('查询拼接状态失败:', error);
        }
      }, 500); // Check every 500ms
      
      // Timeout after 30 seconds
      setTimeout(() => {
        clearInterval(checkInterval);
        resolve(null);
      }, 30000);
    });
  };

  const handlePlay = useCallback(async (item: ResultItem) => {
    // If already playing, stop
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
      // Set a temporary loading state for this item
      setResults(prev => prev.map(r => 
        r.id === item.id ? { ...r, preview_status: 'loading' } : r
      ));
      setPlayingId(item.id);
      
      // Trigger concat in background
      triggerConcat(item).then(videoUrl => {
        if (videoUrl) {
          // Video ready, update status (player will auto-load)
          setResults(prev => prev.map(r => 
            r.id === item.id ? { ...r, preview_status: 'completed', preview_url: videoUrl } : r
          ));
        } else {
          // Failed, show error
          setResults(prev => prev.map(r => 
            r.id === item.id ? { ...r, preview_status: 'failed' } : r
          ));
          setPlayingId(null);
        }
      });
    }
  }, [playingId]);

  // Check if device is mobile
  const isMobile = () => {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  };

  // Check if Web Share API is supported
  const canUseWebShare = () => {
    return navigator.share && navigator.canShare;
  };

  // Download video using Web Share API (mobile) or Blob (desktop)
  const downloadVideo = async (videoUrl: string, filename: string) => {
    try {
      setDownloadingIds(prev => new Set(prev).add(filename));
      
      const response = await fetch(videoUrl);
      if (!response.ok) throw new Error('获取视频失败');
      
      const blob = await response.blob();
      const file = new File([blob], filename, { type: 'video/mp4' });
      
      // Try Web Share API on mobile (allows saving to gallery)
      if (isMobile() && canUseWebShare() && navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({
            files: [file],
            title: 'MixCut 视频',
            text: '下载的视频'
          });
          // Share successful
          return;
        } catch (shareError) {
          // User cancelled share or failed, fallback to blob download
          console.log('Web Share failed, using fallback:', shareError);
        }
      }
      
      // Fallback: Blob download (desktop or Web Share not supported)
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
      
    } catch (error) {
      console.error('下载失败:', error);
      alert('下载失败：' + (error instanceof Error ? error.message : '请重试'));
    } finally {
      setDownloadingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(filename);
        return newSet;
      });
    }
  };

  // Production mode: direct download via backend (suitable for large files, OSS/CDN)
  const directDownloadVideo = (downloadUrl: string) => {
    // Use iframe for download to avoid opening new tab
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = downloadUrl;
    document.body.appendChild(iframe);
    
    // Remove iframe after download starts
    setTimeout(() => {
      document.body.removeChild(iframe);
    }, 5000);
  };

  const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
    e.stopPropagation();
    
    let videoUrl = item.preview_url;
    
    // If video not ready, trigger concat first
    if (item.preview_status !== 'completed' || !videoUrl) {
      videoUrl = await triggerConcat(item);
      if (!videoUrl) {
        alert('视频拼接失败，请重试');
        return;
      }
    }
    
    // Now download the video
    try {
      const fullUrl = videoUrl.startsWith('http') ? videoUrl : `${API_BASE_URL}${videoUrl}`;
      await downloadVideo(fullUrl, `mixcut_${item.id}.mp4`);
    } catch (error) {
      console.error('下载失败:', error);
      alert('下载失败：' + (error instanceof Error ? error.message : '请重试'));
    }
  }, [defaultQuality]);

  const handleBatchDownload = useCallback(async () => {
    const selectedItems = results.filter(r => r.selected);
    if (selectedItems.length === 0) {
      alert('请先选择要下载的视频');
      return;
    }
    
    // Process all selected items
    for (const item of selectedItems) {
      try {
        let videoUrl = item.preview_url;
        
        // Ensure video is ready
        if (item.preview_status !== 'completed' || !videoUrl) {
          videoUrl = await triggerConcat(item);
        }
        
        // Download
        if (videoUrl) {
          const fullUrl = videoUrl.startsWith('http') ? videoUrl : `${API_BASE_URL}${videoUrl}`;
          await downloadVideo(fullUrl, `mixcut_${item.id}.mp4`);
        }
        
        // Small delay between downloads
        await new Promise(resolve => setTimeout(resolve, 1000));
      } catch (error) {
        console.error('批量下载失败:', error);
      }
    }
  }, [results]);

  // 打开网感剪辑（使用选中的视频）
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
    
    // 确保视频已合成
    let videoUrl = item.preview_url;
    if (item.preview_status !== 'completed' || !videoUrl) {
      setKaipaiLoadingId(item.id);
      videoUrl = await triggerConcat(item);
      setKaipaiLoadingId(null);
      if (!videoUrl) {
        alert('视频合成失败，请重试');
        return;
      }
    }
    
    try {
      // 创建 KaipaiEdit 任务
      const response = await fetch(`${API_BASE_URL}/api/renders/${item.id}/kaipai/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '创建剪辑任务失败');
      }
      
      const data = await response.json();
      console.log('Kaipai edit created:', data);
      setKaipaiEditId(data.edit_id);
      setKaipaiVideoUrl(data.video_url);
      setShowKaipaiEditor(true);
    } catch (error: any) {
      alert('创建剪辑任务失败：' + error.message);
    }
  }, [results]);

  // 关闭网感剪辑
  const handleCloseKaipai = () => {
    setShowKaipaiEditor(false);
    setKaipaiEditId('');
    setKaipaiVideoUrl('');
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
                    {isPlaying ? (
                      // Playing state - show video player
                      <div className="absolute inset-0 bg-black">
                        {item.preview_url ? (
                          // Video ready - play it
                          <video
                            src={item.preview_url.startsWith('http') ? item.preview_url : `${API_BASE_URL}${item.preview_url}`}
                            className="w-full h-full object-contain"
                            controls
                            autoPlay
                            playsInline
                          />
                        ) : (
                          // Video loading - show spinner
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
                      // Thumbnail state
                      <div className="absolute inset-0 bg-black">
                        <img 
                          src={`${API_BASE_URL}${item.thumbnail}`} 
                          alt="cover"
                          className="w-full h-full object-cover"
                        />
                        
                        {/* Play Button - always show */}
                        <button
                          onClick={() => handlePlay(item)}
                          className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/50 transition-colors"
                        >
                          <div className="w-10 h-10 bg-white/90 rounded-full flex items-center justify-center">
                            <Play size={18} className="text-blue-600 ml-0.5" fill="currentColor" />
                          </div>
                        </button>
                        
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
          <div className="flex items-center gap-2">
            {/* 文字快剪按钮 - 只选中一个视频时可用 */}
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
