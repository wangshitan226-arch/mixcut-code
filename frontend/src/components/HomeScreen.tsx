import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  ChevronLeft, Scissors, FileText, ChevronRight, Play, Trash, 
  CheckSquare, Sparkles, User, Video, Newspaper, Zap, 
  Mic, Image, TrendingUp, MessageCircle, Loader2, AlertCircle, 
  Volume2, CheckCircle2, Plus
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface HomeScreenProps {
  onNavigate: () => void;
  onSelectVideoType: () => void;
  onOpenDigitalHuman: () => void;
  onOpenAICopy: () => void;
  onOpenAudioRecord: () => void;
  onOpenCoverGenerator: (editId: string, videoUrl: string, originalVideoUrl: string, videoText: string, extractedTitle: string) => void;
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

interface DigitalHumanItem {
  id: string;
  title: string;
  avatar_id?: string;
  video_url?: string;
  cover_url?: string;
  voice_id?: string;
  voice_name?: string;
  status: string;
  videoretalk_status?: string;
  videoretalk_task_id?: string;
  generated_video_url?: string;
  generated_video_duration?: number;
  created_at: string;
  updated_at: string;
}

interface VoiceCloneItem {
  id: string;
  title: string;
  audio_url?: string;
  clone_voice_id?: string;
  clone_task_id?: string;
  preview_url?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const thumbnailCache = new Map<string, string>();

const generateVideoThumbnail = (videoUrl: string): Promise<string> => {
  return new Promise((resolve, reject) => {
    if (thumbnailCache.has(videoUrl)) {
      resolve(thumbnailCache.get(videoUrl)!);
      return;
    }
    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.preload = 'metadata';
    video.onloadedmetadata = () => {
      const seekTime = Math.min(1, video.duration / 2);
      video.currentTime = seekTime;
    };
    video.onseeked = () => {
      const canvas = document.createElement('canvas');
      const aspectRatio = video.videoWidth / video.videoHeight;
      canvas.width = 400;
      canvas.height = Math.round(400 / aspectRatio);
      const ctx = canvas.getContext('2d');
      if (ctx) {
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
        if (isMounted) { setThumbnailUrl(url); setIsLoading(false); }
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
    <div onClick={onClick} className="flex-shrink-0 w-[108px] cursor-pointer group">
      <div className="relative w-[108px] h-[192px] rounded-xl overflow-hidden bg-gray-900 shadow-sm group-hover:shadow-lg transition-all duration-200">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={draft.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-b from-gray-800 to-gray-900">
            {isLoading ? (
              <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <Play size={28} className="text-blue-400" />
            )}
          </div>
        )}
        {draft.status !== 'completed' && (
          <div className="absolute top-2 left-2">
            <span className={`text-[10px] px-2 py-1 rounded-full font-medium shadow-sm ${
              draft.status === 'processing' ? 'bg-blue-500 text-white' :
              draft.status === 'transcribing' ? 'bg-amber-500 text-white' :
              draft.status === 'failed' ? 'bg-red-500 text-white' : 'bg-gray-600 text-white'
            }`}>
              {draft.status === 'processing' ? '处理中' :
               draft.status === 'transcribing' ? '识别中' :
               draft.status === 'failed' ? '失败' : '草稿'}
            </span>
          </div>
        )}
        {draft.duration && (
          <div className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded font-medium">
            {formatDuration(parseFloat(draft.duration))}
          </div>
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-200" />
      </div>
      <p className="mt-2 text-xs text-gray-800 truncate font-medium px-0.5">
        {draft.title || draft.id.slice(0, 8)}
      </p>
    </div>
  );
}

interface AllDraftsModalProps {
  drafts: Draft[];
  isOpen: boolean;
  onClose: () => void;
  onOpenDraft: (draft: Draft) => void;
  onDeleteDrafts: (draftIds: string[]) => void;
}

function AllDraftsModal({ drafts, isOpen, onClose, onOpenDraft, onDeleteDrafts }: AllDraftsModalProps) {
  const [isManaging, setIsManaging] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  if (!isOpen) return null;

  const toggleSelection = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) newSelected.delete(id); else newSelected.add(id);
    setSelectedIds(newSelected);
  };

  const selectAll = () => {
    if (selectedIds.size === drafts.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(drafts.map(d => d.id)));
  };

  const handleDeleteSelected = () => {
    if (selectedIds.size === 0) return;
    if (confirm(`确定要删除选中的 ${selectedIds.size} 个草稿吗？`)) {
      onDeleteDrafts(Array.from(selectedIds));
      setSelectedIds(new Set());
      setIsManaging(false);
    }
  };

  const handleClose = () => { setIsManaging(false); setSelectedIds(new Set()); onClose(); };

  return (
    <div className="fixed inset-0 z-50 flex flex-col">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />
      <div className="absolute bottom-0 left-0 right-0 bg-gray-50 rounded-t-3xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-3">
            <button onClick={handleClose} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ChevronLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-lg font-semibold text-gray-900">全部草稿</h2>
            <span className="text-sm text-gray-400">({drafts.length})</span>
          </div>
          {isManaging ? (
            <div className="flex items-center gap-2">
              <button onClick={selectAll} className="text-sm text-blue-600 font-medium px-3 py-2 hover:bg-blue-50 rounded-lg transition-colors">
                {selectedIds.size === drafts.length ? '取消全选' : '全选'}
              </button>
              <button onClick={() => setIsManaging(false)} className="text-sm text-gray-500 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors">完成</button>
            </div>
          ) : (
            <button onClick={() => setIsManaging(true)} className="flex items-center gap-1.5 text-sm text-blue-600 font-medium px-4 py-2 hover:bg-blue-50 rounded-lg transition-colors">
              <Trash size={16} />管理
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {drafts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <FileText size={56} className="mb-4 opacity-30" />
              <p className="text-base">暂无草稿</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              {drafts.map((draft, index) => (
                <DraftGridItem key={draft.id} draft={draft} index={index} isManaging={isManaging} isSelected={selectedIds.has(draft.id)}
                  onClick={() => { if (isManaging) toggleSelection(draft.id); else onOpenDraft(draft); }}
                />
              ))}
            </div>
          )}
        </div>
        {isManaging && selectedIds.size > 0 && (
          <div className="border-t border-gray-200 px-4 pt-4 pb-20 bg-white">
            <button onClick={handleDeleteSelected} className="w-full bg-red-500 text-white py-3.5 rounded-xl font-semibold text-base active:scale-[0.98] transition-transform shadow-lg shadow-red-200">
              删除选中 ({selectedIds.size})
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

interface DraftThumbnailImageProps {
  videoUrl: string;
}

function DraftThumbnailImage({ videoUrl }: DraftThumbnailImageProps) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    const loadThumbnail = async () => {
      try { const url = await generateVideoThumbnail(videoUrl); if (isMounted) setThumbnailUrl(url); }
      catch (err) { console.error('生成缩略图失败:', err); }
    };
    loadThumbnail();
    return () => { isMounted = false; };
  }, [videoUrl]);

  if (thumbnailUrl) {
    return <img src={thumbnailUrl} alt="缩略图" className="w-full h-full object-cover" />;
  }
  return (
    <div className="w-full h-full flex items-center justify-center bg-gradient-to-b from-gray-800 to-gray-900">
      <Play size={16} className="text-blue-400" />
    </div>
  );
}

interface DraftGridItemProps {
  draft: Draft; index: number; isManaging: boolean; isSelected: boolean; onClick: () => void;
}

function DraftGridItem({ draft, index, isManaging, isSelected, onClick }: DraftGridItemProps) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string>('');

  useEffect(() => {
    let isMounted = true;
    const loadThumbnail = async () => {
      try { const url = await generateVideoThumbnail(draft.original_video_url); if (isMounted) setThumbnailUrl(url); }
      catch (err) { console.error('生成缩略图失败:', err); }
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
    <div onClick={onClick} className="relative cursor-pointer group">
      <div className="relative aspect-[9/16] rounded-xl overflow-hidden bg-gray-900 shadow-sm">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={draft.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-b from-gray-800 to-gray-900">
            <Play size={24} className="text-blue-400" />
          </div>
        )}
        {isManaging && isSelected && (
          <div className="absolute inset-0 bg-blue-500/40 flex items-center justify-center">
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center shadow-lg"><CheckSquare size={20} className="text-white" /></div>
          </div>
        )}
        {isManaging && !isSelected && <div className="absolute inset-0 bg-black/30" />}
        {draft.status !== 'completed' && (
          <div className="absolute top-2 left-2">
            <span className={`text-[10px] px-2 py-1 rounded-full font-medium shadow-sm ${
              draft.status === 'processing' ? 'bg-blue-500 text-white' :
              draft.status === 'transcribing' ? 'bg-amber-500 text-white' :
              draft.status === 'failed' ? 'bg-red-500 text-white' : 'bg-gray-600 text-white'
            }`}>
              {draft.status === 'processing' ? '处理中' : draft.status === 'transcribing' ? '识别中' : draft.status === 'failed' ? '失败' : '草稿'}
            </span>
          </div>
        )}
        {draft.duration && (
          <div className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded font-medium">
            {formatDuration(parseFloat(draft.duration))}
          </div>
        )}
      </div>
      <p className="mt-2 text-sm text-gray-800 truncate font-medium">{draft.title || draft.id.slice(0, 8)}</p>
      <p className="text-xs text-gray-400 mt-0.5">{new Date(draft.updated_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}</p>
    </div>
  );
}

const QUICK_TOOLS = [
  { id: 'digital_human', name: 'AI数字人', icon: User, color: 'from-purple-500 to-indigo-500', desc: '创建和管理数字人' },
  { id: 'record_audio', name: '录制音频', icon: Mic, color: 'from-pink-500 to-rose-500', desc: '录制配音音频' },
  { id: 'ai_copy', name: 'AI文案', icon: Sparkles, color: 'from-amber-500 to-orange-500', desc: '智能生成视频文案' },
  { id: 'cover', name: '自动封面', icon: Image, color: 'from-cyan-500 to-blue-500', desc: '一键生成视频封面' },
];

export default function HomeScreen({ onNavigate, onSelectVideoType, onOpenDigitalHuman, onOpenAICopy, onOpenAudioRecord, onOpenCoverGenerator, userId }: HomeScreenProps) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAllDrafts, setShowAllDrafts] = useState(false);
  const [showCoverDraftPicker, setShowCoverDraftPicker] = useState(false);
  const [digitalHumans, setDigitalHumans] = useState<DigitalHumanItem[]>([]);
  const [voiceClones, setVoiceClones] = useState<VoiceCloneItem[]>([]);
  const [showAllDigitalHumans, setShowAllDigitalHumans] = useState(false);
  const [showAllVoiceClones, setShowAllVoiceClones] = useState(false);
  const [managingDH, setManagingDH] = useState(false);
  const [selectedDHIds, setSelectedDHIds] = useState<Set<string>>(new Set());
  const [managingVC, setManagingVC] = useState(false);
  const [selectedVCIds, setSelectedVCIds] = useState(new Set<string>());

  useEffect(() => {
    const loadDrafts = async () => {
      if (!userId) return;
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/users/${userId}/kaipai/drafts`);
        if (response.ok) { const data = await response.json(); setDrafts(data.drafts || []); }
      } catch (err) { console.error('加载草稿失败:', err); }
      finally { setLoading(false); }
    };
    loadDrafts();
  }, [userId]);

  useEffect(() => {
    const loadDigitalHumans = async () => {
      if (!userId) return;
      try {
        console.log('[Home] Loading digital humans for:', userId);
        const resp = await fetch(`${API_BASE_URL}/api/users/${userId}/digital-humans`);
        if (resp.ok) {
          const data = await resp.json();
          console.log('[Home] Digital humans loaded:', (data.digital_humans || []).length, 'items');
          setDigitalHumans(data.digital_humans || []);
        } else {
          console.error('[Home] Load digital humans error:', resp.status);
        }
      } catch (err) {
        console.error('[Home] Load digital humans error:', err);
      }
    };
    const loadVoiceClones = async () => {
      if (!userId) return;
      try {
        console.log('[Home] Loading voice clones for:', userId);
        const resp = await fetch(`${API_BASE_URL}/api/users/${userId}/voice-clones`);
        if (resp.ok) {
          const data = await resp.json();
          console.log('[Home] Voice clones loaded:', (data.voice_clones || []).length, 'items');
          setVoiceClones(data.voice_clones || []);
        } else {
          console.error('[Home] Load voice clones error:', resp.status);
        }
      } catch (err) {
        console.error('[Home] Load voice clones error:', err);
      }
    };
    loadDigitalHumans();
    loadVoiceClones();
  }, [userId]);

  const deleteDrafts = useCallback(async (draftIds: string[]) => {
    const deletePromises = draftIds.map(async (draftId) => {
      try { const response = await fetch(`${API_BASE_URL}/api/kaipai/${draftId}`, { method: 'DELETE' }); return { draftId, success: response.ok }; }
      catch (err) { console.error('删除草稿失败:', draftId, err); return { draftId, success: false }; }
    });
    const results = await Promise.all(deletePromises);
    const successCount = results.filter(r => r.success).length;
    setDrafts(prev => prev.filter(d => !draftIds.includes(d.id)));
    if (successCount < draftIds.length) alert(`成功删除 ${successCount}/${draftIds.length} 个草稿`);
  }, []);

  const openDraft = useCallback((draft: Draft) => {
    window.dispatchEvent(new CustomEvent('openKaipaiEditor', { detail: { editId: draft.id, videoUrl: draft.original_video_url } }));
  }, []);

  const handleQuickTool = (id: string) => {
    if (id === 'digital_human') { onOpenDigitalHuman(); return; }
    if (id === 'cover') { setShowCoverDraftPicker(true); return; }
    if (id === 'ai_copy') { onOpenAICopy(); return; }
    if (id === 'record_audio') { onOpenAudioRecord(); return; }
    alert(`${id} 功能开发中...`);
  };

  const handleSelectDraftForCover = async (draft: Draft) => {
    setShowCoverDraftPicker(false);
    try {
      const response = await fetch(`${API_BASE_URL}/api/kaipai/${draft.id}`);
      if (!response.ok) throw new Error('获取草稿详情失败');
      const data = await response.json();
      const asrResult = data.asr_result || {};
      const sentences = asrResult.sentences || [];
      const speechSentences = sentences.filter((s: any) => s.type === 'speech' && s.text);
      const videoText = speechSentences.map((s: any) => s.text).join('\n');
      const extractedTitle = asrResult.metadata?.title || '';
      const videoUrl = draft.output_video_url || draft.original_video_url;
      if (!videoText || videoText.trim().length < 5) {
        alert('该草稿没有足够的语音文案内容，无法生成封面。请先完成语音识别。');
        return;
      }
      onOpenCoverGenerator(draft.id, videoUrl, draft.original_video_url, videoText, extractedTitle);
    } catch (err: any) {
      alert('获取草稿信息失败: ' + err.message);
    }
  };

  const displayDrafts = drafts.slice(0, 6);
  const hasMore = drafts.length > 6;

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      <header className="flex items-center justify-center h-14 shrink-0 bg-white border-b border-gray-100">
        <h1 className="text-lg font-bold text-gray-900">FengMa-AI</h1>
      </header>
      
      <div className="flex-1 overflow-y-auto">
        <div className="p-4">
          <div 
            onClick={onSelectVideoType}
            className="bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-600 rounded-2xl p-5 shadow-lg shadow-indigo-200 text-white flex items-center justify-between active:scale-[0.98] transition-transform cursor-pointer mb-4"
          >
            <div className="flex items-center gap-4">
              <div className="bg-white/20 p-3 rounded-xl backdrop-blur-sm">
                <Sparkles size={28} className="text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold tracking-wide">创作4种视频</h3>
                <p className="text-indigo-100 text-xs mt-1">数字人 / 混剪 / 口播</p>
              </div>
            </div>
            <ChevronLeft size={24} className="rotate-180 text-white/80" />
          </div>

          <div className="grid grid-cols-4 gap-3 mb-6">
            {QUICK_TOOLS.map((tool) => (
              <button
                key={tool.id}
                onClick={() => handleQuickTool(tool.id)}
                className="flex flex-col items-center gap-1.5 py-3 active:scale-95 transition-transform"
              >
                <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${tool.color} flex items-center justify-center shadow-sm`}>
                  <tool.icon size={20} className="text-white" />
                </div>
                <span className="text-[11px] text-gray-700 font-medium">{tool.name}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="px-4 mb-4">
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-4 border border-blue-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                  <Scissors size={18} className="text-white" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-900">智能混剪</h3>
                  <p className="text-[11px] text-gray-500">批量生成不重复的高质量视频</p>
                </div>
              </div>
              <button
                onClick={onNavigate}
                className="px-3 py-1.5 bg-blue-500 text-white text-xs font-medium rounded-lg active:scale-95 transition-transform"
              >
                进入
              </button>
            </div>
          </div>
        </div>

        {drafts.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center justify-between px-4 mb-3">
              <h2 className="text-sm font-semibold text-gray-800">最近草稿</h2>
              <button onClick={() => setShowAllDrafts(true)} className="flex items-center gap-0.5 text-sm text-blue-600 font-medium hover:text-blue-700 transition-colors">
                全部 <ChevronRight size={16} />
              </button>
            </div>
            <div className="flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-hide" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
              {displayDrafts.map((draft, index) => (
                <DraftThumbnail key={draft.id} draft={draft} index={index} onClick={() => openDraft(draft)} />
              ))}
              {hasMore && (
                <div onClick={() => setShowAllDrafts(true)} className="flex-shrink-0 w-[108px] h-[192px] rounded-xl bg-gradient-to-b from-blue-50 to-blue-100 flex flex-col items-center justify-center cursor-pointer hover:from-blue-100 hover:to-blue-200 transition-all border border-blue-200">
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

        {drafts.length === 0 && !loading && (
          <div className="px-4">
            <div className="flex items-center justify-between mb-3 px-1">
              <h2 className="text-sm font-semibold text-gray-800">最近草稿</h2>
            </div>
            <div className="bg-white rounded-2xl p-8 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <FileText size={28} className="text-gray-400" />
              </div>
              <p className="text-gray-500 text-sm">暂无草稿</p>
              <p className="text-gray-400 text-xs mt-1">创作视频后，草稿会显示在这里</p>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        <div className="mb-6">
          <div className="flex items-center justify-between px-4 mb-3">
            <div className="flex items-center gap-2">
              <User size={16} className="text-purple-500" />
              <h2 className="text-sm font-semibold text-gray-800">我的数字人</h2>
              {digitalHumans.length > 0 && (
                <span className="text-xs text-gray-400">({digitalHumans.length})</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => { console.log('[Home] Opening digital human creation'); onOpenDigitalHuman(); }} className="flex items-center gap-0.5 text-xs text-purple-600 font-medium">
                <Plus size={14} />新建
              </button>
              {digitalHumans.length > 0 && (
                <button onClick={() => { console.log('[Home] Opening all digital humans'); setShowAllDigitalHumans(true); }} className="flex items-center gap-0.5 text-sm text-blue-600 font-medium">
                  全部 <ChevronRight size={16} />
                </button>
              )}
            </div>
          </div>
          {digitalHumans.length === 0 ? (
            <div className="px-4">
              <button onClick={() => { console.log('[Home] Opening digital human creation (empty)'); onOpenDigitalHuman(); }} className="w-full bg-white rounded-2xl p-4 shadow-sm border border-gray-100 flex items-center gap-3 active:scale-[0.98] transition-transform">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-500 flex items-center justify-center">
                  <Plus size={18} className="text-white" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium text-gray-800">创建你的第一个数字人</p>
                  <p className="text-xs text-gray-400">上传视频即可AI生成数字人</p>
                </div>
              </button>
            </div>
          ) : (
            <div className="flex gap-3 overflow-x-auto px-4 pb-2" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
              {digitalHumans.slice(0, 6).map((dh) => (
                <div key={dh.id} className="flex-shrink-0 w-[100px]">
                  <div className="relative aspect-[3/4] rounded-xl overflow-hidden bg-gradient-to-br from-purple-100 to-indigo-100 border border-gray-200">
                    {dh.cover_url ? (
                      <img src={dh.cover_url} alt={dh.title} className="w-full h-full object-cover" />
                    ) : dh.video_url ? (
                      <video src={dh.video_url} className="w-full h-full object-cover" muted />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <User size={28} className="text-purple-300" />
                      </div>
                    )}
                    {dh.status === 'training' && (
                      <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[9px] py-1 text-center flex items-center justify-center gap-1">
                        <Loader2 size={8} className="animate-spin" />训练中
                      </div>
                    )}
                    {dh.status === 'ready' && (
                      <div className="absolute top-1.5 right-1.5 bg-green-500 text-white text-[8px] px-1.5 py-0.5 rounded-full font-medium">就绪</div>
                    )}
                    {dh.status === 'failed' && (
                      <div className="absolute top-1.5 right-1.5 bg-red-500 text-white text-[8px] px-1.5 py-0.5 rounded-full font-medium">失败</div>
                    )}
                  </div>
                  <p className="mt-1.5 text-[11px] text-gray-700 font-medium truncate w-full text-center">{dh.title}</p>
                </div>
              ))}
              <button onClick={() => { console.log('[Home] Opening digital human creation (plus)'); onOpenDigitalHuman(); }} className="flex-shrink-0 w-[100px]">
                <div className="aspect-[3/4] rounded-xl border-2 border-dashed border-gray-300 flex items-center justify-center bg-gray-50">
                  <Plus size={24} className="text-gray-400" />
                </div>
                <p className="mt-1.5 text-[11px] text-gray-400 font-medium text-center">新建</p>
              </button>
            </div>
          )}
        </div>

        <div className="mb-6">
          <div className="flex items-center justify-between px-4 mb-3">
            <div className="flex items-center gap-2">
              <Volume2 size={16} className="text-pink-500" />
              <h2 className="text-sm font-semibold text-gray-800">我的声音</h2>
              {voiceClones.length > 0 && (
                <span className="text-xs text-gray-400">({voiceClones.length})</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => { console.log('[Home] Opening audio record'); onOpenAudioRecord(); }} className="flex items-center gap-0.5 text-xs text-pink-600 font-medium">
                <Plus size={14} />录制
              </button>
              {voiceClones.length > 0 && (
                <button onClick={() => { console.log('[Home] Opening all voice clones'); setShowAllVoiceClones(true); }} className="flex items-center gap-0.5 text-sm text-blue-600 font-medium">
                  全部 <ChevronRight size={16} />
                </button>
              )}
            </div>
          </div>
          {voiceClones.length === 0 ? (
            <div className="px-4">
              <button onClick={() => { console.log('[Home] Opening audio record (empty)'); onOpenAudioRecord(); }} className="w-full bg-white rounded-2xl p-4 shadow-sm border border-gray-100 flex items-center gap-3 active:scale-[0.98] transition-transform">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center">
                  <Mic size={18} className="text-white" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium text-gray-800">录制你的第一个声音</p>
                  <p className="text-xs text-gray-400">AI克隆你的专属声音</p>
                </div>
              </button>
            </div>
          ) : (
            <div className="px-4 space-y-2">
              {voiceClones.slice(0, 3).map((vc) => (
                <div key={vc.id} className="bg-white rounded-xl p-3 shadow-sm border border-gray-100 flex items-center gap-3">
                  <button
                    onClick={() => {
                      if (vc.preview_url) {
                        console.log('[Home] Playing voice preview:', vc.preview_url);
                        const audio = new Audio(vc.preview_url);
                        audio.play().catch(e => console.error('[Home] Play error:', e));
                      } else if (vc.audio_url) {
                        console.log('[Home] Playing original audio:', vc.audio_url);
                        const audio = new Audio(vc.audio_url);
                        audio.play().catch(e => console.error('[Home] Play error:', e));
                      } else {
                        console.log('[Home] No audio URL for voice:', vc.id);
                      }
                    }}
                    className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center shrink-0 active:scale-95 transition-transform"
                  >
                    <Play size={16} className="text-white ml-0.5" />
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{vc.title}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {vc.status === 'cloning' && (
                        <span className="text-[10px] text-yellow-600 flex items-center gap-0.5">
                          <Loader2 size={8} className="animate-spin" />克隆中
                        </span>
                      )}
                      {vc.status === 'ready' && (
                        <span className="text-[10px] text-green-600">就绪</span>
                      )}
                      {vc.status === 'failed' && (
                        <span className="text-[10px] text-red-500">失败</span>
                      )}
                      {vc.clone_voice_id && (
                        <span className="text-[9px] text-gray-400 truncate">{vc.clone_voice_id}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AllDraftsModal drafts={drafts} isOpen={showAllDrafts} onClose={() => setShowAllDrafts(false)} onOpenDraft={openDraft} onDeleteDrafts={deleteDrafts} />

      {showAllDigitalHumans && (
        <div className="fixed inset-0 z-[200] flex flex-col">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => { setShowAllDigitalHumans(false); setManagingDH(false); setSelectedDHIds(new Set()); }} />
          <div className="absolute bottom-0 left-0 right-0 bg-gray-50 rounded-t-3xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 bg-white">
              <div className="flex items-center gap-3">
                <button onClick={() => { setShowAllDigitalHumans(false); setManagingDH(false); setSelectedDHIds(new Set()); }} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
                  <ChevronLeft size={24} className="text-gray-700" />
                </button>
                <h2 className="text-lg font-semibold text-gray-900">全部数字人</h2>
                <span className="text-sm text-gray-400">({digitalHumans.length})</span>
              </div>
              {managingDH ? (
                <div className="flex items-center gap-2">
                  <button onClick={() => { const all = new Set(digitalHumans.map(d => d.id)); setSelectedDHIds(selectedDHIds.size === digitalHumans.length ? new Set() : all); }} className="text-sm text-blue-600 font-medium px-3 py-2 hover:bg-blue-50 rounded-lg transition-colors">
                    {selectedDHIds.size === digitalHumans.length ? '取消全选' : '全选'}
                  </button>
                  <button onClick={() => { setManagingDH(false); setSelectedDHIds(new Set()); }} className="text-sm text-gray-500 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors">完成</button>
                </div>
              ) : (
                <button onClick={() => setManagingDH(true)} className="flex items-center gap-1.5 text-sm text-blue-600 font-medium px-4 py-2 hover:bg-blue-50 rounded-lg transition-colors">
                  <Trash size={16} />管理
                </button>
              )}
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {digitalHumans.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                  <User size={56} className="mb-4 opacity-30" />
                  <p className="text-base">暂无数字人</p>
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-4">
                  {digitalHumans.map((dh) => (
                    <div key={dh.id} onClick={() => { if (managingDH) { const s = new Set(selectedDHIds); s.has(dh.id) ? s.delete(dh.id) : s.add(dh.id); setSelectedDHIds(s); } }} className="relative cursor-pointer group">
                      <div className="relative aspect-[3/4] rounded-xl overflow-hidden bg-gradient-to-br from-purple-100 to-indigo-100 shadow-sm">
                        {dh.cover_url ? (
                          <img src={dh.cover_url} alt={dh.title} className="w-full h-full object-cover" />
                        ) : dh.video_url ? (
                          <video src={dh.video_url} className="w-full h-full object-cover" muted />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <User size={28} className="text-purple-300" />
                          </div>
                        )}
                        {managingDH && selectedDHIds.has(dh.id) && (
                          <div className="absolute inset-0 bg-blue-500/40 flex items-center justify-center">
                            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center shadow-lg"><CheckSquare size={20} className="text-white" /></div>
                          </div>
                        )}
                        {managingDH && !selectedDHIds.has(dh.id) && <div className="absolute inset-0 bg-black/30" />}
                        {dh.status === 'training' && (
                          <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[9px] py-1 text-center flex items-center justify-center gap-1">
                            <Loader2 size={8} className="animate-spin" />训练中
                          </div>
                        )}
                        {dh.status === 'ready' && (
                          <div className="absolute top-1.5 right-1.5 bg-green-500 text-white text-[8px] px-1.5 py-0.5 rounded-full font-medium">就绪</div>
                        )}
                        {dh.status === 'failed' && (
                          <div className="absolute top-1.5 right-1.5 bg-red-500 text-white text-[8px] px-1.5 py-0.5 rounded-full font-medium">失败</div>
                        )}
                      </div>
                      <p className="mt-1.5 text-[11px] text-gray-700 font-medium truncate w-full text-center">{dh.title}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {managingDH && selectedDHIds.size > 0 && (
              <div className="border-t border-gray-200 px-4 pt-4 pb-20 bg-white">
                <button onClick={async () => { if (!confirm(`确定删除 ${selectedDHIds.size} 个数字人？`)) return; for (const id of Array.from(selectedDHIds)) { await fetch(`${API_BASE_URL}/api/digital-humans/${id}`, { method: 'DELETE' }); } setDigitalHumans(prev => prev.filter(d => !selectedDHIds.has(d.id))); setSelectedDHIds(new Set()); setManagingDH(false); }} className="w-full bg-red-500 text-white py-3.5 rounded-xl font-semibold text-base active:scale-[0.98] transition-transform shadow-lg shadow-red-200">
                  删除选中 ({selectedDHIds.size})
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showAllVoiceClones && (
        <div className="fixed inset-0 z-[200] flex flex-col">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => { setShowAllVoiceClones(false); setManagingVC(false); setSelectedVCIds(new Set()); }} />
          <div className="absolute bottom-0 left-0 right-0 bg-gray-50 rounded-t-3xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 bg-white">
              <div className="flex items-center gap-3">
                <button onClick={() => { setShowAllVoiceClones(false); setManagingVC(false); setSelectedVCIds(new Set()); }} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
                  <ChevronLeft size={24} className="text-gray-700" />
                </button>
                <h2 className="text-lg font-semibold text-gray-900">全部声音</h2>
                <span className="text-sm text-gray-400">({voiceClones.length})</span>
              </div>
              {managingVC ? (
                <div className="flex items-center gap-2">
                  <button onClick={() => { const all = new Set(voiceClones.map(v => v.id)); setSelectedVCIds(selectedVCIds.size === voiceClones.length ? new Set() : all); }} className="text-sm text-blue-600 font-medium px-3 py-2 hover:bg-blue-50 rounded-lg transition-colors">
                    {selectedVCIds.size === voiceClones.length ? '取消全选' : '全选'}
                  </button>
                  <button onClick={() => { setManagingVC(false); setSelectedVCIds(new Set()); }} className="text-sm text-gray-500 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors">完成</button>
                </div>
              ) : (
                <button onClick={() => setManagingVC(true)} className="flex items-center gap-1.5 text-sm text-blue-600 font-medium px-4 py-2 hover:bg-blue-50 rounded-lg transition-colors">
                  <Trash size={16} />管理
                </button>
              )}
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {voiceClones.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                  <Volume2 size={56} className="mb-4 opacity-30" />
                  <p className="text-base">暂无声音</p>
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-4">
                  {voiceClones.map((vc) => (
                    <div key={vc.id} onClick={() => {
                      if (managingVC) {
                        const s = new Set(selectedVCIds);
                        s.has(vc.id) ? s.delete(vc.id) : s.add(vc.id);
                        setSelectedVCIds(s);
                      } else if (vc.preview_url || vc.audio_url) {
                        const url = vc.preview_url || vc.audio_url;
                        console.log('[Home] Playing voice:', url);
                        new Audio(url!).play().catch(e => console.error('[Home] Play error:', e));
                      }
                    }} className="relative cursor-pointer group">
                      <div className="relative aspect-[3/4] rounded-xl overflow-hidden bg-gradient-to-br from-pink-100 to-rose-100 shadow-sm">
                        <div className="w-full h-full flex flex-col items-center justify-center gap-2">
                          <div className="w-12 h-12 rounded-full bg-white/80 flex items-center justify-center">
                            <Play size={20} className="text-pink-500 ml-1" />
                          </div>
                          {vc.status === 'ready' && <span className="text-[9px] text-green-600 font-medium">点击播放</span>}
                        </div>
                        {managingVC && selectedVCIds.has(vc.id) && (
                          <div className="absolute inset-0 bg-blue-500/40 flex items-center justify-center">
                            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center shadow-lg"><CheckSquare size={20} className="text-white" /></div>
                          </div>
                        )}
                        {managingVC && !selectedVCIds.has(vc.id) && <div className="absolute inset-0 bg-black/30" />}
                        {vc.status === 'cloning' && (
                          <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[9px] py-1 text-center flex items-center justify-center gap-1">
                            <Loader2 size={8} className="animate-spin" />克隆中
                          </div>
                        )}
                        {vc.status === 'ready' && (
                          <div className="absolute top-1.5 right-1.5 bg-green-500 text-white text-[8px] px-1.5 py-0.5 rounded-full font-medium">就绪</div>
                        )}
                        {vc.status === 'failed' && (
                          <div className="absolute top-1.5 right-1.5 bg-red-500 text-white text-[8px] px-1.5 py-0.5 rounded-full font-medium">失败</div>
                        )}
                      </div>
                      <p className="mt-1.5 text-[11px] text-gray-700 font-medium truncate w-full text-center">{vc.title}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {managingVC && selectedVCIds.size > 0 && (
              <div className="border-t border-gray-200 px-4 pt-4 pb-20 bg-white">
                <button onClick={async () => { if (!confirm(`确定删除 ${selectedVCIds.size} 个声音？`)) return; for (const id of Array.from(selectedVCIds)) { await fetch(`${API_BASE_URL}/api/voice-clones/${id}`, { method: 'DELETE' }); } setVoiceClones(prev => prev.filter(v => !selectedVCIds.has(v.id))); setSelectedVCIds(new Set()); setManagingVC(false); }} className="w-full bg-red-500 text-white py-3.5 rounded-xl font-semibold text-base active:scale-[0.98] transition-transform shadow-lg shadow-red-200">
                  删除选中 ({selectedVCIds.size})
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Cover Draft Picker Modal */}
      {showCoverDraftPicker && (
        <div className="fixed inset-0 z-50 flex flex-col">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowCoverDraftPicker(false)} />
          <div className="absolute bottom-0 left-0 right-0 bg-gray-50 rounded-t-3xl overflow-hidden flex flex-col max-h-[70vh]">
            <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 bg-white">
              <div className="flex items-center gap-3">
                <button onClick={() => setShowCoverDraftPicker(false)} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
                  <ChevronLeft size={24} className="text-gray-700" />
                </button>
                <h2 className="text-lg font-semibold text-gray-900">选择草稿生成封面</h2>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {drafts.filter(d => d.output_video_url).length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                  <Image size={48} className="mb-4 opacity-30" />
                  <p className="text-sm">暂无已完成的草稿</p>
                  <p className="text-xs mt-1">需要先完成视频编辑才能生成封面</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {drafts.filter(d => d.output_video_url).map((draft) => (
                    <button
                      key={draft.id}
                      onClick={() => handleSelectDraftForCover(draft)}
                      className="w-full bg-white rounded-2xl p-3 shadow-sm border border-gray-100 flex items-center gap-3 active:scale-[0.98] transition-transform text-left"
                    >
                      <div className="w-16 h-28 rounded-lg overflow-hidden bg-gray-900 shrink-0">
                        <DraftThumbnailImage videoUrl={draft.output_video_url!} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-gray-900 text-sm truncate">{draft.title || '未命名草稿'}</h3>
                        <p className="text-xs text-gray-400 mt-1">{new Date(draft.updated_at).toLocaleDateString('zh-CN')}</p>
                        <span className="inline-block text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 font-medium mt-2">已渲染</span>
                      </div>
                      <ChevronLeft size={20} className="text-gray-300 rotate-180 shrink-0" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
