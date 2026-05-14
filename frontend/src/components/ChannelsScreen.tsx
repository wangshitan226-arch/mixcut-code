import React, { useState, useEffect, useCallback } from 'react';
import { 
  ChevronLeft, Plus, Trash2, RefreshCw, TrendingUp, 
  Video, MessageCircle, Loader2, CheckCircle, AlertCircle,
  ExternalLink, Send, Eye, EyeOff, Flame, X, Play, Edit3
} from 'lucide-react';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

interface Account {
  id: number;
  nickname: string;
  avatar?: string;
  status: 'normal' | 'expired' | 'invalid';
  last_login_at?: string;
}

interface PublishRecord {
  id: number;
  account_id: number;
  title: string;
  tags?: string;
  status: 'pending' | 'uploading' | 'publishing' | 'success' | 'failed';
  platform_link?: string;
  platform_video_id?: string;
  error_msg?: string;
  created_at: string;
}

interface Monitor {
  id: number;
  account_id: number;
  publish_record_id: number;
  platform_video_id: string;
  status: 'monitoring' | 'stopped' | 'expired';
  total_comments: number;
  new_comments: number;
  unreplied_comments: number;
  high_intent_comments: number;
  last_fetch_at?: string;
  created_at: string;
  auto_reply_enabled?: boolean;
  auto_reply_text?: string;
  auto_reply_only_high_intent?: boolean;
}

interface Comment {
  id: number;
  monitor_id: number;
  commenter_name: string;
  content: string;
  is_high_intent: boolean;
  intent_keywords?: string;
  reply_status: 'pending' | 'replied' | 'ignored';
  reply_content?: string;
  is_new: boolean;
  created_at: string;
}

interface Props {
  userId?: string;
  onBack: () => void;
}

type TabType = 'accounts' | 'publish' | 'comments' | 'drafts';

