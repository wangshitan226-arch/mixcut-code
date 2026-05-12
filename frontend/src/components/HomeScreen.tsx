import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronLeft, Scissors, FileText, ChevronRight, Play, Trash, CheckSquare } from 'lucide-react';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

interface HomeScreenProps {
  onNavigate: () => void;
  userId?: string;
}

interface Draft {
  id: string;
  title: string;
  render_id: string;
  original_video_url: string;
  output_video_url: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  thumbnail?: string;
  duration?: string;
}

// 全局缩略图缓存
const thumbnailCache = new Map<string, string>();

// 生成视频缩略图 - 使用更高的分辨率和正确的比例
const generateVideoThumbnail = (videoUrl: string): Promise<string> => {
  return new Promise((resolve, reject) => {
    // 检查缓存
    if (thumbnailCache.has(videoUrl)) {
      resolve(thumbnailCache.get(videoUrl)!);
      return;
    }

    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.preload = 'metadata';
    
    video.onloadedmetadata = () => {
      // 跳到第1秒或视频中间位置
      const seekTime = Math.min(1, video.duration / 2);
      video.currentTime = seekTime;
    };
    
    video.onseeked = () => {
      const canvas = document.createElement('canvas');
      // 使用更高的分辨率生成缩略图
      const aspectRatio = video.videoWidth / video.videoHeight;
      canvas.width = 400;
      canvas.height = Math.round(400 / aspectRatio);
      
      const ctx = canvas.getContext('2d');
      if (ctx) {
        // 使用更好的图像质量
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
        thumbnailCache.set(videoUrl, dataUrl);
        resolve(dataUrl);
      } else {
        reject(new Error('无法获取canvas上下文'));
      }
    };
    
    video.onerror = () => reject(new Error('视频加载失败'));
    
    video.src = videoUrl;
  });
};

// 草稿缩略图组件 - 使用9:16竖屏比例
interface DraftThumbnailProps {
  draft: Draft;
  onClick: () => void;
  index: number;
}

function DraftThumbnail({ draft, onClick, index }: DraftThumbnailProps) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    
    const loadThumbnail = async () => {
      try {
        const url = await generateVideoThumbnail(draft.original_video_url);
        if (isMounted) {
          setThumbnailUrl(url);
          setIsLoading(false);
        }
      } catch (err) {
        console.error('生成缩略图失败:', err);
        if (isMounted) setIsLoading(false);
      }
    };

    loadThumbnail();
    return () => { isMounted = false; };
  }, [draft.original_video_url]);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div 
      onClick={onClick}
      className="flex-shrink-0 w-[108px] cursor-pointer group"
    >
      {/* 缩略图容器 - 9:16 竖屏比例 */}
      <div className="relative w-[108px] h-[192px] rounded-xl overflow-hidden bg-gray-900 shadow-sm group-hover:shadow-lg transition-all duration-200">
        {thumbnailUrl ? (
          <img 
            src={thumbnailUrl}
            alt={draft.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-b from-gray-800 to-gray-900">
            {isLoading ? (
              <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <Play size={28} className="text-blue-400" />
            )}
          </div>
        )}
        
        {/* 状态标签 */}
        {draft.status !== 'completed' && (
          <div className="absolute top-2 left-2">
            <span className={`text-[10px] px-2 py-1 rounded-full font-medium shadow-sm ${
              draft.status === 'processing' ? 'bg-blue-500 text-white' :
              draft.status === 'transcribing' ? 'bg-amber-500 text-white' :
              draft.status === 'failed' ? 'bg-red-500 text-white' :
              'bg-gray-600 text-white'
            }`}>
              {draft.status === 'processing' ? '处理中' :
               draft.status === 'transcribing' ? '识别中' :
               draft.status === 'failed' ? '失败' : '草稿'}
            </span>
          </div>
        )}
        
        {/* 时长标签 */}
        {draft.duration && (
          <div className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded font-medium">
            {formatDuration(parseFloat(draft.duration))}
          </div>
        )}
        
        {/* 悬停效果 */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-200" />
      </div>
      
      {/* 标题 */}
      <p className="mt-2 text-xs text-gray-800 truncate font-medium px-0.5">
        {draft.title || draft.id.slice(0, 8)}
      </p>
    </div>
  );
}

