import React, { useState, useRef, useCallback, useEffect } from 'react';
import { ChevronLeft, Mic, Trash2, Plus, Film, Image as ImageIcon, Loader2 } from 'lucide-react';
import { io, Socket } from 'socket.io-client';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3002';
const WS_BASE_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
const POLLING_INTERVAL = 200; // 200ms轮询间隔，作为WebSocket的fallback

interface Material {
  id: string;
  type: 'video' | 'image';
  url: string;
  thumbnail: string;
  duration?: string;
  name: string;
  transcode_status?: 'processing' | 'completed' | 'failed';
  transcode_task_id?: string;
}

interface Shot {
  id: number;
  name: string;
  sequence: number;
  materials: Material[];
}

interface EditScreenProps {
  userId: string;
  shots: Shot[];
  onBack: () => void;
  onSynthesize: () => void;
  onAddShot: () => void;
  onDeleteShot: (id: number) => void;
  onDeleteMaterial: (materialId: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
  selectedQuality: 'low' | 'medium' | 'high' | 'ultra';
  onQualityChange: (quality: 'low' | 'medium' | 'high' | 'ultra') => void;
}

const QUALITY_OPTIONS = [
  { value: 'low', label: '流畅', desc: '720P' },
  { value: 'medium', label: '高清', desc: '1080P' },
  { value: 'high', label: '超清', desc: '2K' },
  { value: 'ultra', label: '原画', desc: '4K' }
];

export default function EditScreen({ 
  userId, 
  shots, 
  onBack, 
  onSynthesize, 
  onAddShot, 
  onDeleteShot, 
  onDeleteMaterial,
  onRefresh,
  isLoading,
  selectedQuality,
  onQualityChange
}: EditScreenProps) {
  const [uploading, setUploading] = useState<{ shotId: number | null; progress: number }>({ shotId: null, progress: 0 });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeShotId, setActiveShotId] = useState<number | null>(null);
  const [transcodingMaterials, setTranscodingMaterials] = useState<Set<string>>(new Set());
  
  // WebSocket连接
  const socketRef = useRef<Socket | null>(null);
  
  // Use ref to access latest shots without triggering effect recreation
  const shotsRef = useRef(shots);
  shotsRef.current = shots;
  
  // Use ref to access onRefresh without triggering effect recreation
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  // Check if any material is transcoding
  const hasTranscodingMaterials = React.useMemo(() => {
    return shots.some(shot => 
      shot.materials.some(mat => 
        mat.transcode_status === 'processing' || transcodingMaterials.has(mat.id)
      )
    );
  }, [shots, transcodingMaterials]);