export default function ChannelsScreen({ userId, onBack }: Props) {
  const [activeTab, setActiveTab] = useState<TabType>('accounts');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [records, setRecords] = useState<PublishRecord[]>([]);
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(false);
  
  const [drafts, setDrafts] = useState<any[]>([]);
  const [showDraftPublishModal, setShowDraftPublishModal] = useState(false);
  const [selectedDraft, setSelectedDraft] = useState<any>(null);
  const [draftPublishAccount, setDraftPublishAccount] = useState<number | null>(null);
  const [draftPublishTitle, setDraftPublishTitle] = useState('');
  const [draftPublishTags, setDraftPublishTags] = useState('');
  const [isPublishingDraft, setIsPublishingDraft] = useState(false);
  const [publishTaskId, setPublishTaskId] = useState<string | null>(null);
  const [publishProgress, setPublishProgress] = useState(0);
  const [publishStage, setPublishStage] = useState('');
  
  const [selectedMonitor, setSelectedMonitor] = useState<number | null>(null);
  const [commentFilter, setCommentFilter] = useState<'all' | 'unreplied' | 'high_intent'>('all');
  const [replyText, setReplyText] = useState('');
  const [replyingComment, setReplyingComment] = useState<number | null>(null);
  const [fetchingComments, setFetchingComments] = useState(false);
  const [showAutoReplyModal, setShowAutoReplyModal] = useState(false);
  const [autoReplyText, setAutoReplyText] = useState('');
  const [autoReplyEnabled, setAutoReplyEnabled] = useState(false);
  const [autoReplyOnlyHighIntent, setAutoReplyOnlyHighIntent] = useState(true);
  const [batchReplyText, setBatchReplyText] = useState('');
  const [showBatchReplyModal, setShowBatchReplyModal] = useState(false);
  
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginTaskId, setLoginTaskId] = useState<string | null>(null);
  const [loginStatus, setLoginStatus] = useState<'opening' | 'waiting_login' | 'success' | 'failed'>('opening');
  const [loginError, setLoginError] = useState<string | null>(null);
  
  const [showVideoIdModal, setShowVideoIdModal] = useState(false);
  const [editingRecordId, setEditingRecordId] = useState<number | null>(null);
  const [manualVideoId, setManualVideoId] = useState('');
  const [refreshingRecordId, setRefreshingRecordId] = useState<number | null>(null);

  const loadAccounts = useCallback(async () => {
    if (!userId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/accounts?user_id=${userId}`);
      if (response.ok) {
        const data = await response.json();
        setAccounts(data.accounts || []);
      }
    } catch (e) {
      console.error('加载账号失败:', e);
    }
  }, [userId]);
  
  const loadRecords = useCallback(async () => {
    if (!userId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/publish-records?user_id=${userId}`);
      if (response.ok) {
        const data = await response.json();
        setRecords(data.records || []);
      }
    } catch (e) {
      console.error('加载发布记录失败:', e);
    }
  }, [userId]);
  
  const loadMonitors = useCallback(async () => {
    if (!userId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/monitors?user_id=${userId}`);
      if (response.ok) {
        const data = await response.json();
        setMonitors(data.monitors || []);
      }
    } catch (e) {
      console.error('加载监控任务失败:', e);
    }
  }, [userId]);
  
  const loadDrafts = useCallback(async () => {
    if (!userId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/${userId}/kaipai/drafts`);
      if (response.ok) {
        const data = await response.json();
        setDrafts(data.drafts || []);
      }
    } catch (e) {
      console.error('加载草稿失败:', e);
    }
  }, [userId]);
  
  const loadComments = useCallback(async (monitorId: number, filter: string = 'all') => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/monitors/${monitorId}/comments?filter=${filter}`);
      if (response.ok) {
        const data = await response.json();
        setComments(data.comments || []);
      }
    } catch (e) {
      console.error('加载评论失败:', e);
    }
  }, []);
  
  useEffect(() => {
    loadAccounts();
    loadRecords();
    loadMonitors();
    loadDrafts();
  }, [loadAccounts, loadRecords, loadMonitors, loadDrafts]);
  
  useEffect(() => {
    if (selectedMonitor) {
      loadComments(selectedMonitor, commentFilter);
    }
  }, [selectedMonitor, commentFilter, loadComments]);

  useEffect(() => {
    if (!publishTaskId) return;
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/channels/publish-tasks/${publishTaskId}`);
        if (response.ok) {
          const data = await response.json();
          setPublishProgress(data.progress || 0);
          setPublishStage(data.stage || '');
          if (data.status === 'success' || data.status === 'failed') {
            setPublishTaskId(null);
            loadRecords();
          }
        }
      } catch (e) {
        console.error('轮询发布状态失败:', e);
      }
    }, 3000);
    return () => clearInterval(pollInterval);
  }, [publishTaskId, loadRecords]);

  const handleCloseLoginModal = async () => {
    if (loginTaskId) {
      try {
        await fetch(`${API_BASE_URL}/api/channels/login-tasks/${loginTaskId}/cancel`, {
          method: 'POST'
        });
      } catch (e) {
        console.error('取消登录任务失败:', e);
      }
    }
    setShowLoginModal(false);
    setLoginTaskId(null);
    setLoginStatus('opening');
    setLoginError(null);
  };

  const handleAddAccount = async () => {
    if (!userId) return;
    setLoading(true);
    setLoginError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      });
      
      if (response.ok) {
        const data = await response.json();
        setLoginTaskId(data.task_id);
        setLoginStatus('opening');
        setShowLoginModal(true);
        pollLoginStatus(data.task_id);
      } else {
        const error = await response.json();
        setLoginError(error.error || '启动登录失败');
      }
    } catch (e) {
      console.error('启动登录失败:', e);
      setLoginError('网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };
  
  const pollLoginStatus = async (taskId: string) => {
    const checkStatus = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/channels/login-status/${taskId}?user_id=${userId}`
        );
        if (response.ok) {
          const data = await response.json();
          
          if (data.status === 'success') {
            setLoginStatus('success');
            setTimeout(() => {
              setShowLoginModal(false);
              loadAccounts();
            }, 1500);
            return;
          } else if (data.status === 'failed') {
            setLoginStatus('failed');
            setLoginError(data.error || '登录失败');
            return;
          } else if (data.status === 'waiting_login') {
            setLoginStatus('waiting_login');
          }
          
          setTimeout(() => checkStatus(), 3000);
        }
      } catch (e) {
        console.error('检查登录状态失败:', e);
      }
    };
    
    checkStatus();
  };
  
  const handleDeleteAccount = async (accountId: number) => {
    if (!confirm('确定要删除这个账号吗？')) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/accounts/${accountId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        loadAccounts();
      }
    } catch (e) {
      console.error('删除账号失败:', e);
    }
  };
  
  const handleRelogin = async (accountId: number) => {
    setLoginError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/accounts/${accountId}/relogin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      
      if (response.ok) {
        const data = await response.json();
        setLoginTaskId(data.task_id);
        setLoginStatus('opening');
        setShowLoginModal(true);
        pollLoginStatus(data.task_id);
      }
    } catch (e) {
      console.error('重新登录失败:', e);
      setLoginError('重新登录失败');
    }
  };
  
  const handleCreateMonitor = async (record: PublishRecord) => {
    if (!record.platform_video_id) {
      alert('该发布记录没有视频ID，请先刷新获取视频ID或手动输入');
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/monitors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          account_id: record.account_id,
          publish_record_id: record.id,
          platform_video_id: record.platform_video_id
        })
      });
      
      if (response.ok) {
        loadMonitors();
        setActiveTab('comments');
      } else {
        const error = await response.json();
        alert(error.error || '创建监控失败');
      }
    } catch (e) {
      console.error('创建监控失败:', e);
    }
  };
  
  const handleFetchComments = async (monitorId: number) => {
    setFetchingComments(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/monitors/${monitorId}/fetch`, {
        method: 'POST'
      });
      
      if (response.ok) {
        const data = await response.json();
        alert(`抓取完成！新增 ${data.new_comments} 条评论，其中高意向 ${data.high_intent_count} 条`);
        loadComments(monitorId, commentFilter);
        loadMonitors();
      } else {
        const error = await response.json();
        alert(error.error || '抓取失败');
      }
    } catch (e) {
      console.error('抓取评论失败:', e);
    } finally {
      setFetchingComments(false);
    }
  };
  
  const handleReplyComment = async (commentId: number) => {
    if (!replyText.trim()) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/comments/${commentId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply_text: replyText })
      });
      
      if (response.ok) {
        setReplyText('');
        setReplyingComment(null);
        if (selectedMonitor) {
          loadComments(selectedMonitor, commentFilter);
        }
      } else {
        const error = await response.json();
        alert(error.error || '回复失败');
      }
    } catch (e) {
      console.error('回复评论失败:', e);
    }
  };
  
  const handleIgnoreComment = async (commentId: number) => {
    try {
      await fetch(`${API_BASE_URL}/api/channels/comments/${commentId}/ignore`, {
        method: 'POST'
      });
      if (selectedMonitor) {
        loadComments(selectedMonitor, commentFilter);
      }
    } catch (e) {
      console.error('忽略评论失败:', e);
    }
  };
  
  const handleMarkRead = async (commentId: number) => {
    try {
      await fetch(`${API_BASE_URL}/api/channels/comments/${commentId}/mark-read`, {
        method: 'POST'
      });
      if (selectedMonitor) {
        loadComments(selectedMonitor, commentFilter);
      }
    } catch (e) {
      console.error('标记已读失败:', e);
    }
  };
  
  const handleUpdateAutoReply = async (monitorId: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/monitors/${monitorId}/auto-reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: autoReplyEnabled,
          reply_text: autoReplyText,
          only_high_intent: autoReplyOnlyHighIntent
        })
      });
      
      if (response.ok) {
        setShowAutoReplyModal(false);
        loadMonitors();
        alert('自动回复配置已保存');
      } else {
        const error = await response.json();
        alert(error.error || '保存失败');
      }
    } catch (e) {
      console.error('更新自动回复配置失败:', e);
    }
  };
  
  const handlePublishDraft = async () => {
    if (!selectedDraft || !draftPublishAccount || !draftPublishTitle.trim()) {
      alert('请选择草稿、账号并填写标题');
      return;
    }
    
    setIsPublishingDraft(true);
    try {
      const videoUrl = selectedDraft.output_video_url || selectedDraft.video_url;
      console.log('[DraftPublish] 草稿数据:', selectedDraft);
      console.log('[DraftPublish] 视频URL:', videoUrl);
      
      if (!videoUrl) {
        alert('草稿没有视频文件，请先渲染视频');
        setIsPublishingDraft(false);
        return;
      }
      
      const requestBody = {
        user_id: userId,
        account_id: draftPublishAccount,
        render_id: selectedDraft.id,
        video_path: videoUrl,
        title: draftPublishTitle,
        tags: draftPublishTags,
        description: ''
      };
      console.log('[DraftPublish] 发送请求:', requestBody);
      
      const response = await fetch(`${API_BASE_URL}/api/channels/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });
      
      console.log('[DraftPublish] 响应状态:', response.status);
      const data = await response.json();
      console.log('[DraftPublish] 响应数据:', data);
      
      if (data.success) {
        if (data.task_id) {
          setPublishTaskId(data.task_id);
          setPublishProgress(0);
          setPublishStage('starting');
        }
        setShowDraftPublishModal(false);
        setSelectedDraft(null);
        setDraftPublishTitle('');
        setDraftPublishTags('');
        setActiveTab('publish');
        loadRecords();
      } else {
        alert('发布失败: ' + (data.error || '未知错误'));
      }
    } catch (e: any) {
      console.error('[DraftPublish] 请求异常:', e);
      alert('发布请求失败: ' + e.message);
    } finally {
      setIsPublishingDraft(false);
    }
  };

  const handleRefreshVideoId = async (recordId: number) => {
    setRefreshingRecordId(recordId);
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/publish-records/${recordId}/refresh`, {
        method: 'POST'
      });
      const data = await response.json();
      if (response.ok) {
        alert('已获取视频ID: ' + (data.platform_video_id || '未找到'));
        loadRecords();
      } else {
        alert('获取视频ID失败: ' + (data.error || '未知错误'));
      }
    } catch (e) {
      console.error('刷新视频ID失败:', e);
      alert('刷新失败，请重试');
    } finally {
      setRefreshingRecordId(null);
    }
  };

  const handleSetVideoId = async () => {
    if (!editingRecordId || !manualVideoId.trim()) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/publish-records/${editingRecordId}/set-video-id`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform_video_id: manualVideoId.trim() })
      });
      if (response.ok) {
        setShowVideoIdModal(false);
        setEditingRecordId(null);
        setManualVideoId('');
        loadRecords();
        alert('视频ID已设置');
      } else {
        const error = await response.json();
        alert(error.error || '设置失败');
      }
    } catch (e) {
      console.error('设置视频ID失败:', e);
    }
  };
  
  const handleBatchReply = async (monitorId: number) => {
    if (!batchReplyText.trim()) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/monitors/${monitorId}/batch-reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply_text: batchReplyText })
      });
      
      if (response.ok) {
        const data = await response.json();
        setShowBatchReplyModal(false);
        setBatchReplyText('');
        loadComments(monitorId, commentFilter);
        loadMonitors();
        alert(data.message);
      } else {
        const error = await response.json();
        alert(error.error || '批量回复失败');
      }
    } catch (e) {
      console.error('批量回复失败:', e);
    }
  };
  
  const handleAutoFetchAndReply = async (monitorId: number) => {
    setFetchingComments(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/channels/monitors/${monitorId}/auto-fetch`, {
        method: 'POST'
      });
      
      if (response.ok) {
        const data = await response.json();
        loadComments(monitorId, commentFilter);
        loadMonitors();
        alert(data.message);
      } else {
        const error = await response.json();
        alert(error.error || '自动抓取失败');
      }
    } catch (e) {
      console.error('自动抓取失败:', e);
    } finally {
      setFetchingComments(false);
    }
  };
  
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'normal':
        return <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">正常</span>;
      case 'expired':
        return <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">登录过期</span>;
      case 'invalid':
        return <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">失效</span>;
      default:
        return <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full">未知</span>;
    }
  };
  
  const getPublishStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">成功</span>;
      case 'failed':
        return <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">失败</span>;
      case 'pending':
        return <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full">等待中</span>;
      case 'uploading':
        return <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">上传中</span>;
      case 'publishing':
        return <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">发布中</span>;
      default:
        return <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full">{status}</span>;
    }
  };
  
  const getMonitorStatusBadge = (status: string) => {
    switch (status) {
      case 'monitoring':
        return <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">监控中</span>;
      case 'stopped':
        return <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full">已停止</span>;
      case 'expired':
        return <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">已过期</span>;
      default:
        return <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full">{status}</span>;
    }
  };

  const getStageText = (stage: string) => {
    switch (stage) {
      case 'opening_page': return '打开发布页面...';
      case 'uploading': return '上传视频中...';
      case 'filling_info': return '填写信息中...';
      case 'publishing': return '点击发表中...';
      case 'completed': return '发布完成';
      case 'starting': return '启动中...';
      default: return stage || '处理中...';
    }
  };
  
  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 z-10 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <button onClick={onBack} className="p-1 -ml-1 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
            <ChevronLeft size={24} />
          </button>
          <h1 className="font-semibold text-gray-900 text-base">视频号运营</h1>
        </div>
      </header>
      
      <div className="flex bg-white border-b border-gray-100">
        {[
          { id: 'accounts' as TabType, label: '账号管理', icon: Video },
          { id: 'drafts' as TabType, label: '发布草稿', icon: Play },
          { id: 'publish' as TabType, label: '发布历史', icon: TrendingUp },
          { id: 'comments' as TabType, label: '评论管理', icon: MessageCircle },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-1 py-3 text-sm font-medium transition-colors ${
              activeTab === tab.id 
                ? 'text-blue-600 border-b-2 border-blue-600' 
                : 'text-gray-500'
            }`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>
      
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'accounts' && (
          <div className="p-4">
            <button
              onClick={handleAddAccount}
              disabled={loading}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium flex items-center justify-center gap-2 mb-4 disabled:opacity-50"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
              添加视频号账号
            </button>
            
            {accounts.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <Video size={48} className="mx-auto mb-3 opacity-50" />
                <p className="text-sm">暂无账号，点击上方按钮添加</p>
                <p className="text-xs mt-1">登录后 Cookie 会自动保存</p>
              </div>
            ) : (
              <div className="space-y-3">
                {accounts.map(account => (
                  <div key={account.id} className="bg-white rounded-xl p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center">
                          {account.avatar ? (
                            <img src={account.avatar} alt="" className="w-full h-full rounded-full object-cover" />
                          ) : (
                            <Video size={20} className="text-gray-400" />
                          )}
                        </div>
                        <div>
                          <h3 className="font-medium text-gray-900">{account.nickname}</h3>
                          <div className="flex items-center gap-2 mt-1">
                            {getStatusBadge(account.status)}
                            {account.last_login_at && (
                              <span className="text-xs text-gray-400">
                                最近登录: {new Date(account.last_login_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        {account.status === 'expired' && (
                          <button
                            onClick={() => handleRelogin(account.id)}
                            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
                            title="重新登录"
                          >
                            <RefreshCw size={16} />
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteAccount(account.id)}
                          className="p-2 text-red-500 hover:bg-red-50 rounded-lg"
                          title="删除账号"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'drafts' && (
          <div className="p-4">
            <button
              onClick={() => {
                if (accounts.filter(a => a.status === 'normal').length === 0) {
                  alert('请先添加视频号账号');
                  return;
                }
                setShowDraftPublishModal(true);
                setDraftPublishAccount(accounts.find(a => a.status === 'normal')?.id || null);
              }}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium flex items-center justify-center gap-2 mb-4"
            >
              <Plus size={18} />
              选择草稿发布
            </button>
            
            <p className="text-xs text-gray-400 text-center mb-4">
              点击上方按钮，选择已保存的草稿视频直接发布到视频号
            </p>
            
            {drafts.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <Play size={48} className="mx-auto mb-3 opacity-50" />
                <p className="text-sm">暂无草稿</p>
                <p className="text-xs mt-1">先在编辑器中保存视频</p>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-gray-500 mb-2">已有 {drafts.length} 个草稿</p>
                {drafts.slice(0, 5).map(draft => (
                  <div key={draft.id} className="bg-white rounded-xl p-3 shadow-sm flex items-center gap-3">
                    <div className="w-16 h-12 bg-gray-200 rounded-lg flex items-center justify-center">
                      <Video size={16} className="text-gray-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">{draft.title || '未命名草稿'}</p>
                      <p className="text-xs text-gray-400">
                        {new Date(draft.updated_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'publish' && (
          <div className="p-4">
            {publishTaskId && (
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <Loader2 size={16} className="animate-spin text-blue-600" />
                  <span className="text-sm font-medium text-blue-700">{getStageText(publishStage)}</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${publishProgress}%` }}
                  />
                </div>
                <p className="text-xs text-blue-600 mt-1">{publishProgress}%</p>
              </div>
            )}

            {records.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <TrendingUp size={48} className="mx-auto mb-3 opacity-50" />
                <p className="text-sm">暂无发布记录</p>
                <p className="text-xs mt-1">在"发布草稿"中选择草稿发布到视频号</p>
              </div>
            ) : (
              <div className="space-y-3">
                {records.map(record => (
                  <div key={record.id} className="bg-white rounded-xl p-4 shadow-sm">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-900 line-clamp-2">{record.title}</h3>
                        <div className="flex items-center gap-2 mt-2">
                          {getPublishStatusBadge(record.status)}
                          <span className="text-xs text-gray-400">
                            {new Date(record.created_at).toLocaleString()}
                          </span>
                        </div>
                        {record.tags && (
                          <p className="text-xs text-blue-600 mt-1">
                            {record.tags.split(' ').map(tag => `#${tag}`).join(' ')}
                          </p>
                        )}
                        {record.error_msg && (
                          <p className="text-xs text-red-500 mt-1">{record.error_msg}</p>
                        )}
                        {record.platform_video_id && (
                          <p className="text-xs text-green-600 mt-1">
                            视频ID: {record.platform_video_id}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col gap-1">
                        {record.status === 'success' && !record.platform_video_id && (
                          <>
                            <button
                              onClick={() => handleRefreshVideoId(record.id)}
                              disabled={refreshingRecordId === record.id}
                              className="p-2 text-orange-600 hover:bg-orange-50 rounded-lg"
                              title="自动获取视频ID"
                            >
                              {refreshingRecordId === record.id ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                            </button>
                            <button
                              onClick={() => {
                                setEditingRecordId(record.id);
                                setManualVideoId('');
                                setShowVideoIdModal(true);
                              }}
                              className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
                              title="手动输入视频ID"
                            >
                              <Edit3 size={16} />
                            </button>
                          </>
                        )}
                        {record.status === 'success' && record.platform_video_id && (
                          <button
                            onClick={() => handleCreateMonitor(record)}
                            className="p-2 text-green-600 hover:bg-green-50 rounded-lg"
                            title="监控评论"
                          >
                            <MessageCircle size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'comments' && (
          <div className="h-full flex flex-col">
            {!selectedMonitor ? (
              <div className="p-4">
                {monitors.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <MessageCircle size={48} className="mx-auto mb-3 opacity-50" />
                    <p className="text-sm">暂无监控任务</p>
                    <p className="text-xs mt-1">在发布历史中点击消息图标创建监控</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {monitors.map(monitor => {
                      const record = records.find(r => r.id === monitor.publish_record_id);
                      return (
                        <div 
                          key={monitor.id} 
                          className="bg-white rounded-xl p-4 shadow-sm cursor-pointer active:bg-gray-50"
                          onClick={() => setSelectedMonitor(monitor.id)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <h3 className="font-medium text-gray-900">
                                  {record?.title || '未知视频'}
                                </h3>
                                {getMonitorStatusBadge(monitor.status)}
                              </div>
                              <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                                <span className="flex items-center gap-1">
                                  <MessageCircle size={12} />
                                  {monitor.total_comments} 条评论
                                </span>
                                {monitor.new_comments > 0 && (
                                  <span className="flex items-center gap-1 text-blue-600">
                                    <Eye size={12} />
                                    {monitor.new_comments} 条新评论
                                  </span>
                                )}
                                {monitor.high_intent_comments > 0 && (
                                  <span className="flex items-center gap-1 text-orange-600">
                                    <Flame size={12} />
                                    {monitor.high_intent_comments} 条高意向
                                  </span>
                                )}
                              </div>
                              {monitor.last_fetch_at && (
                                <p className="text-xs text-gray-400 mt-1">
                                  上次抓取: {new Date(monitor.last_fetch_at).toLocaleString()}
                                </p>
                              )}
                            </div>
                            <ChevronLeft size={20} className="text-gray-400 rotate-180" />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex-1 flex flex-col">
                <div className="bg-white border-b border-gray-100 p-3 flex items-center justify-between">
                  <button 
                    onClick={() => setSelectedMonitor(null)}
                    className="flex items-center gap-1 text-sm text-gray-600"
                  >
                    <ChevronLeft size={16} />
                    返回
                  </button>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        const monitor = monitors.find(m => m.id === selectedMonitor);
                        if (monitor) {
                          setAutoReplyEnabled(monitor.auto_reply_enabled || false);
                          setAutoReplyText(monitor.auto_reply_text || '');
                          setAutoReplyOnlyHighIntent(monitor.auto_reply_only_high_intent !== false);
                          setShowAutoReplyModal(true);
                        }
                      }}
                      className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg"
                    >
                      <MessageCircle size={14} />
                      自动回复
                    </button>
                    <button
                      onClick={() => setShowBatchReplyModal(true)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white text-sm rounded-lg"
                    >
                      <Send size={14} />
                      批量回复
                    </button>
                    <button
                      onClick={() => handleAutoFetchAndReply(selectedMonitor)}
                      disabled={fetchingComments}
                      className="flex items-center gap-1 px-3 py-1.5 bg-orange-600 text-white text-sm rounded-lg disabled:opacity-50"
                    >
                      {fetchingComments ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                      抓取+自动回复
                    </button>
                    <button
                      onClick={() => handleFetchComments(selectedMonitor)}
                      disabled={fetchingComments}
                      className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg disabled:opacity-50"
                    >
                      {fetchingComments ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                      仅抓取
                    </button>
                  </div>
                </div>
                
                <div className="bg-white border-b border-gray-100 px-3 py-2 flex gap-2">
                  {[
                    { key: 'all', label: '全部' },
                    { key: 'unreplied', label: '待回复' },
                    { key: 'high_intent', label: '高意向' }
                  ].map(filter => (
                    <button
                      key={filter.key}
                      onClick={() => setCommentFilter(filter.key as any)}
                      className={`px-3 py-1 text-xs rounded-full ${
                        commentFilter === filter.key
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
                
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  {comments.length === 0 ? (
                    <div className="text-center py-12 text-gray-400">
                      <MessageCircle size={36} className="mx-auto mb-2 opacity-50" />
                      <p className="text-sm">暂无评论</p>
                      <p className="text-xs mt-1">点击"仅抓取"获取最新评论</p>
                    </div>
                  ) : (
                    comments.map(comment => (
                      <div 
                        key={comment.id} 
                        className={`bg-white rounded-lg p-3 shadow-sm ${
                          comment.is_new ? 'border-l-4 border-blue-500' : ''
                        } ${comment.is_high_intent ? 'bg-orange-50' : ''}`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-sm text-gray-900">{comment.commenter_name}</span>
                              {comment.is_high_intent && (
                                <span className="flex items-center gap-0.5 px-1.5 py-0.5 bg-orange-100 text-orange-700 text-xs rounded-full">
                                  <Flame size={10} />
                                  高意向
                                </span>
                              )}
                              {comment.is_new && (
                                <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
                                  新
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-700 mt-1">{comment.content}</p>
                            {comment.intent_keywords && (
                              <p className="text-xs text-orange-600 mt-1">
                                关键词: {comment.intent_keywords}
                              </p>
                            )}
                            {comment.reply_status === 'replied' && comment.reply_content && (
                              <div className="mt-2 p-2 bg-green-50 rounded-lg">
                                <p className="text-xs text-green-700">
                                  <span className="font-medium">已回复:</span> {comment.reply_content}
                                </p>
                              </div>
                            )}
                            <div className="flex items-center gap-3 mt-2">
                              <span className="text-xs text-gray-400">
                                {new Date(comment.created_at).toLocaleString()}
                              </span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100">
                          {comment.reply_status === 'pending' && (
                            <>
                              <button
                                onClick={() => setReplyingComment(replyingComment === comment.id ? null : comment.id)}
                                className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded"
                              >
                                <Send size={12} />
                                回复
                              </button>
                              <button
                                onClick={() => handleIgnoreComment(comment.id)}
                                className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 rounded"
                              >
                                <EyeOff size={12} />
                                忽略
                              </button>
                            </>
                          )}
                          {comment.is_new && (
                            <button
                              onClick={() => handleMarkRead(comment.id)}
                              className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 rounded"
                            >
                              <Eye size={12} />
                              已读
                            </button>
                          )}
                        </div>
                        
                        {replyingComment === comment.id && (
                          <div className="mt-2 flex gap-2">
                            <input
                              type="text"
                              value={replyText}
                              onChange={(e) => setReplyText(e.target.value)}
                              placeholder="输入回复内容..."
                              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                              onKeyPress={(e) => e.key === 'Enter' && handleReplyComment(comment.id)}
                            />
                            <button
                              onClick={() => handleReplyComment(comment.id)}
                              disabled={!replyText.trim()}
                              className="px-3 py-2 bg-blue-600 text-white text-sm rounded-lg disabled:opacity-50"
                            >
                              <Send size={14} />
                            </button>
                            <button
                              onClick={() => {
                                setReplyingComment(null);
                                setReplyText('');
                              }}
                              className="px-3 py-2 bg-gray-100 text-gray-600 text-sm rounded-lg"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      
      {showAutoReplyModal && selectedMonitor && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">自动回复配置</h2>
            
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-700">启用自动回复</span>
                <button
                  onClick={() => setAutoReplyEnabled(!autoReplyEnabled)}
                  className={`w-12 h-6 rounded-full transition-colors ${
                    autoReplyEnabled ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    autoReplyEnabled ? 'translate-x-6' : 'translate-x-0.5'
                  }`} />
                </button>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-700">仅回复高意向评论</span>
                <button
                  onClick={() => setAutoReplyOnlyHighIntent(!autoReplyOnlyHighIntent)}
                  className={`w-12 h-6 rounded-full transition-colors ${
                    autoReplyOnlyHighIntent ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    autoReplyOnlyHighIntent ? 'translate-x-6' : 'translate-x-0.5'
                  }`} />
                </button>
              </div>
              
              <div>
                <span className="text-sm text-gray-700">自动回复内容</span>
                <textarea
                  value={autoReplyText}
                  onChange={(e) => setAutoReplyText(e.target.value)}
                  placeholder="输入自动回复的内容..."
                  className="w-full mt-2 p-3 text-sm border border-gray-200 rounded-lg resize-none h-24 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowAutoReplyModal(false)}
                className="flex-1 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium"
              >
                取消
              </button>
              <button
                onClick={() => handleUpdateAutoReply(selectedMonitor)}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
      
      {showBatchReplyModal && selectedMonitor && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">批量回复</h2>
            <p className="text-sm text-gray-500 mb-4">
              将回复所有待回复的评论
            </p>
            
            <textarea
              value={batchReplyText}
              onChange={(e) => setBatchReplyText(e.target.value)}
              placeholder="输入批量回复的内容..."
              className="w-full p-3 text-sm border border-gray-200 rounded-lg resize-none h-24 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowBatchReplyModal(false)}
                className="flex-1 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium"
              >
                取消
              </button>
              <button
                onClick={() => handleBatchReply(selectedMonitor)}
                disabled={!batchReplyText.trim()}
                className="flex-1 py-2.5 bg-purple-600 text-white rounded-lg font-medium disabled:opacity-50"
              >
                发送
              </button>
            </div>
          </div>
        </div>
      )}
      
      {showDraftPublishModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md max-h-[80vh] flex flex-col">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">发布草稿到视频号</h2>
            
            <div className="flex-1 overflow-y-auto space-y-4">
              <div>
                <span className="text-sm text-gray-700">选择视频号账号</span>
                <div className="mt-2 space-y-2">
                  {accounts.filter(a => a.status === 'normal').map(account => (
                    <button
                      key={account.id}
                      onClick={() => setDraftPublishAccount(account.id)}
                      className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all ${
                        draftPublishAccount === account.id
                          ? 'bg-blue-50 border-blue-500'
                          : 'bg-white border-gray-200'
                      }`}
                    >
                      <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                        <Video size={18} className="text-gray-500" />
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-medium text-gray-900">{account.nickname}</p>
                        <p className="text-xs text-green-600">状态正常</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              
              <div>
                <span className="text-sm text-gray-700">选择草稿</span>
                <div className="mt-2 space-y-2 max-h-40 overflow-y-auto">
                  {drafts.map(draft => (
                    <button
                      key={draft.id}
                      onClick={() => {
                        setSelectedDraft(draft);
                        if (!draftPublishTitle && draft.title) {
                          setDraftPublishTitle(draft.title);
                        }
                      }}
                      className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all ${
                        selectedDraft?.id === draft.id
                          ? 'bg-blue-50 border-blue-500'
                          : 'bg-white border-gray-200'
                      }`}
                    >
                      <div className="w-12 h-8 bg-gray-200 rounded flex items-center justify-center">
                        <Video size={14} className="text-gray-400" />
                      </div>
                      <div className="text-left flex-1">
                        <p className="text-sm font-medium text-gray-900 truncate">{draft.title || '未命名草稿'}</p>
                        <p className="text-xs text-gray-400">{new Date(draft.updated_at).toLocaleString()}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              
              <div>
                <span className="text-sm text-gray-700">视频标题</span>
                <input
                  type="text"
                  value={draftPublishTitle}
                  onChange={(e) => setDraftPublishTitle(e.target.value)}
                  placeholder="输入视频标题..."
                  className="w-full mt-2 p-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <span className="text-sm text-gray-700">话题标签（用空格分隔）</span>
                <input
                  type="text"
                  value={draftPublishTags}
                  onChange={(e) => setDraftPublishTags(e.target.value)}
                  placeholder="例如：美食 教程 生活"
                  className="w-full mt-2 p-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowDraftPublishModal(false);
                  setSelectedDraft(null);
                }}
                className="flex-1 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium"
              >
                取消
              </button>
              <button
                onClick={handlePublishDraft}
                disabled={isPublishingDraft || !selectedDraft || !draftPublishAccount || !draftPublishTitle.trim()}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
              >
                {isPublishingDraft ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    发布中...
                  </span>
                ) : '确认发布'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showVideoIdModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">手动输入视频ID</h2>
            <p className="text-sm text-gray-500 mb-4">
              请在视频号助手管理后台找到该视频的ID并输入。视频ID通常可以在视频管理页面的URL中找到。
            </p>
            <input
              type="text"
              value={manualVideoId}
              onChange={(e) => setManualVideoId(e.target.value)}
              placeholder="输入视频ID..."
              className="w-full p-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowVideoIdModal(false);
                  setEditingRecordId(null);
                }}
                className="flex-1 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium"
              >
                取消
              </button>
              <button
                onClick={handleSetVideoId}
                disabled={!manualVideoId.trim()}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
              >
                确认
              </button>
            </div>
          </div>
        </div>
      )}
      
      {showLoginModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm">
            {loginStatus === 'opening' && (
              <>
                <div className="text-center">
                  <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <ExternalLink size={28} className="text-blue-600" />
                  </div>
                  <h2 className="text-lg font-semibold text-gray-900 mb-2">
                    请在浏览器窗口中登录
                  </h2>
                  <p className="text-sm text-gray-500 mb-4">
                    已为您打开视频号助手登录页面，请在弹出的浏览器窗口中使用微信扫码登录
                  </p>
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
                    <p className="text-xs text-yellow-700">
                      登录成功后，系统会自动保存登录状态，下次无需再次扫码
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-center gap-2 text-sm text-gray-400">
                  <Loader2 size={16} className="animate-spin" />
                  等待登录...
                </div>
              </>
            )}
            
            {loginStatus === 'waiting_login' && (
              <>
                <div className="text-center">
                  <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Loader2 size={28} className="text-blue-600 animate-spin" />
                  </div>
                  <h2 className="text-lg font-semibold text-gray-900 mb-2">
                    等待扫码登录
                  </h2>
                  <p className="text-sm text-gray-500">
                    请在浏览器窗口中使用微信扫码登录
                  </p>
                </div>
                <div className="mt-4 flex items-center justify-center gap-2 text-sm text-gray-400">
                  <Loader2 size={16} className="animate-spin" />
                  正在等待...
                </div>
              </>
            )}
            
            {loginStatus === 'success' && (
              <div className="text-center py-4">
                <CheckCircle size={48} className="mx-auto text-green-500 mb-3" />
                <h2 className="text-lg font-semibold text-gray-900 mb-1">
                  登录成功
                </h2>
                <p className="text-sm text-gray-500">
                  账号已添加，登录状态已保存
                </p>
              </div>
            )}
            
            {loginStatus === 'failed' && (
              <>
                <div className="text-center">
                  <AlertCircle size={48} className="mx-auto text-red-500 mb-3" />
                  <h2 className="text-lg font-semibold text-gray-900 mb-1">
                    登录失败
                  </h2>
                  <p className="text-sm text-red-500">
                    {loginError || '登录过程中出现错误'}
                  </p>
                </div>
                <button
                  onClick={handleCloseLoginModal}
                  className="w-full mt-4 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium"
                >
                  关闭
                </button>
              </>
            )}
            
            {(loginStatus === 'opening' || loginStatus === 'waiting_login') && (
              <button
                onClick={handleCloseLoginModal}
                className="w-full mt-4 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium"
              >
                取消
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