// 全部草稿弹窗组件
interface AllDraftsModalProps {
  drafts: Draft[];
  isOpen: boolean;
  onClose: () => void;
  onOpenDraft: (draft: Draft) => void;
  onDeleteDrafts: (draftIds: string[]) => void;
}

function AllDraftsModal({ 
  drafts, 
  isOpen, 
  onClose, 
  onOpenDraft, 
  onDeleteDrafts
}: AllDraftsModalProps) {
  const [isManaging, setIsManaging] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  if (!isOpen) return null;

  const toggleSelection = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const selectAll = () => {
    if (selectedIds.size === drafts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(drafts.map(d => d.id)));
    }
  };

  const handleDeleteSelected = () => {
    if (selectedIds.size === 0) return;
    if (confirm(`确定要删除选中的 ${selectedIds.size} 个草稿吗？`)) {
      onDeleteDrafts(Array.from(selectedIds));
      setSelectedIds(new Set());
      setIsManaging(false);
    }
  };

  const handleClose = () => {
    setIsManaging(false);
    setSelectedIds(new Set());
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col">
      {/* 遮罩层 */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />
      
      {/* 内容区域 - 从下到上滑出 */}
      <div className="absolute bottom-0 left-0 right-0 bg-gray-50 rounded-t-3xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-3">
            <button 
              onClick={handleClose}
              className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
            >
              <ChevronLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-lg font-semibold text-gray-900">全部草稿</h2>
            <span className="text-sm text-gray-400">({drafts.length})</span>
          </div>
          
          {isManaging ? (
            <div className="flex items-center gap-2">
              <button
                onClick={selectAll}
                className="text-sm text-blue-600 font-medium px-3 py-2 hover:bg-blue-50 rounded-lg transition-colors"
              >
                {selectedIds.size === drafts.length ? '取消全选' : '全选'}
              </button>
              <button
                onClick={() => setIsManaging(false)}
                className="text-sm text-gray-500 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                完成
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsManaging(true)}
              className="flex items-center gap-1.5 text-sm text-blue-600 font-medium px-4 py-2 hover:bg-blue-50 rounded-lg transition-colors"
            >
              <Trash size={16} />
              管理
            </button>
          )}
        </div>
        
        {/* 草稿网格 */}
        <div className="flex-1 overflow-y-auto p-4">
          {drafts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <FileText size={56} className="mb-4 opacity-30" />
              <p className="text-base">暂无草稿</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              {drafts.map((draft, index) => (
                <DraftGridItem 
                  key={draft.id}
                  draft={draft}
                  index={index}
                  isManaging={isManaging}
                  isSelected={selectedIds.has(draft.id)}
                  onClick={() => {
                    if (isManaging) {
                      toggleSelection(draft.id);
                    } else {
                      onOpenDraft(draft);
                    }
                  }}
                />
              ))}
            </div>
          )}
        </div>
        
        {/* 底部删除栏 */}
        {isManaging && selectedIds.size > 0 && (
          <div className="border-t border-gray-200 px-4 pt-4 pb-20 bg-white">
            <button
              onClick={handleDeleteSelected}
              className="w-full bg-red-500 text-white py-3.5 rounded-xl font-semibold text-base active:scale-[0.98] transition-transform shadow-lg shadow-red-200"
            >
              删除选中 ({selectedIds.size})
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// 网格项组件 - 同样使用9:16比例
interface DraftGridItemProps {
  draft: Draft;
  index: number;
  isManaging: boolean;
  isSelected: boolean;
  onClick: () => void;
}

function DraftGridItem({ draft, index, isManaging, isSelected, onClick }: DraftGridItemProps) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    
    const loadThumbnail = async () => {
      try {
        const url = await generateVideoThumbnail(draft.original_video_url);
        if (isMounted) setThumbnailUrl(url);
      } catch (err) {
        console.error('生成缩略图失败:', err);
      }
    };

    loadThumbnail();
    return () => { isMounted = false; };
  }, [draft.original_video_url]);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div 
      onClick={onClick}
      className="relative cursor-pointer group"
    >
      {/* 缩略图 - 9:16 竖屏比例 */}
      <div className="relative aspect-[9/16] rounded-xl overflow-hidden bg-gray-900 shadow-sm">
        {thumbnailUrl ? (
          <img 
            src={thumbnailUrl}
            alt={draft.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-b from-gray-800 to-gray-900">
            <Play size={24} className="text-blue-400" />
          </div>
        )}
        
        {/* 选中状态遮罩 */}
        {isManaging && isSelected && (
          <div className="absolute inset-0 bg-blue-500/40 flex items-center justify-center">
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center shadow-lg">
              <CheckSquare size={20} className="text-white" />
            </div>
          </div>
        )}
        
        {/* 管理模式下未选中的遮罩 */}
        {isManaging && !isSelected && (
          <div className="absolute inset-0 bg-black/30" />
        )}
        
        {/* 状态标签 */}
        {draft.status !== 'completed' && (
          <div className="absolute top-2 left-2">
            <span className={`text-[10px] px-2 py-1 rounded-full font-medium shadow-sm ${
              draft.status === 'processing' ? 'bg-blue-500 text-white' :
              draft.status === 'transcribing' ? 'bg-amber-500 text-white' :
              draft.status === 'failed' ? 'bg-red-500 text-white' :
              'bg-gray-600 text-white'
            }`}>
              {draft.status === 'processing' ? '处理中' :
               draft.status === 'transcribing' ? '识别中' :
               draft.status === 'failed' ? '失败' : '草稿'}
            </span>
          </div>
        )}
        
        {/* 时长 */}
        {draft.duration && (
          <div className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded font-medium">
            {formatDuration(parseFloat(draft.duration))}
          </div>
        )}
      </div>
      
      {/* 标题 */}
      <p className="mt-2 text-sm text-gray-800 truncate font-medium">
        {draft.title || draft.id.slice(0, 8)}
      </p>
      
      {/* 时间 */}
      <p className="text-xs text-gray-400 mt-0.5">
        {new Date(draft.updated_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}
      </p>
    </div>
  );
}