  // WebSocket连接 - 零延迟接收转码完成通知
  useEffect(() => {
    console.log('[WebSocket] Initializing connection...');
    
    // 创建Socket连接
    const socket = io(API_BASE_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
    });
    
    socketRef.current = socket;
    
    socket.on('connect', () => {
      console.log('[WebSocket] Connected:', socket.id);
      // 注册当前用户，接收该用户的转码通知
      socket.emit('register', { user_id: userId });
    });
    
    socket.on('registered', (data) => {
      console.log('[WebSocket] Registered:', data);
    });
    
    // 监听转码完成事件（零延迟推送）
    socket.on('transcode_complete', (data) => {
      console.log('[WebSocket] Transcode complete received:', data);
      
      // 立即更新状态
      setTranscodingMaterials(prev => {
        const newSet = new Set(prev);
        newSet.delete(data.material_id);
        return newSet;
      });
      
      // 立即刷新获取最新状态
      onRefreshRef.current();
    });
    
    socket.on('disconnect', () => {
      console.log('[WebSocket] Disconnected');
    });
    
    socket.on('error', (error) => {
      console.error('[WebSocket] Error:', error);
    });
    
    return () => {
      console.log('[WebSocket] Closing connection');
      socket.close();
    };
  }, [userId]); // 只在userId变化时重新连接

  // Poll transcoding status - 作为WebSocket的fallback
  React.useEffect(() => {
    console.log('[Polling] Starting transcode status polling (fallback)');
    
    const interval = setInterval(async () => {
      // 从ref获取最新shots，不依赖shots state
      const currentShots = shotsRef.current;
      
      // 获取所有需要检查转码状态的素材（包括processing状态和正在转码中的）
      const processingMaterials = currentShots.flatMap(shot => 
        shot.materials.filter(mat => {
          // 只要有task_id就检查，不限制状态
          if (!mat.transcode_task_id) return false;
          // 检查processing状态或本地记录的正在转码的素材
          return mat.transcode_status === 'processing' || transcodingMaterials.has(mat.id);
        })
      );
      
      if (processingMaterials.length === 0) {
        console.log('[Polling] No processing materials to check');
        return;
      }
      
      console.log(`[Polling] Checking ${processingMaterials.length} materials`);
      
      for (const mat of processingMaterials) {
        try {
          console.log(`[Polling] Checking status for ${mat.id}, task: ${mat.transcode_task_id}`);
          const response = await fetch(`${API_BASE_URL}/api/transcode/${mat.transcode_task_id}/status`);
          if (response.ok) {
            const data = await response.json();
            console.log(`[Polling] Status for ${mat.id}: ${data.status}`);
            
            if (data.status === 'completed') {
              console.log(`[Polling] Material ${mat.id} completed!`);
              setTranscodingMaterials(prev => {
                const newSet = new Set(prev);
                newSet.delete(mat.id);
                return newSet;
              });
              // 立即刷新获取最新状态
              onRefreshRef.current();
            } else if (data.status === 'processing') {
              setTranscodingMaterials(prev => new Set(prev).add(mat.id));
            }
          }
        } catch (error) {
          console.error('[Polling] 查询转码状态失败:', error);
        }
      }
    }, POLLING_INTERVAL);
    
    return () => {
      console.log('[Polling] Stopping transcode status polling');
      clearInterval(interval);
    };
  }, []); // 空依赖数组，只在组件挂载时启动轮询

  // 立即检查转码状态（上传成功后调用）
  const checkTranscodeStatusImmediately = async (taskId: string, materialId: string) => {
    console.log(`[Immediate Check] Starting for material ${materialId}, task ${taskId}`);
    
    const checkStatus = async (): Promise<boolean> => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/transcode/${taskId}/status`);
        if (response.ok) {
          const data = await response.json();
          console.log(`[Immediate Check] Status for ${materialId}: ${data.status}`);
          
          if (data.status === 'completed') {
            console.log(`[Immediate Check] Material ${materialId} completed!`);
            setTranscodingMaterials(prev => {
              const newSet = new Set(prev);
              newSet.delete(materialId);
              return newSet;
            });
            // 立即刷新获取最新状态
            onRefreshRef.current();
            return true;
          } else if (data.status === 'failed') {
            console.log(`[Immediate Check] Material ${materialId} failed`);
            setTranscodingMaterials(prev => {
              const newSet = new Set(prev);
              newSet.delete(materialId);
              return newSet;
            });
            return true;
          }
        }
      } catch (error) {
        console.error('[Immediate Check] Error:', error);
      }
      return false;
    };
    
    // 立即检查一次
    let isCompleted = await checkStatus();
    if (isCompleted) return;
    
    // 每200ms检查一次，最多检查30次（6秒）
    let checkCount = 0;
    const maxChecks = 30;
    
    const intervalId = setInterval(async () => {
      checkCount++;
      isCompleted = await checkStatus();
      
      if (isCompleted || checkCount >= maxChecks) {
        clearInterval(intervalId);
        if (checkCount >= maxChecks) {
          console.log(`[Immediate Check] Max checks reached for ${materialId}`);
        }
      }
    }, 200);
  };

  const handleAddMaterialClick = (shotId: number) => {
    setActiveShotId(shotId);
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0 || activeShotId === null) return;

    const file = files[0];
    const isVideo = file.type.startsWith('video/');
    const isImage = file.type.startsWith('image/');

    if (!isVideo && !isImage) {
      alert('请上传视频或图片文件');
      return;
    }

    setUploading({ shotId: activeShotId, progress: 0 });

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);
      formData.append('shotId', activeShotId.toString());
      formData.append('quality', selectedQuality);

      const xhr = new XMLHttpRequest();
      
      const uploadPromise = new Promise<any>((resolve, reject) => {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100);
            setUploading({ shotId: activeShotId, progress });
          }
        });

        xhr.addEventListener('load', () => {
          if (xhr.status === 200) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            reject(new Error('上传失败'));
          }
        });

        xhr.addEventListener('error', () => reject(new Error('上传失败')));
        xhr.addEventListener('abort', () => reject(new Error('上传被取消')));

        xhr.open('POST', `${API_BASE_URL}/api/upload`);
        xhr.send(formData);
      });

      const result = await uploadPromise;
      console.log('[Upload] Upload completed, result:', result);
      
      // 立即将新素材加入转码跟踪（如果有转码任务）
      if (result.transcode_task_id) {
        console.log('[Upload] Adding material to transcoding tracking:', result.id);
        setTranscodingMaterials(prev => new Set(prev).add(result.id));
      }
      
      // Refresh shots data from backend
      onRefresh();
      
      // 立即开始检查转码状态（不等待轮询）
      if (result.transcode_task_id) {
        console.log('[Upload] Starting immediate transcode status check');
        // 延迟100ms后开始检查，给后端一点时间启动转码
        setTimeout(() => {
          checkTranscodeStatusImmediately(result.transcode_task_id, result.id);
        }, 100);
      }

    } catch (error) {
      console.error('上传失败:', error);
      alert('上传失败，请重试');
    } finally {
      setUploading({ shotId: null, progress: 0 });
      setActiveShotId(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteMaterial = async (shotId: number, materialId: string) => {
    await onDeleteMaterial(materialId);
  };

  // Sort shots by sequence
  const sortedShots = [...(shots || [])].sort((a, b) => a.sequence - b.sequence);

  // Calculate total combinations
  const totalCombinations = sortedShots.reduce((acc, shot) => {
    return acc * ((shot.materials?.length) || 1);
  }, 1);

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*,image/*"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 z-10 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">智能混剪</h1>
        <div className="w-8"></div>
      </header>

      {/* Scrollable Config Content */}
      <div className="flex-1 overflow-y-auto p-3 pb-28 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] space-y-3">
        {sortedShots.map((shot) => (
          <div key={shot.id} className="bg-white rounded-xl p-3 shadow-sm border border-gray-100">
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-gray-800 text-sm">{shot.name}</span>
                <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">素材: {shot.materials?.length || 0}</span>
              </div>
              <div className="flex gap-3 text-gray-400">
                <Mic size={16} className="hover:text-blue-500 cursor-pointer" />
                <Trash2 
                  size={16} 
                  className="hover:text-red-500 cursor-pointer transition-colors" 
                  onClick={() => onDeleteShot(shot.id)}
                />
              </div>
            </div>
            
            <div className="flex gap-2 overflow-x-auto pb-2 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              <button 
                onClick={() => handleAddMaterialClick(shot.id)}
                disabled={uploading.shotId === shot.id}
                className="w-20 h-28 shrink-0 border-2 border-dashed border-gray-200 rounded-lg flex flex-col items-center justify-center text-gray-400 hover:border-blue-400 hover:text-blue-500 bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden"
              >
                {uploading.shotId === shot.id ? (
                  <>
                    <div className="absolute inset-0 bg-blue-50 transition-all" style={{ width: `${uploading.progress}%` }} />
                    <span className="text-[10px] relative z-10 text-blue-600 font-medium">{uploading.progress}%</span>
                  </>
                ) : (
                  <>
                    <Plus size={20} className="mb-1" />
                    <span className="text-[10px]">添加素材</span>
                  </>
                )}
              </button>
              {(shot.materials || []).map((material) => (
                <div 
                  key={material.id} 
                  className="w-20 h-28 shrink-0 rounded-lg overflow-hidden relative group bg-gray-200"
                  onContextMenu={(e) => {
                    e.preventDefault();
                    if (confirm('确定要删除这个素材吗？')) {
                      handleDeleteMaterial(shot.id, material.id);
                    }
                  }}
                >
                  <img 
                    src={`${API_BASE_URL}${material.thumbnail}`} 
                    alt={material.name} 
                    className="w-full h-full object-cover" 
                    referrerPolicy="no-referrer" 
                  />
                  {/* Type indicator */}
                  <div className="absolute top-1 left-1 bg-black/60 text-white p-0.5 rounded">
                    {material.type === 'video' ? <Film size={10} /> : <ImageIcon size={10} />}
                  </div>
                  {/* Duration badge */}
                  {material.duration && (
                    <div className="absolute bottom-1 right-1 bg-black/60 text-white text-[9px] px-1 rounded">
                      {material.duration}
                    </div>
                  )}
                  {/* Delete button - always visible on mobile, hover on desktop */}
                  <button 
                    onClick={() => handleDeleteMaterial(shot.id, material.id)}
                    className="absolute top-1 right-1 p-1 bg-red-500 text-white rounded-full opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity shadow-md"
                    style={{ zIndex: 10 }}
                    aria-label="删除素材"
                  >
                    <Trash2 size={10} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}

        <button 
          onClick={onAddShot}
          className="w-full py-4 border-2 border-dashed border-blue-200 text-blue-500 rounded-xl flex items-center justify-center gap-2 hover:bg-blue-50 transition-colors bg-white shadow-sm mt-2"
        >
          <Plus size={20} />
          <span className="font-medium text-sm">添加镜头</span>
        </button>
      </div>

      {/* Sticky Action Bar */}
      <div className="absolute bottom-16 left-0 right-0 p-3 bg-white border-t border-gray-100 shadow-[0_-4px_10px_rgba(0,0,0,0.03)]">
        {/* Quality Selector */}
        <div className="mb-3">
          <div className="flex gap-1">
            {QUALITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => onQualityChange(opt.value as any)}
                disabled={isLoading}
                className={`flex-1 py-1.5 px-1 rounded-lg text-[10px] font-medium transition-colors ${
                  selectedQuality === opt.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <div>{opt.label}</div>
                <div className="text-[8px] opacity-80">{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>
        
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-xs text-gray-500">预计生成: <strong className="text-gray-900">{Math.min(totalCombinations, 1000)}条</strong></span>
          <span className="text-xs text-gray-500">镜头数: <strong className="text-gray-900">{sortedShots.length}</strong></span>
        </div>
        <button 
          onClick={onSynthesize}
          disabled={isLoading || hasTranscodingMaterials || sortedShots.every(s => (s.materials?.length || 0) === 0)}
          className="w-full bg-blue-600 text-white font-medium py-3 rounded-xl shadow-md shadow-blue-200 active:scale-[0.98] transition-transform disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              生成中...
            </>
          ) : hasTranscodingMaterials ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              转码中...
            </>
          ) : (
            '开始合成视频'
          )}
        </button>
      </div>
    </div>
  );
}
