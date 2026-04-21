import React, { useState, useEffect } from 'react';
import { ChevronLeft, Scissors, FileText, Clock, MoreVertical, Trash2, Edit3 } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3002';

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
}

export default function HomeScreen({ onNavigate, userId }: HomeScreenProps) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeMenu, setActiveMenu] = useState<string | null>(null);

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

  // 删除草稿
  const deleteDraft = async (draftId: string) => {
    if (!confirm('确定要删除这个草稿吗？')) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/kaipai/${draftId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        setDrafts(prev => prev.filter(d => d.id !== draftId));
      }
    } catch (err) {
      alert('删除失败');
    }
    setActiveMenu(null);
  };

  // 打开草稿编辑
  const openDraft = (draft: Draft) => {
    // 通过自定义事件通知父组件打开编辑器
    window.dispatchEvent(new CustomEvent('openKaipaiEditor', { 
      detail: { editId: draft.id, videoUrl: draft.original_video_url }
    }));
  };

  // 格式化时间
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString('zh-CN');
  };

  // 获取状态文本
  const getStatusText = (status: string) => {
    const statusMap: Record<string, string> = {
      'draft': '草稿',
      'transcribing': '识别中',
      'processing': '处理中',
      'completed': '已完成',
      'failed': '失败'
    };
    return statusMap[status] || status;
  };

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      'draft': 'bg-gray-100 text-gray-600',
      'transcribing': 'bg-yellow-100 text-yellow-600',
      'processing': 'bg-blue-100 text-blue-600',
      'completed': 'bg-green-100 text-green-600',
      'failed': 'bg-red-100 text-red-600'
    };
    return colorMap[status] || 'bg-gray-100 text-gray-600';
  };

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-center h-14 shrink-0 bg-white border-b border-gray-100">
        <h1 className="text-lg font-bold text-gray-900">易媒助手</h1>
      </header>
      
      <div className="flex-1 overflow-y-auto p-4">
        {/* 创作工具 */}
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

        {/* 草稿箱 */}
        <div className="flex items-center justify-between mb-3 px-1">
          <h2 className="text-sm font-semibold text-gray-800">文字快剪草稿</h2>
          {drafts.length > 0 && (
            <span className="text-xs text-gray-400">{drafts.length}个草稿</span>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : drafts.length === 0 ? (
          <div className="bg-white rounded-2xl p-8 text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <FileText size={28} className="text-gray-400" />
            </div>
            <p className="text-gray-500 text-sm">暂无草稿</p>
            <p className="text-gray-400 text-xs mt-1">在智能混剪中生成视频后，可以进行文字快剪</p>
          </div>
        ) : (
          <div className="space-y-3">
            {drafts.map(draft => (
              <div 
                key={draft.id}
                className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100"
              >
                <div className="flex items-start justify-between">
                  <div 
                    className="flex-1 cursor-pointer"
                    onClick={() => openDraft(draft)}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold text-gray-900">{draft.title}</h3>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${getStatusColor(draft.status)}`}>
                        {getStatusText(draft.status)}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <span className="flex items-center gap-1">
                        <Clock size={12} />
                        {formatTime(draft.updated_at)}
                      </span>
                      {draft.output_video_url && (
                        <span className="text-green-600">已导出</span>
                      )}
                    </div>
                  </div>
                  
                  {/* 更多操作菜单 */}
                  <div className="relative">
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveMenu(activeMenu === draft.id ? null : draft.id);
                      }}
                      className="p-2 text-gray-400 hover:bg-gray-100 rounded-full"
                    >
                      <MoreVertical size={18} />
                    </button>
                    
                    {activeMenu === draft.id && (
                      <>
                        <div 
                          className="fixed inset-0 z-40"
                          onClick={() => setActiveMenu(null)}
                        />
                        <div className="absolute right-0 top-full mt-1 bg-white rounded-xl shadow-lg border border-gray-100 py-1 z-50 min-w-[120px]">
                          <button
                            onClick={() => openDraft(draft)}
                            className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                          >
                            <Edit3 size={14} />
                            编辑
                          </button>
                          <button
                            onClick={() => deleteDraft(draft.id)}
                            className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                          >
                            <Trash2 size={14} />
                            删除
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