export default function HomeScreen({ onNavigate, userId }: HomeScreenProps) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAllDrafts, setShowAllDrafts] = useState(false);

  // 加载草稿列表
  useEffect(() => {
    const loadDrafts = async () => {
      if (!userId) return;
      
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/users/${userId}/kaipai/drafts`);
        if (response.ok) {
          const data = await response.json();
          setDrafts(data.drafts || []);
        }
      } catch (err) {
        console.error('加载草稿失败:', err);
      } finally {
        setLoading(false);
      }
    };

    loadDrafts();
  }, [userId]);

  // 删除草稿（支持批量）
  const deleteDrafts = useCallback(async (draftIds: string[]) => {
    const deletePromises = draftIds.map(async (draftId) => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kaipai/${draftId}`, {
          method: 'DELETE'
        });
        return { draftId, success: response.ok };
      } catch (err) {
        console.error('删除草稿失败:', draftId, err);
        return { draftId, success: false };
      }
    });

    const results = await Promise.all(deletePromises);
    const successCount = results.filter(r => r.success).length;
    
    // 更新本地状态
    setDrafts(prev => prev.filter(d => !draftIds.includes(d.id)));
    
    if (successCount < draftIds.length) {
      alert(`成功删除 ${successCount}/${draftIds.length} 个草稿`);
    }
  }, []);

  // 打开草稿编辑
  const openDraft = useCallback((draft: Draft) => {
    window.dispatchEvent(new CustomEvent('openKaipaiEditor', { 
      detail: { editId: draft.id, videoUrl: draft.original_video_url }
    }));
  }, []);

  // 获取前6个草稿
  const displayDrafts = drafts.slice(0, 6);
  const hasMore = drafts.length > 6;

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-center h-14 shrink-0 bg-white border-b border-gray-100">
        <h1 className="text-lg font-bold text-gray-900">FengMa-AI</h1>
      </header>
      
      <div className="flex-1 overflow-y-auto">
        {/* 创作工具 */}
        <div className="p-4">
          <h2 className="text-sm font-semibold text-gray-800 mb-3 px-1">创作工具</h2>
          
          {/* 智能混剪 Card */}
          <div 
            onClick={onNavigate}
            className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl p-5 shadow-lg shadow-blue-200 text-white flex items-center justify-between active:scale-[0.98] transition-transform cursor-pointer mb-6"
          >
            <div className="flex items-center gap-4">
              <div className="bg-white/20 p-3 rounded-xl backdrop-blur-sm">
                <Scissors size={28} className="text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold tracking-wide">智能混剪</h3>
                <p className="text-blue-100 text-xs mt-1">批量生成不重复的高质量视频</p>
              </div>
            </div>
            <ChevronLeft size={24} className="rotate-180 text-white/80" />
          </div>
        </div>

        {/* 草稿箱 - 缩略图展示 */}
        {drafts.length > 0 && (
          <div className="mb-6">
            {/* 标题栏 */}
            <div className="flex items-center justify-between px-4 mb-3">
              <h2 className="text-sm font-semibold text-gray-800">文字快剪草稿</h2>
              <button 
                onClick={() => setShowAllDrafts(true)}
                className="flex items-center gap-0.5 text-sm text-blue-600 font-medium hover:text-blue-700 transition-colors"
              >
                全部
                <ChevronRight size={16} />
              </button>
            </div>

            {/* 横向滚动缩略图列表 */}
            <div 
              className="flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-hide"
              style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
            >
              {displayDrafts.map((draft, index) => (
                <DraftThumbnail 
                  key={draft.id}
                  draft={draft}
                  index={index}
                  onClick={() => openDraft(draft)}
                />
              ))}
              
              {/* 查看更多按钮 */}
              {hasMore && (
                <div 
                  onClick={() => setShowAllDrafts(true)}
                  className="flex-shrink-0 w-[108px] h-[192px] rounded-xl bg-gradient-to-b from-blue-50 to-blue-100 flex flex-col items-center justify-center cursor-pointer hover:from-blue-100 hover:to-blue-200 transition-all border border-blue-200"
                >
                  <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center mb-2">
                    <ChevronRight size={24} className="text-blue-600" />
                  </div>
                  <span className="text-sm text-blue-600 font-medium">查看更多</span>
                  <span className="text-xs text-blue-400 mt-1">{drafts.length}个草稿</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 空状态 */}
        {drafts.length === 0 && !loading && (
          <div className="px-4">
            <div className="flex items-center justify-between mb-3 px-1">
              <h2 className="text-sm font-semibold text-gray-800">文字快剪草稿</h2>
            </div>
            <div className="bg-white rounded-2xl p-8 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <FileText size={28} className="text-gray-400" />
              </div>
              <p className="text-gray-500 text-sm">暂无草稿</p>
              <p className="text-gray-400 text-xs mt-1">在智能混剪中生成视频后，可以进行文字快剪</p>
            </div>
          </div>
        )}

        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* 全部草稿弹窗 */}
      <AllDraftsModal
        drafts={drafts}
        isOpen={showAllDrafts}
        onClose={() => setShowAllDrafts(false)}
        onOpenDraft={openDraft}
        onDeleteDrafts={deleteDrafts}
      />
    </div>
  );
}
