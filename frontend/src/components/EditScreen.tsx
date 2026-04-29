import React, { useState, useRef, useCallback, useEffect } from 'react';
import { ChevronLeft, Mic, Trash2, Plus, Film, Image as ImageIcon, Loader2, Cpu, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
import { io, Socket } from 'socket.io-client';
import { useClientRendering } from '../hooks/useClientRendering';
import { processMaterial, ProcessedMaterial } from '../utils/clientMaterialProcessor';
import { isOPFSSupported } from '../utils/opfs';
import { isIndexedDBSupported } from '../utils/indexedDB';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';
const WS_BASE_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
const POLLING_INTERVAL = 200; // 200ms轮询间隔，作为WebSocket的fallback

// 上传队列项（单镜头多文件上传）
interface UploadQueueItem {
  id: string;              // 任务ID
  shotId: number;          // 所属镜头ID
  file: File;              // 文件
  fileName: string;        // 文件名
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  progress: number;        // 0-100
  error?: string;          // 错误信息
  materialId?: string;     // 上传成功后返回的素材ID
  transcodeTaskId?: string; // 转码任务ID
}

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeShotId, setActiveShotId] = useState<number | null>(null);
  
  // 上传队列（单镜头多文件上传）
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const [isProcessingQueue, setIsProcessingQueue] = useState(false);
  const [currentShotId, setCurrentShotId] = useState<number | null>(null);
  
  // 转码任务管理
  const [transcodingMaterials, setTranscodingMaterials] = useState<Set<string>>(new Set());
  const [transcodeFailedMaterials, setTranscodeFailedMaterials] = useState<Set<string>>(new Set());
  const [transcodeProgressMap, setTranscodeProgressMap] = useState<Map<string, number>>(new Map());
  const [showTranscodePanel, setShowTranscodePanel] = useState(false);

  // 客户端渲染状态
  const { state: clientRenderState, enable: enableClientRender, disable: disableClientRender, forceEnable: forceEnableClientRender } = useClientRendering();

  // 使用 ref 来避免循环依赖问题（必须在 clientRenderState 初始化之后定义）
  const uploadQueueRef = useRef(uploadQueue);
  uploadQueueRef.current = uploadQueue;
  const isProcessingQueueRef = useRef(isProcessingQueue);
  isProcessingQueueRef.current = isProcessingQueue;
  const currentShotIdRef = useRef(currentShotId);
  currentShotIdRef.current = currentShotId;
  const clientRenderStateRef = useRef(clientRenderState);
  clientRenderStateRef.current = clientRenderState;
  const [clientProcessedMaterials, setClientProcessedMaterials] = useState<Map<string, ProcessedMaterial>>(new Map());
  const [showClientRenderPanel, setShowClientRenderPanel] = useState(false);
  
  // WebSocket连接
  const socketRef = useRef<Socket | null>(null);
  const [wsStatus, setWsStatus] = useState<'connected' | 'disconnected' | 'connecting'>('connecting');
  
  // Use ref to access latest shots without triggering effect recreation
  const shotsRef = useRef(shots);
  shotsRef.current = shots;
  
  // Use ref to access onRefresh without triggering effect recreation
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  // Check if any material is transcoding or uploading
  const hasTranscodingMaterials = React.useMemo(() => {
    // 检查是否有任何文件正在上传或等待
    const isUploading = uploadQueue.some(item => item.status === 'pending' || item.status === 'uploading');
    
    // 检查是否有素材正在转码
    const isTranscoding = shots.some(shot => 
      shot.materials.some(mat => 
        mat.transcode_status === 'processing' || transcodingMaterials.has(mat.id)
      )
    );
    
    return isUploading || isTranscoding;
  }, [shots, transcodingMaterials, uploadQueue]);
  
  // 计算当前上传的项
  const currentUploadItem = React.useMemo(() => {
    return uploadQueue.find(item => item.status === 'uploading');
  }, [uploadQueue]);
  
  // 计算等待中的项数
  const pendingCount = React.useMemo(() => {
    return uploadQueue.filter(item => item.status === 'pending').length;
  }, [uploadQueue]);
  
  // 检查是否有活跃的上传任务
  const hasActiveUploads = React.useMemo(() => {
    return uploadQueue.some(item => item.status === 'pending' || item.status === 'uploading');
  }, [uploadQueue]);

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
      setWsStatus('connected');
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
      setWsStatus('disconnected');
    });
    
    socket.on('connect_error', (error) => {
      console.error('[WebSocket] Connection error:', error);
      setWsStatus('disconnected');
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
            console.log(`[Polling] Status for ${mat.id}: ${data.status}, progress: ${data.progress}%`);
            
            // 更新进度
            if (data.progress !== undefined) {
              setTranscodeProgressMap(prev => new Map(prev).set(mat.id, data.progress));
            }
            
            if (data.status === 'completed') {
              console.log(`[Polling] Material ${mat.id} completed!`);
              setTranscodingMaterials(prev => {
                const newSet = new Set(prev);
                newSet.delete(mat.id);
                return newSet;
              });
              setTranscodeFailedMaterials(prev => {
                const newSet = new Set(prev);
                newSet.delete(mat.id);
                return newSet;
              });
              // 立即刷新获取最新状态
              onRefreshRef.current();
            } else if (data.status === 'processing') {
              setTranscodingMaterials(prev => new Set(prev).add(mat.id));
              setTranscodeFailedMaterials(prev => {
                const newSet = new Set(prev);
                newSet.delete(mat.id);
                return newSet;
              });
            } else if (data.status === 'failed') {
              console.log(`[Polling] Material ${mat.id} failed!`);
              setTranscodingMaterials(prev => {
                const newSet = new Set(prev);
                newSet.delete(mat.id);
                return newSet;
              });
              setTranscodeFailedMaterials(prev => new Set(prev).add(mat.id));
              // 立即刷新获取最新状态
              onRefreshRef.current();
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
            setTranscodeFailedMaterials(prev => {
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
            setTranscodeFailedMaterials(prev => new Set(prev).add(materialId));
            // 立即刷新获取最新状态
            onRefreshRef.current();
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

  // 客户端渲染模式：双轨并行制
  // 轨道1: 浏览器 WebCodecs 本地转码 (视频② - 用于预览)
  // 轨道2: 服务器 FFmpeg 转码 (视频① - 用于ASR和导出)
  const handleClientSideUpload = async (file: File, shotId: number, uploadItemId: string): Promise<any> => {
    console.log('[EditScreen] ====== 开始双轨并行上传 ======');
    console.log('[EditScreen] 文件名:', file.name, '大小:', (file.size / 1024 / 1024).toFixed(2), 'MB');

    // 双轨进度跟踪
    let browserTrackProgress = 0;
    let serverTrackProgress = 0;
    
    const updateCombinedProgress = () => {
      // 浏览器轨道占50%，服务器轨道占50%
      const combinedProgress = Math.round((browserTrackProgress * 0.5) + (serverTrackProgress * 0.5));
      // 更新队列中的进度
      setUploadQueue(prev => prev.map(item => 
        item.id === uploadItemId ? { ...item, progress: combinedProgress } : item
      ));
    };

    try {
      // 生成素材ID（确保前后端一致）
      const materialId = `mat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      console.log('[EditScreen] 生成素材ID:', materialId);

      // ========== 双轨并行处理 ==========
      console.log('[EditScreen] 启动双轨并行处理...');

      // 轨道1: 浏览器 WebCodecs 本地转码 (0-100% 进度，最终占50%)
      const browserTrackPromise = processMaterial(file, {
        quality: clientRenderState.capability?.recommendedQuality || 'medium',
        generateThumbnail: true,
        materialId,
        onProgress: (progress, stage) => {
          browserTrackProgress = progress;
          updateCombinedProgress();
        },
      }).then(processed => {
        console.log('[EditScreen] 轨道1完成(浏览器转码):', processed.id);
        setClientProcessedMaterials(prev => new Map(prev).set(processed.id, processed));
        return processed;
      });

      // 轨道2: 服务器上传 + FFmpeg 转码 (0-100% 进度，最终占50%)
      const serverTrackPromise = (async () => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', userId);
        formData.append('shotId', shotId.toString());
        formData.append('quality', selectedQuality);
        // 传入 material_id 确保前后端使用相同ID
        formData.append('material_id', materialId);

        return new Promise<any>((resolve, reject) => {
          const xhr = new XMLHttpRequest();

          xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
              // 上传阶段占服务器轨道的50%
              const uploadRatio = e.loaded / e.total;
              serverTrackProgress = Math.round(uploadRatio * 50);
              updateCombinedProgress();
            }
          });

          xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
              const result = JSON.parse(xhr.responseText);
              console.log('[EditScreen] 轨道2完成(服务器上传):', result.id);
              // 上传完成，服务器轨道显示50%，等待转码完成
              serverTrackProgress = 50;
              updateCombinedProgress();
              resolve(result);
            } else {
              reject(new Error('服务器上传失败'));
            }
          });

          xhr.addEventListener('error', () => reject(new Error('上传失败')));
          xhr.addEventListener('abort', () => reject(new Error('上传被取消')));

          xhr.open('POST', `${API_BASE_URL}/api/upload`);
          xhr.send(formData);
        });
      })();

      // 等待双轨都完成
      const [browserResult, serverResult] = await Promise.all([
        browserTrackPromise,
        serverTrackPromise
      ]);

      console.log('[EditScreen] 双轨处理完成:');
      console.log('  - 浏览器轨道:', browserResult.id, '本地URL:', browserResult.videoUrl);
      console.log('  - 服务器轨道:', serverResult.id, '服务器路径:', serverResult.url);

      // 如果服务器返回了转码任务ID，开始跟踪转码状态
      if (serverResult.transcode_task_id) {
        console.log('[EditScreen] 服务器转码任务:', serverResult.transcode_task_id);
        setTranscodingMaterials(prev => new Set(prev).add(serverResult.id));
        // 上传完成但转码未完成，服务器轨道保持50%
        serverTrackProgress = 50;
        updateCombinedProgress();
        setTimeout(() => {
          checkTranscodeStatusImmediately(serverResult.transcode_task_id, serverResult.id);
        }, 100);
      } else {
        // 没有转码任务，服务器轨道完成
        serverTrackProgress = 100;
        updateCombinedProgress();
      }

      console.log('[EditScreen] ====== 双轨并行上传成功 ======');

      // 刷新镜头数据
      onRefresh();
      
      return serverResult;

    } catch (error) {
      console.error('[EditScreen] 双轨处理失败:', error);
      throw error;
    }
  };

  // 服务器渲染模式：原有上传逻辑
  const handleServerSideUpload = async (file: File, shotId: number, uploadItemId: string): Promise<any> => {
    console.log('[EditScreen] ====== 开始服务器上传 ======');
    console.log('[EditScreen] 文件名:', file.name, '大小:', (file.size / 1024 / 1024).toFixed(2), 'MB');

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);
      formData.append('shotId', shotId.toString());
      formData.append('quality', selectedQuality);

      const xhr = new XMLHttpRequest();

      const uploadPromise = new Promise<any>((resolve, reject) => {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100);
            // 更新队列中的进度
            setUploadQueue(prev => prev.map(item => 
              item.id === uploadItemId ? { ...item, progress } : item
            ));
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
      console.log('[EditScreen] 服务器上传完成:', result);
      console.log('[EditScreen] ====== 服务器上传成功 ======');

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
      
      return result;

    } catch (error) {
      console.error('上传失败:', error);
      throw error;
    }
  };

  // 添加上传任务到队列
  const addToUploadQueue = useCallback((files: FileList, shotId: number) => {
    const newItems: UploadQueueItem[] = [];
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const isVideo = file.type.startsWith('video/');
      const isImage = file.type.startsWith('image/');
      
      if (!isVideo && !isImage) {
        console.warn(`[Upload Queue] 跳过不支持的文件: ${file.name}`);
        continue;
      }
      
      const item: UploadQueueItem = {
        id: `upload_${Date.now()}_${i}_${Math.random().toString(36).substr(2, 9)}`,
        shotId,
        file,
        fileName: file.name,
        status: 'pending',
        progress: 0,
      };
      newItems.push(item);
    }
    
    if (newItems.length === 0) {
      alert('没有有效的视频或图片文件');
      return;
    }
    
    const updatedQueue = [...uploadQueue, ...newItems];
    setUploadQueue(updatedQueue);
    setCurrentShotId(shotId);
    console.log(`[Upload Queue] 添加了 ${newItems.length} 个文件到队列`, newItems.map(i => i.fileName));
    
    // 立即更新 ref，确保 processUploadQueue 能获取最新队列
    uploadQueueRef.current = updatedQueue;
    
    // 触发队列处理
    setTimeout(() => processUploadQueue(), 0);
  }, [uploadQueue]);

  // 处理上传队列
  const processUploadQueue = useCallback(async () => {
    // 防止重复执行
    if (isProcessingQueueRef.current) {
      console.log('[Upload Queue] 已有上传任务在执行，跳过');
      return;
    }
    
    // 检查队列中是否有待处理的文件
    const currentQueue = uploadQueueRef.current;
    const pendingItem = currentQueue.find(item => item.status === 'pending');
    if (!pendingItem) {
      console.log('[Upload Queue] 没有待处理的文件');
      return;
    }
    
    console.log(`[Upload Queue] 开始处理: ${pendingItem.fileName}`);
    setIsProcessingQueue(true);
    
    // 更新为上传中状态
    setUploadQueue(prev => prev.map(item => 
      item.id === pendingItem.id ? { ...item, status: 'uploading' } : item
    ));
    
    try {
      const file = pendingItem.file;
      const isVideo = file.type.startsWith('video/');
      const shotId = currentShotIdRef.current!;
      
      let result: any;
      
      if (isVideo && clientRenderStateRef.current.isEnabled) {
        // 客户端渲染模式
        result = await handleClientSideUpload(file, shotId, pendingItem.id);
      } else {
        // 服务器上传模式
        result = await handleServerSideUpload(file, shotId, pendingItem.id);
      }
      
      console.log(`[Upload Queue] 上传完成: ${pendingItem.fileName}`, result);
      
      // 标记为完成
      setUploadQueue(prev => prev.map(item => 
        item.id === pendingItem.id 
          ? { ...item, status: 'completed', materialId: result.id, transcodeTaskId: result.transcode_task_id }
          : item
      ));
      
    } catch (error) {
      console.error(`[Upload Queue] 上传失败: ${pendingItem.fileName}`, error);
      // 标记为失败
      setUploadQueue(prev => prev.map(item => 
        item.id === pendingItem.id 
          ? { ...item, status: 'failed', error: error instanceof Error ? error.message : '上传失败' }
          : item
      ));
    } finally {
      setIsProcessingQueue(false);
      // 继续处理下一个
      setTimeout(() => processUploadQueue(), 100);
    }
  }, []); // 空依赖数组，使用 ref 获取最新值

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0 || activeShotId === null) return;

    // 添加到上传队列
    addToUploadQueue(files, activeShotId);
    
    // 清空input，允许再次选择相同文件
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDeleteMaterial = async (shotId: number, materialId: string) => {
    await onDeleteMaterial(materialId);
  };

  // 重试转码
  const handleRetryTranscode = async (material: Material) => {
    if (!material.transcode_task_id) {
      alert('该素材没有转码任务ID，无法重试');
      return;
    }

    console.log(`[Retry Transcode] 开始重试转码: ${material.id}`);
    
    // 从失败集合中移除
    setTranscodeFailedMaterials(prev => {
      const newSet = new Set(prev);
      newSet.delete(material.id);
      return newSet;
    });
    
    // 添加到转码集合
    setTranscodingMaterials(prev => new Set(prev).add(material.id));
    
    try {
      // 调用后端重试接口
      const response = await fetch(`${API_BASE_URL}/api/transcode/${material.transcode_task_id}/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`[Retry Transcode] 重试成功:`, data);
        
        // 开始检查转码状态
        setTimeout(() => {
          checkTranscodeStatusImmediately(material.transcode_task_id!, material.id);
        }, 100);
      } else {
        const error = await response.json();
        console.error(`[Retry Transcode] 重试失败:`, error);
        alert(`重试转码失败: ${error.error || '未知错误'}`);
        
        // 恢复失败状态
        setTranscodingMaterials(prev => {
          const newSet = new Set(prev);
          newSet.delete(material.id);
          return newSet;
        });
        setTranscodeFailedMaterials(prev => new Set(prev).add(material.id));
      }
    } catch (error) {
      console.error(`[Retry Transcode] 重试异常:`, error);
      alert('重试转码失败，请检查网络连接');
      
      // 恢复失败状态
      setTranscodingMaterials(prev => {
        const newSet = new Set(prev);
        newSet.delete(material.id);
        return newSet;
      });
      setTranscodeFailedMaterials(prev => new Set(prev).add(material.id));
    }
  };

  // Sort shots by sequence
  const sortedShots = [...(shots || [])].sort((a, b) => a.sequence - b.sequence);

  // Calculate total combinations
  const totalCombinations = sortedShots.reduce((acc, shot) => {
    return acc * ((shot.materials?.length) || 1);
  }, 1);

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      {/* Hidden file input - 支持多文件选择 */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="video/*,image/*"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 z-10 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <div className="flex items-center gap-2">
          <h1 className="font-semibold text-gray-900 text-base">智能混剪</h1>
          {/* 客户端渲染状态指示器 */}
          {clientRenderState.isLoading ? (
            <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-[10px] rounded-full animate-pulse">
              检测中...
            </span>
          ) : clientRenderState.isEnabled ? (
            <span className="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] rounded-full">
              本地渲染
            </span>
          ) : (
            <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-[10px] rounded-full">
              服务器渲染
            </span>
          )}
          {/* WebSocket状态指示器 */}
          {wsStatus === 'connected' ? (
            <span className="w-2 h-2 rounded-full bg-green-500" title="实时连接正常" />
          ) : wsStatus === 'connecting' ? (
            <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" title="连接中..." />
          ) : (
            <span className="w-2 h-2 rounded-full bg-red-500" title="实时连接断开，使用轮询模式" />
          )}
        </div>
        {/* 客户端渲染开关 */}
        <button
          onClick={() => setShowClientRenderPanel(!showClientRenderPanel)}
          className={`p-2 rounded-full transition-colors ${clientRenderState.isEnabled ? 'text-green-600 bg-green-50' : 'text-gray-400 hover:text-gray-600'}`}
          title="客户端渲染设置"
        >
          <Cpu size={20} />
        </button>
      </header>

      {/* 全局转码进度面板 */}
      {(transcodingMaterials.size > 0 || transcodeFailedMaterials.size > 0) && (
        <div className="bg-white border-b border-gray-200 p-3 mx-3 mt-2 rounded-xl shadow-sm">
          <div 
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setShowTranscodePanel(!showTranscodePanel)}
          >
            <div className="flex items-center gap-2">
              <Loader2 size={16} className={`text-blue-600 ${transcodingMaterials.size > 0 ? 'animate-spin' : ''}`} />
              <span className="font-medium text-sm text-gray-900">
                转码任务 ({transcodingMaterials.size + transcodeFailedMaterials.size})
              </span>
              {transcodingMaterials.size > 0 && (
                <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-[10px] rounded-full">
                  处理中 {transcodingMaterials.size}
                </span>
              )}
              {transcodeFailedMaterials.size > 0 && (
                <span className="px-2 py-0.5 bg-red-100 text-red-700 text-[10px] rounded-full">
                  失败 {transcodeFailedMaterials.size}
                </span>
              )}
            </div>
            <ChevronLeft 
              size={16} 
              className={`text-gray-400 transition-transform ${showTranscodePanel ? '-rotate-90' : ''}`}
            />
          </div>
          
          {showTranscodePanel && (
            <div className="mt-3 space-y-2 max-h-40 overflow-y-auto">
              {/* 正在转码的素材 */}
              {Array.from(transcodingMaterials).map(materialId => {
                const progress = transcodeProgressMap.get(materialId) || 0;
                // 查找素材信息
                let materialName = '未知素材';
                let materialThumb = '';
                for (const shot of shots) {
                  const mat = shot.materials.find(m => m.id === materialId);
                  if (mat) {
                    materialName = mat.name || `素材-${materialId.slice(-6)}`;
                    materialThumb = mat.thumbnail;
                    break;
                  }
                }
                
                return (
                  <div key={materialId} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                    <div className="w-8 h-8 rounded bg-gray-200 overflow-hidden shrink-0">
                      {materialThumb && (
                        <img 
                          src={`${API_BASE_URL}${materialThumb}`} 
                          alt="" 
                          className="w-full h-full object-cover"
                        />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-gray-700 truncate">{materialName}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-blue-500 rounded-full transition-all duration-300"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-gray-500 w-8 text-right">{progress}%</span>
                      </div>
                    </div>
                    <Loader2 size={14} className="animate-spin text-blue-500 shrink-0" />
                  </div>
                );
              })}
              
              {/* 转码失败的素材 */}
              {Array.from(transcodeFailedMaterials).map(materialId => {
                // 查找素材信息
                let materialName = '未知素材';
                let materialThumb = '';
                for (const shot of shots) {
                  const mat = shot.materials.find(m => m.id === materialId);
                  if (mat) {
                    materialName = mat.name || `素材-${materialId.slice(-6)}`;
                    materialThumb = mat.thumbnail;
                    break;
                  }
                }
                
                return (
                  <div key={materialId} className="flex items-center gap-2 p-2 bg-red-50 rounded-lg">
                    <div className="w-8 h-8 rounded bg-gray-200 overflow-hidden shrink-0">
                      {materialThumb && (
                        <img 
                          src={`${API_BASE_URL}${materialThumb}`} 
                          alt="" 
                          className="w-full h-full object-cover"
                        />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-red-700 truncate">{materialName}</div>
                      <div className="text-[10px] text-red-500">转码失败</div>
                    </div>
                    <AlertCircle size={14} className="text-red-500 shrink-0" />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 客户端渲染面板 */}
      {showClientRenderPanel && (
        <div className="bg-white border-b border-gray-200 p-4 mx-3 mt-2 rounded-xl shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Cpu size={18} className={clientRenderState.isEnabled ? 'text-green-600' : 'text-gray-500'} />
              <span className="font-medium text-sm text-gray-900">客户端渲染</span>
              {clientRenderState.isEnabled && (
                <span className="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] rounded-full">已启用</span>
              )}
            </div>
            {clientRenderState.capability?.canUseClientRendering && (
              <button
                onClick={clientRenderState.isEnabled ? disableClientRender : enableClientRender}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  clientRenderState.isEnabled ? 'bg-green-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                    clientRenderState.isEnabled ? 'translate-x-5' : 'translate-x-1'
                  }`}
                />
              </button>
            )}
          </div>

          {clientRenderState.isLoading ? (
            <div className="text-xs text-gray-500">检测设备能力...</div>
          ) : clientRenderState.capability ? (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                <div>性能等级: {clientRenderState.capability.performanceLevel}</div>
                <div>内存: {clientRenderState.capability.memoryGB}GB</div>
              </div>
              {!clientRenderState.capability.canUseClientRendering && (
                <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                  当前设备不支持客户端渲染
                  {clientRenderState.capability.isMobile && (
                    <button
                      onClick={forceEnableClientRender}
                      className="ml-2 px-2 py-0.5 bg-orange-600 text-white rounded text-[10px]"
                    >
                      强制启用
                    </button>
                  )}
                </div>
              )}
              <div className="flex gap-2 text-[10px]">
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
            </div>
          ) : (
            <div className="text-xs text-red-500">设备检测失败</div>
          )}
        </div>
      )}

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
                className="w-20 h-28 shrink-0 border-2 border-dashed border-gray-200 rounded-lg flex flex-col items-center justify-center text-gray-400 hover:border-blue-400 hover:text-blue-500 bg-gray-50 transition-colors relative overflow-hidden"
              >
                {/* 显示当前镜头的上传状态 */}
                {(() => {
                  const shotUploadingItem = uploadQueue.find(item => item.shotId === shot.id && item.status === 'uploading');
                  const shotPendingItems = uploadQueue.filter(item => item.shotId === shot.id && item.status === 'pending');
                  const shotPendingCount = shotPendingItems.length;
                  
                  // 当前正在上传
                  if (shotUploadingItem) {
                    return (
                      <>
                        <div className="absolute inset-0 bg-blue-50 transition-all" style={{ width: `${shotUploadingItem.progress}%` }} />
                        <div className="relative z-10 flex flex-col items-center px-1">
                          <span className="text-[9px] text-blue-600 font-medium truncate w-full text-center">
                            {shotUploadingItem.fileName}
                          </span>
                          <span className="text-[10px] text-blue-600 font-medium">
                            {shotUploadingItem.progress}%
                          </span>
                          {shotPendingCount > 0 && (
                            <span className="text-[8px] text-blue-500 mt-0.5">
                              等待 {shotPendingCount} 个
                            </span>
                          )}
                        </div>
                      </>
                    );
                  }
                  
                  // 有等待中的文件（在其他镜头上传时）
                  if (shotPendingCount > 0) {
                    const firstPendingItem = shotPendingItems[0];
                    return (
                      <>
                        <div className="absolute inset-0 bg-yellow-50" />
                        <div className="relative z-10 flex flex-col items-center px-1">
                          <Loader2 size={16} className="animate-spin text-yellow-600 mb-1" />
                          <span className="text-[9px] text-yellow-700 font-medium truncate w-full text-center">
                            {firstPendingItem.fileName}
                          </span>
                          <span className="text-[8px] text-yellow-600 mt-0.5">
                            队列中 {shotPendingCount} 个
                          </span>
                        </div>
                      </>
                    );
                  }
                  
                  return (
                    <>
                      <Plus size={20} className="mb-1" />
                      <span className="text-[10px]">添加素材</span>
                    </>
                  );
                })()}
              </button>
              {(shot.materials || []).map((material) => {
                const isTranscoding = material.transcode_status === 'processing' || transcodingMaterials.has(material.id);
                const isTranscodeFailed = material.transcode_status === 'failed' || transcodeFailedMaterials.has(material.id);
                const isTranscodeCompleted = material.transcode_status === 'completed' && !isTranscoding && !isTranscodeFailed;
                
                return (
                  <div 
                    key={material.id} 
                    className={`w-20 h-28 shrink-0 rounded-lg overflow-hidden relative group bg-gray-200 ${isTranscoding ? 'ring-2 ring-blue-400' : ''} ${isTranscodeFailed ? 'ring-2 ring-red-400' : ''}`}
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
                      className={`w-full h-full object-cover ${isTranscoding ? 'opacity-60' : ''}`}
                      referrerPolicy="no-referrer" 
                    />
                    
                    {/* 转码状态遮罩层 */}
                    {isTranscoding && (
                      <div className="absolute inset-0 bg-blue-500/20 flex flex-col items-center justify-center">
                        <Loader2 size={20} className="animate-spin text-blue-600 mb-1" />
                        <span className="text-[9px] text-blue-700 font-medium bg-white/80 px-1.5 py-0.5 rounded">转码中</span>
                      </div>
                    )}
                    
                    {/* 转码失败遮罩层 */}
                    {isTranscodeFailed && (
                      <div className="absolute inset-0 bg-red-500/30 flex flex-col items-center justify-center">
                        <AlertCircle size={20} className="text-red-600 mb-1" />
                        <span className="text-[9px] text-red-700 font-medium bg-white/90 px-1.5 py-0.5 rounded mb-1">转码失败</span>
                        {/* 重试按钮 */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRetryTranscode(material);
                          }}
                          className="flex items-center gap-0.5 px-2 py-0.5 bg-red-600 text-white text-[9px] rounded-full hover:bg-red-700 transition-colors"
                        >
                          <RefreshCw size={8} />
                          重试
                        </button>
                      </div>
                    )}
                    
                    {/* Type indicator */}
                    <div className="absolute top-1 left-1 bg-black/60 text-white p-0.5 rounded flex items-center gap-0.5">
                      {material.type === 'video' ? <Film size={10} /> : <ImageIcon size={10} />}
                      {/* 转码完成指示器 */}
                      {isTranscodeCompleted && material.type === 'video' && (
                        <CheckCircle2 size={8} className="text-green-400" />
                      )}
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
                );
              })}
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
          ) : currentUploadItem ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              上传中 {currentUploadItem?.progress || 0}%
              {uploadQueue.length > 1 && (
                <span className="text-xs">({uploadQueue.filter(i => i.status === 'completed').length + 1}/{uploadQueue.length})</span>
              )}
            </>
          ) : transcodingMaterials.size > 0 ? (
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
