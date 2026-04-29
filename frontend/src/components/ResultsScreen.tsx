import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ChevronLeft, CheckCircle2, Circle, Clock, Download, Play, Loader2, Pause, Square, Scissors, Cpu } from 'lucide-react';
import KaipaiEditor from './KaipaiEditor';
import OptimizedVideoPlayer from './OptimizedVideoPlayer';
import ProcessingModal from './ProcessingModal';
import { saveVideo, getVideo, hasVideoInLocal, initPreloadManager, preloadManager } from '../utils/videoCache';
import { useClientRendering } from '../hooks/useClientRendering';
import { renderPreviewFromFiles, releaseBlobUrl } from '../utils/clientRenderer';
import { exportCombination, uploadToOSS } from '../utils/clientExport';
import { uploadToOSSDirect } from '../utils/ossUpload';
import { generateCombinations, convertServerMaterials, groupMaterialsByShot } from '../utils/combinationGenerator';
import { loadMaterial } from '../utils/opfs';
import { loadMaterialFromIndexedDB } from '../utils/indexedDB';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

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
  server_video_url?: string; // 视频①：服务器高质量拼接视频URL
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
  const [kaipaiVideoUrl, setKaipaiVideoUrl] = useState<string>(''); // 视频①：服务器高质量视频URL
  const [kaipaiClientVideoUrl, setKaipaiClientVideoUrl] = useState<string>(''); // 视频②：客户端预览视频URL
  const [kaipaiLoadingId, setKaipaiLoadingId] = useState<string | null>(null);

  // 进度弹窗状态
  const [processingModal, setProcessingModal] = useState<{
    isOpen: boolean;
    title: string;
    description?: string;
    showProgress: boolean;
    progress: number;
    type: 'download' | 'kaipai';
  }>({
    isOpen: false,
    title: '',
    description: '',
    showProgress: false,
    progress: 0,
    type: 'download'
  });

  // 本地缓存状态
  const [cachedVideos, setCachedVideos] = useState<Set<string>>(new Set());
  const downloadingRef = useRef<Set<string>>(new Set());

  // 客户端渲染状态
  const { state: clientRenderState } = useClientRendering();
  const [clientRenderedVideos, setClientRenderedVideos] = useState<Map<string, string>>(new Map());
  // 使用 ref 获取最新的 clientRenderedVideos，避免闭包问题
  const clientRenderedVideosRef = useRef(clientRenderedVideos);
  useEffect(() => {
    clientRenderedVideosRef.current = clientRenderedVideos;
  }, [clientRenderedVideos]);
  
  // 已上传到OSS的URL缓存（避免重复上传）
  const [ossUploadedUrls, setOssUploadedUrls] = useState<Map<string, string>>(new Map());
  const ossUploadedUrlsRef = useRef(ossUploadedUrls);
  useEffect(() => {
    ossUploadedUrlsRef.current = ossUploadedUrls;
  }, [ossUploadedUrls]);
  const [showClientRenderPanel, setShowClientRenderPanel] = useState(false);

  // 渲染状态锁定 - 防止重复渲染同一视频
  const renderingIdsRef = useRef<Set<string>>(new Set());
  
  // 组件卸载时清理所有 Blob URL
  useEffect(() => {
    return () => {
      // 清理客户端渲染的 Blob URL
      clientRenderedVideos.forEach((url) => {
        if (url.startsWith('blob:')) {
          releaseBlobUrl(url);
          console.log('[ResultsScreen] 清理 Blob URL:', url.substring(0, 50) + '...');
        }
      });
    };
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

      // 检查哪些视频已经缓存到本地
      checkCachedVideos(items);
      
      // 初始化预加载管理器
      initPreloadManager(API_BASE_URL);
      
      // 智能预加载：优先预加载前3个未缓存的视频
      const videosToPreload = items
        .filter(item => item.preview_status === 'completed' && item.preview_url)
        .slice(0, 3);
      
      videosToPreload.forEach((item, index) => {
        if (preloadManager) {
          preloadManager.addToQueue(item.id, item.preview_url!, 3 - index);
        }
      });
    }
  }, [initialCombinations]);

  // 检查已缓存的视频
  const checkCachedVideos = async (items: ResultItem[]) => {
    const cached = new Set<string>();
    for (const item of items) {
      if (item.preview_url) {
        const isCached = await hasVideoInLocal(item.id);
        if (isCached) {
          cached.add(item.id);
        }
      }
    }
    setCachedVideos(cached);
    console.log('[ResultsScreen] 已缓存视频:', cached.size, '个');
  };

  // 缓存视频到本地
  const cacheVideo = async (item: ResultItem) => {
    // 防止重复下载
    if (downloadingRef.current.has(item.id)) {
      console.log('[缓存] 下载正在进行中:', item.id);
      return;
    }

    // 检查是否已缓存
    const isCached = await hasVideoInLocal(item.id);
    if (isCached) {
      console.log('[缓存] 视频已在本地:', item.id);
      setCachedVideos(prev => new Set(prev).add(item.id));
      return;
    }

    if (!item.preview_url) {
      console.log('[缓存] 无视频URL:', item.id);
      return;
    }

    try {
      downloadingRef.current.add(item.id);
      console.log('[缓存] 开始下载视频:', item.id);

      // 构建完整的视频URL
      let fullVideoUrl: string;
      if (item.preview_url.startsWith('blob:')) {
        // Blob URL 是本地生成的，直接下载
        fullVideoUrl = item.preview_url;
      } else if (item.preview_url.startsWith('http')) {
        fullVideoUrl = item.preview_url;
      } else {
        fullVideoUrl = `${API_BASE_URL}${item.preview_url}`;
      }
      
      // Blob URL 直接下载，不需要代理
      let videoDownloadUrl: string;
      if (fullVideoUrl.startsWith('blob:')) {
        videoDownloadUrl = fullVideoUrl;
      } else {
        // 使用后端代理接口避免CORS（无论是OSS还是本地文件）
        videoDownloadUrl = `${API_BASE_URL}/api/proxy/video?url=${encodeURIComponent(fullVideoUrl)}`;
      }

      // 下载视频文件
      const response = await fetch(videoDownloadUrl);
      if (!response.ok) {
        throw new Error('下载视频失败');
      }

      const blob = await response.blob();
      
      // 检查blob大小
      if (blob.size === 0) {
        throw new Error('下载的视频为空');
      }
      
      const file = new File([blob], `${item.id}.mp4`, { type: 'video/mp4' });

      // 保存到本地
      await saveVideo(item.id, file, item.preview_url || '');
      console.log('[缓存] 视频已缓存到本地:', item.id, '大小:', (file.size / 1024 / 1024).toFixed(2), 'MB');

      setCachedVideos(prev => new Set(prev).add(item.id));
    } catch (err) {
      console.error('[缓存] 缓存视频失败:', err);
    } finally {
      downloadingRef.current.delete(item.id);
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

  // 从本地存储加载素材文件
  const loadLocalMaterialFiles = async (materials: Material[]): Promise<File[]> => {
    const files: File[] = [];
    for (const material of materials) {
      let file: File | null = null;
      // 优先从 OPFS 加载
      try {
        const opfsResult = await loadMaterial(material.id);
        if (opfsResult.video) {
          file = opfsResult.video;
        }
      } catch {
        // OPFS 加载失败，尝试 IndexedDB
      }
      if (!file) {
        try {
          const idbResult = await loadMaterialFromIndexedDB(material.id);
          if (idbResult.video) {
            file = new File([idbResult.video], `${material.id}.mp4`, { type: 'video/mp4' });
          }
        } catch {
          // IndexedDB 也失败
        }
      }
      if (file) {
        files.push(file);
      }
    }
    return files;
  };

  // 客户端渲染预览
  const clientRenderPreview = async (item: ResultItem): Promise<string | null> => {
    try {
      console.log('[ResultsScreen] ====== 尝试客户端渲染预览 ======');
      console.log('[ResultsScreen] 组合ID:', item.id, '素材数:', item.materials.length);

      // 检查是否已有客户端渲染结果（使用 ref 获取最新值，避免闭包问题）
      const cachedUrl = clientRenderedVideosRef.current.get(item.id);
      if (cachedUrl) {
        console.log('[ResultsScreen] 使用缓存的客户端渲染结果:', cachedUrl);
        return cachedUrl;
      }

      // 加载本地素材文件
      console.log('[ResultsScreen] 从本地存储加载素材...');
      const files = await loadLocalMaterialFiles(item.materials);
      console.log('[ResultsScreen] 本地素材加载结果:', files.length, '/', item.materials.length, '个');

      if (files.length === 0) {
        console.warn('[ResultsScreen] 没有本地素材，降级到服务器渲染');
        return null;
      }

      // 客户端秒级拼接
      console.log('[ResultsScreen] 开始客户端秒级拼接...');
      const startTime = performance.now();
      const result = await renderPreviewFromFiles(files, {
        renderId: `result_${item.id}`,
        onProgress: (progress, stage) => {
          console.log(`[ResultsScreen] 拼接进度: ${progress}% - ${stage}`);
        },
      });
      const duration = performance.now() - startTime;
      console.log('[ResultsScreen] 客户端拼接完成，耗时:', duration.toFixed(0), 'ms');

      // 保存渲染结果
      setClientRenderedVideos(prev => new Map(prev).set(item.id, result.blobUrl));
      console.log('[ResultsScreen] ====== 客户端渲染预览成功 ======');
      return result.blobUrl;
    } catch (error) {
      console.error('[ResultsScreen] 客户端渲染失败:', error);
      return null;
    }
  };

  // 启动服务器FFmpeg高质量拼接并上传OSS（视频①）
  const startServerFFmpegRender = useCallback(async (item: ResultItem) => {
    console.log(`[双轨制] ========== 服务器FFmpeg拼接+OSS上传开始 ==========`);
    console.log(`[双轨制] 组合ID: ${item.id}`);
    console.log(`[双轨制] 当前状态: server_video_url=${item.server_video_url || '无'}`);
    
    try {
      console.log(`[双轨制] 调用接口: POST /api/combinations/${item.id}/server-render`);
      
      const response = await fetch(`${API_BASE_URL}/api/combinations/${item.id}/server-render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      console.log(`[双轨制] 后端响应状态码: ${response.status}`);
      
      const data = await response.json();
      console.log('[双轨制] 后端响应数据:', JSON.stringify(data, null, 2));
      
      if (data.status === 'completed') {
        console.log(`[双轨制] ✅ 服务器FFmpeg拼接+OSS上传完成`);
        console.log(`[双轨制] 📹 视频①OSS URL: ${data.video_url}`);
        
        // 视频①已上传OSS
        setResults(prev => prev.map(r =>
          r.id === item.id ? { ...r, server_video_url: data.video_url } : r
        ));
      } else if (data.status === 'processing' || data.status === 'local_ready') {
        console.log(`[双轨制] ⏳ 服务器FFmpeg拼接+OSS上传中...`);
      } else if (data.error) {
        console.error(`[双轨制] ❌ 服务器FFmpeg拼接+OSS上传失败: ${data.error}`);
      }
      
      return data;
    } catch (error) {
      console.error('[双轨制] ❌ 启动服务器FFmpeg拼接+OSS上传异常:', error);
      return null;
    } finally {
      console.log(`[双轨制] ========== 服务器FFmpeg拼接+OSS上传结束 ==========`);
    }
  }, []);

  // 获取稳定的视频URL - 确保同一视频始终使用相同URL
  const getStableVideoUrl = useCallback((item: ResultItem): string | null => {
    // 优先级1: 已缓存的客户端渲染结果（最稳定）
    const cachedClientUrl = clientRenderedVideosRef.current.get(item.id);
    if (cachedClientUrl) {
      console.log(`[getStableVideoUrl] 使用缓存的客户端渲染URL: ${item.id}`);
      return cachedClientUrl;
    }
    
    // 优先级2: 已存在的 preview_url
    if (item.preview_url && item.preview_status === 'completed') {
      console.log(`[getStableVideoUrl] 使用已有的 preview_url: ${item.id}`);
      return item.preview_url;
    }
    
    return null;
  }, []);

  const handlePlay = useCallback(async (item: ResultItem) => {
    // If already playing, stop
    if (playingId === item.id) {
      setPlayingId(null);
      return;
    }

    // 检查是否已有稳定的视频URL
    const stableUrl = getStableVideoUrl(item);
    if (stableUrl) {
      console.log(`[handlePlay] 使用稳定的URL直接播放: ${item.id}`);
      setPlayingId(item.id);
      // 确保 results 中的 URL 是最新的
      if (item.preview_url !== stableUrl) {
        setResults(prev => prev.map(r =>
          r.id === item.id ? { ...r, preview_url: stableUrl, preview_status: 'completed' } : r
        ));
      }
      // 后台缓存视频
      cacheVideo(item);
      // 同时确保服务器FFmpeg高质量视频+OSS也在生成中（如果还没有）
      if (!item.server_video_url) {
        startServerFFmpegRender(item);
      }
      return;
    }

    // 检查是否正在渲染中，防止重复渲染
    if (renderingIdsRef.current.has(item.id)) {
      console.log(`[handlePlay] 渲染进行中，跳过重复请求: ${item.id}`);
      setPlayingId(item.id);
      return;
    }

    // For pending items: show player immediately, generate in background
    if (item.preview_status === 'pending' || item.preview_status === 'failed' || !item.preview_url) {
      // Set a temporary loading state for this item
      setResults(prev => prev.map(r =>
        r.id === item.id ? { ...r, preview_status: 'loading' } : r
      ));
      setPlayingId(item.id);

      // 标记为正在渲染
      renderingIdsRef.current.add(item.id);

      try {
        // ========== 双轨并行：同时启动浏览器WebCodecs拼接（视频②）和本地FFmpeg拼接（视频①） ==========
        console.log(`[双轨制] ========== 点击预览，双轨并行开始 ==========`);
        console.log(`[双轨制] 组合ID: ${item.id}`);
        console.log(`[双轨制] 素材列表: ${item.materials.map(m => m.id).join(', ')}`);
        
        // 1. 启动服务器FFmpeg高质量拼接+OSS上传（视频①）- 异步，不阻塞预览
        console.log(`[双轨制] 🎬 轨道①: 启动服务器FFmpeg拼接+OSS上传（异步）`);
        startServerFFmpegRender(item);

        // 2. 浏览器WebCodecs快速拼接（视频②）- 用于立即预览
        console.log(`[双轨制] 🌐 轨道②: 启动浏览器WebCodecs拼接`);
        let videoUrl: string | null = null;
        console.log(`[双轨制] 浏览器WebCodecs状态: ${clientRenderState.isEnabled ? '✅ 开启' : '❌ 关闭'}`);
        
        if (clientRenderState.isEnabled) {
          console.log(`[双轨制] 调用 clientRenderPreview...`);
          videoUrl = await clientRenderPreview(item);
          console.log(`[双轨制] clientRenderPreview 返回: ${videoUrl ? '✅ 成功' : '❌ 失败'}`);
          if (videoUrl) {
            console.log(`[双轨制] 📹 视频② Blob URL: ${videoUrl.substring(0, 50)}...`);
          }
        } else {
          console.log('[双轨制] 浏览器WebCodecs未开启，跳过轨道②');
        }

        // 浏览器WebCodecs拼接失败或未开启，降级到本地FFmpeg拼接
        if (!videoUrl) {
          console.log('[双轨制] ⚠️ 轨道②失败，降级到本地FFmpeg拼接...');
          videoUrl = await triggerConcat(item);
          console.log(`[双轨制] 本地FFmpeg降级拼接: ${videoUrl ? '✅ 成功' : '❌ 失败'}`);
        }
        
        console.log(`[双轨制] ========== 双轨并行结束 ==========`);

        if (videoUrl) {
          // Video ready, update status (player will auto-load)
          setResults(prev => prev.map(r =>
            r.id === item.id ? { ...r, preview_status: 'completed', preview_url: videoUrl } : r
          ));
          // 后台缓存视频
          const updatedItem = { ...item, preview_url: videoUrl, preview_status: 'completed' as const };
          cacheVideo(updatedItem);
        } else {
          // Failed, show error
          setResults(prev => prev.map(r =>
            r.id === item.id ? { ...r, preview_status: 'failed' } : r
          ));
          setPlayingId(null);
        }
      } finally {
        // 移除渲染锁定
        renderingIdsRef.current.delete(item.id);
      }
    }
  }, [playingId, clientRenderState.isEnabled, startServerFFmpegRender, getStableVideoUrl]);

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

  // 客户端导出视频
  const clientExportVideo = async (item: ResultItem): Promise<Blob | null> => {
    try {
      // 检查是否已有客户端渲染结果（使用 ref 获取最新值）
      let existingBlob: Blob | undefined;
      const cachedUrl = clientRenderedVideosRef.current.get(item.id);
      if (cachedUrl) {
        const response = await fetch(cachedUrl);
        existingBlob = await response.blob();
      }

      // 加载本地素材文件
      const files = await loadLocalMaterialFiles(item.materials);
      if (files.length === 0) {
        return null;
      }

      // 客户端导出
      const result = await exportCombination(files, {
        quality: defaultQuality === 'ultra' ? 'hd' : defaultQuality === 'low' ? 'preview' : 'hd',
        existingBlob,
        onProgress: (progress, stage) => {
          console.log(`[ClientExport] 导出进度: ${progress}% - ${stage}`);
        },
      });

      return result.blob;
    } catch (error) {
      console.error('[ClientExport] 客户端导出失败:', error);
      return null;
    }
  };

  /**
   * 处理单个视频下载
   * 
   * 修复说明：
   * 1. 下载必须使用服务器FFmpeg渲染后上传到OSS的公网URL
   * 2. 不能使用客户端浏览器渲染的Blob URL（效果差）
   * 3. 不能使用服务器本地文件路径（CORS问题）
   * 4. 如果没有OSS URL，调用后端接口触发服务器渲染，显示进度弹窗
   * 
   * 重要：必须从 results 数组中获取最新数据，因为传入的 item 可能是旧引用
   */
  const handleDownload = useCallback(async (item: ResultItem, e: React.MouseEvent) => {
    e.stopPropagation();

    // 检查是否已经在下载中
    if (downloadingIds.has(item.id)) {
      console.log('[Download] 下载进行中，跳过:', item.id);
      return;
    }

    // 从 results 数组中获取最新数据（关键修复）
    const currentItem = results.find(r => r.id === item.id);
    if (!currentItem) {
      console.error('[Download] 找不到视频数据:', item.id);
      alert('视频数据不存在');
      return;
    }

    setDownloadingIds(prev => new Set(prev).add(item.id));

    try {
      // 检查是否有OSS URL（server_video_url 优先，其次是 oss_url）
      const downloadUrl = currentItem.server_video_url || currentItem.oss_url;
      
      if (downloadUrl) {
        console.log('[Download] 使用OSS URL下载:', downloadUrl);
        // 显示下载中弹窗
        setProcessingModal({
          isOpen: true,
          title: '视频下载中',
          description: '正在下载视频，请稍候...',
          showProgress: false,
          progress: 0,
          type: 'download'
        });
        await downloadVideo(downloadUrl, `mixcut_${currentItem.id}.mp4`);
        setProcessingModal(prev => ({ ...prev, isOpen: false }));
        return;
      }

      // 无OSS URL，需要准备
      console.log('[Download] 无OSS URL，调用后端接口:', currentItem.id);
      
      // 显示视频准备中弹窗
      setProcessingModal({
        isOpen: true,
        title: '视频准备中',
        description: '正在将视频上传到云端，请稍候...',
        showProgress: false,
        progress: 0,
        type: 'download'
      });
      
      const response = await fetch(`${API_BASE_URL}/api/combinations/${currentItem.id}/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        throw new Error('请求下载接口失败');
      }

      const data = await response.json();
      console.log('[Download] 后端响应:', data);

      if (data.status === 'completed' && data.video_url) {
        // 立即完成，开始下载
        console.log('[Download] 获取到OSS URL:', data.video_url);
        
        // 更新弹窗为下载中
        setProcessingModal({
          isOpen: true,
          title: '视频下载中',
          description: '视频准备完成，正在下载...',
          showProgress: false,
          progress: 0,
          type: 'download'
        });
        
        await downloadVideo(data.video_url, `mixcut_${currentItem.id}.mp4`);
        
        // 更新本地状态，缓存OSS URL
        if (data.source === 'server_oss') {
          setResults(prev => prev.map(r =>
            r.id === currentItem.id ? { ...r, server_video_url: data.video_url } : r
          ));
        } else {
          setResults(prev => prev.map(r =>
            r.id === currentItem.id ? { ...r, oss_url: data.video_url } : r
          ));
        }
        
        setProcessingModal(prev => ({ ...prev, isOpen: false }));
      } else if (data.status === 'processing') {
        // 服务器正在处理，保持弹窗显示，轮询状态
        await pollDownloadStatus(currentItem);
      } else {
        throw new Error(data.error || '下载失败');
      }
    } catch (error) {
      console.error('[Download] 下载失败:', error);
      setProcessingModal(prev => ({ ...prev, isOpen: false }));
      alert('下载失败：' + (error instanceof Error ? error.message : '请重试'));
    } finally {
      setDownloadingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(item.id);
        return newSet;
      });
    }
  }, [results, downloadingIds]);

  /**
   * 轮询下载状态
   */
  const pollDownloadStatus = async (item: ResultItem) => {
    const maxAttempts = 60; // 最多轮询60次（约2分钟）
    const interval = 2000; // 每2秒轮询一次
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/combinations/${item.id}/server-render/status`, {
          method: 'GET'
        });
        
        if (!response.ok) continue;
        
        const data = await response.json();
        console.log('[Download] 轮询状态:', data);
        
        if (data.status === 'completed' && data.video_url) {
          // 视频准备完成，开始下载
          setProcessingModal({
            isOpen: true,
            title: '视频下载中',
            description: '视频准备完成，正在下载...',
            showProgress: false,
            progress: 0,
            type: 'download'
          });
          
          await downloadVideo(data.video_url, `mixcut_${item.id}.mp4`);
          
          // 更新本地状态
          setResults(prev => prev.map(r =>
            r.id === item.id ? { ...r, server_video_url: data.video_url } : r
          ));
          
          setProcessingModal(prev => ({ ...prev, isOpen: false }));
          return;
        }
        
        // 继续等待
        await new Promise(resolve => setTimeout(resolve, interval));
      } catch (error) {
        console.error('[Download] 轮询失败:', error);
      }
    }
    
    // 超时
    setProcessingModal(prev => ({ ...prev, isOpen: false }));
    alert('视频准备超时，请稍后再试');
  };

  /**
   * 批量下载选中的视频
   * 
   * 修复说明：
   * 1. 批量下载同样必须使用OSS URL
   * 2. 如果没有OSS URL，显示"视频准备中"弹窗，等待上传完成
   * 3. 上传完成后，弹窗改为"视频下载中"，下载完成后关闭弹窗
   * 4. 提供下载进度反馈
   */
  const handleBatchDownload = useCallback(async () => {
    const selectedItems = results.filter(r => r.selected);
    if (selectedItems.length === 0) {
      alert('请先选择要下载的视频');
      return;
    }

    // 只处理第一个选中的视频（简化逻辑，避免多个弹窗冲突）
    const item = selectedItems[0];
    
    // 从 results 获取最新数据
    const currentItem = results.find(r => r.id === item.id);
    if (!currentItem) {
      alert('视频数据不存在');
      return;
    }

    // 检查是否已经在下载中
    if (downloadingIds.has(currentItem.id)) {
      console.log('[BatchDownload] 下载进行中，跳过:', currentItem.id);
      return;
    }

    setDownloadingIds(prev => new Set(prev).add(currentItem.id));

    try {
      // 检查是否有OSS URL
      const downloadUrl = currentItem.server_video_url || currentItem.oss_url;

      if (downloadUrl) {
        // 有OSS URL，直接下载
        console.log('[BatchDownload] 使用OSS URL下载:', currentItem.id);
        
        // 显示下载中弹窗
        setProcessingModal({
          isOpen: true,
          title: '视频下载中',
          description: `正在下载视频 ${currentItem.index + 1}，请稍候...`,
          showProgress: false,
          progress: 0,
          type: 'download'
        });
        
        await downloadVideo(downloadUrl, `mixcut_${currentItem.id}.mp4`);
        
        // 关闭弹窗
        setProcessingModal(prev => ({ ...prev, isOpen: false }));
        
        // 如果还有多个选中，提示用户
        if (selectedItems.length > 1) {
          alert(`已下载选中的第1个视频，还有 ${selectedItems.length - 1} 个视频未下载。请重新选择后再次下载。`);
        }
      } else {
        // 没有OSS URL，需要准备
        console.log('[BatchDownload] 无OSS URL，调用后端接口:', currentItem.id);
        
        // 显示视频准备中弹窗
        setProcessingModal({
          isOpen: true,
          title: '视频准备中',
          description: `正在将视频 ${currentItem.index + 1} 上传到云端，请稍候...`,
          showProgress: false,
          progress: 0,
          type: 'download'
        });
        
        const response = await fetch(`${API_BASE_URL}/api/combinations/${currentItem.id}/download`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
          throw new Error('请求下载接口失败');
        }

        const data = await response.json();
        console.log('[BatchDownload] 后端响应:', data);

        if (data.status === 'completed' && data.video_url) {
          // 立即完成，开始下载
          console.log('[BatchDownload] 获取到OSS URL:', data.video_url);
          
          // 更新弹窗为下载中
          setProcessingModal({
            isOpen: true,
            title: '视频下载中',
            description: `视频 ${currentItem.index + 1} 准备完成，正在下载...`,
            showProgress: false,
            progress: 0,
            type: 'download'
          });
          
          await downloadVideo(data.video_url, `mixcut_${currentItem.id}.mp4`);
          
          // 更新本地状态
          if (data.source === 'server_oss') {
            setResults(prev => prev.map(r =>
              r.id === currentItem.id ? { ...r, server_video_url: data.video_url } : r
            ));
          } else {
            setResults(prev => prev.map(r =>
              r.id === currentItem.id ? { ...r, oss_url: data.video_url } : r
            ));
          }
          
          // 关闭弹窗
          setProcessingModal(prev => ({ ...prev, isOpen: false }));
          
          // 如果还有多个选中，提示用户
          if (selectedItems.length > 1) {
            alert(`已下载选中的第1个视频，还有 ${selectedItems.length - 1} 个视频未下载。请重新选择后再次下载。`);
          }
        } else if (data.status === 'processing') {
          // 服务器正在处理，轮询状态
          await pollBatchDownloadStatus(currentItem);
          
          // 如果还有多个选中，提示用户
          if (selectedItems.length > 1) {
            alert(`已下载选中的第1个视频，还有 ${selectedItems.length - 1} 个视频未下载。请重新选择后再次下载。`);
          }
        } else {
          throw new Error(data.error || '下载失败');
        }
      }
    } catch (error) {
      console.error('[BatchDownload] 下载失败:', error);
      setProcessingModal(prev => ({ ...prev, isOpen: false }));
      alert('下载失败：' + (error instanceof Error ? error.message : '请重试'));
    } finally {
      setDownloadingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(item.id);
        return newSet;
      });
    }
  }, [results, downloadingIds]);

  /**
   * 批量下载状态轮询
   */
  const pollBatchDownloadStatus = async (item: ResultItem) => {
    const maxAttempts = 60; // 最多轮询60次（约2分钟）
    const interval = 2000; // 每2秒轮询一次
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/combinations/${item.id}/server-render/status`, {
          method: 'GET'
        });
        
        if (!response.ok) continue;
        
        const data = await response.json();
        console.log('[BatchDownload] 轮询状态:', data);
        
        if (data.status === 'completed' && data.video_url) {
          // 视频准备完成，开始下载
          setProcessingModal({
            isOpen: true,
            title: '视频下载中',
            description: `视频 ${item.index + 1} 准备完成，正在下载...`,
            showProgress: false,
            progress: 0,
            type: 'download'
          });
          
          await downloadVideo(data.video_url, `mixcut_${item.id}.mp4`);
          
          // 更新本地状态
          setResults(prev => prev.map(r =>
            r.id === item.id ? { ...r, server_video_url: data.video_url } : r
          ));
          
          // 关闭弹窗
          setProcessingModal(prev => ({ ...prev, isOpen: false }));
          return;
        }
        
        // 继续等待
        await new Promise(resolve => setTimeout(resolve, interval));
      } catch (error) {
        console.error('[BatchDownload] 轮询失败:', error);
      }
    }
    
    // 超时
    setProcessingModal(prev => ({ ...prev, isOpen: false }));
    alert('视频准备超时，请稍后再试');
  };

  // 打开网感剪辑（使用选中的视频）- 双轨制版本
  /**
   * 修复说明：
   * 1. 文字快剪需要两个视频都准备好才能进入界面
   * 2. 视频①：服务器FFmpeg高质量+OSS（用于ASR/导出）
   * 3. 视频②：浏览器WebCodecs预览视频（用于编辑器预览播放）
   * 4. 如果任一视频未准备好，显示"视频准备中"弹窗，等待两者都完成
   */
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
    
    console.log(`[双轨制] ========== 点击文字快剪，开始准备视频 ==========`);
    console.log(`[双轨制] 组合ID: ${item.id}`);
    console.log(`[双轨制] 当前状态: server_video_url=${item.server_video_url || '无'}, preview_url=${item.preview_url || '无'}`);
    
    // 检查两个视频是否都需要准备
    let serverVideoUrl = item.server_video_url || item.oss_url;
    let clientVideoUrl = item.preview_url;
    
    const needServerVideo = !serverVideoUrl;
    const needClientVideo = !clientVideoUrl || item.preview_status !== 'completed';
    
    console.log(`[双轨制] 🎬 轨道①检查: ${needServerVideo ? '❌ 需要准备' : '✅ 已存在'}`);
    console.log(`[双轨制] 🌐 轨道②检查: ${needClientVideo ? '❌ 需要准备' : '✅ 已存在'}`);
    
    // 如果任一视频需要准备，显示弹窗并同时准备
    if (needServerVideo || needClientVideo) {
      setProcessingModal({
        isOpen: true,
        title: '视频准备中',
        description: '正在准备文字快剪所需视频，请稍候...',
        showProgress: false,
        progress: 0,
        type: 'kaipai'
      });
      
      setKaipaiLoadingId(item.id);
      
      try {
        // 同时启动两个准备流程
        const preparePromises: Promise<void>[] = [];
        
        // 准备视频①：服务器FFmpeg高质量+OSS
        if (needServerVideo) {
          console.log('[双轨制] 启动轨道①准备：服务器FFmpeg拼接+OSS上传');
          preparePromises.push(
            new Promise<void>(async (resolve, reject) => {
              try {
                const serverResponse = await fetch(
                  `${API_BASE_URL}/api/combinations/${item.id}/server-render`,
                  { method: 'POST', headers: { 'Content-Type': 'application/json' } }
                );
                
                const serverData = await serverResponse.json();
                
                if (serverData.status === 'completed') {
                  serverVideoUrl = serverData.video_url;
                  setResults(prev => prev.map(r =>
                    r.id === item.id ? { ...r, server_video_url: serverData.video_url } : r
                  ));
                  resolve();
                } else if (serverData.status === 'processing' || serverData.status === 'local_ready') {
                  // 轮询等待完成
                  const checkInterval = setInterval(async () => {
                    try {
                      const statusResponse = await fetch(
                        `${API_BASE_URL}/api/combinations/${item.id}/server-render/status`
                      );
                      const statusData = await statusResponse.json();
                      
                      if (statusData.status === 'completed') {
                        clearInterval(checkInterval);
                        serverVideoUrl = statusData.video_url;
                        setResults(prev => prev.map(r =>
                          r.id === item.id ? { ...r, server_video_url: statusData.video_url } : r
                        ));
                        resolve();
                      } else if (statusData.status === 'failed') {
                        clearInterval(checkInterval);
                        reject(new Error(statusData.error || '服务器视频准备失败'));
                      }
                    } catch (e) {
                      console.error('[双轨制] 轮询轨道①失败:', e);
                    }
                  }, 2000);
                } else if (serverData.error) {
                  reject(new Error(serverData.error));
                }
              } catch (error) {
                reject(error);
              }
            })
          );
        }
        
        // 准备视频②：浏览器WebCodecs预览视频
        if (needClientVideo) {
          console.log('[双轨制] 启动轨道②准备：浏览器WebCodecs渲染');
          preparePromises.push(
            new Promise<void>(async (resolve) => {
              if (clientRenderState.isEnabled) {
                console.log('[双轨制] 调用 clientRenderPreview...');
                clientVideoUrl = await clientRenderPreview(item);
                console.log(`[双轨制] clientRenderPreview 返回: ${clientVideoUrl ? '✅ 成功' : '❌ 失败'}`);
              }
              
              // 如果浏览器渲染失败，先不降级，等视频①完成后再降级
              resolve();
            })
          );
        }
        
        // 等待所有准备完成
        await Promise.all(preparePromises);
        
        // 如果视频②仍然为空（浏览器渲染失败），降级使用视频①
        if (!clientVideoUrl && serverVideoUrl) {
          console.log('[双轨制] ⚠️ 轨道②失败，降级使用轨道①作为预览');
          clientVideoUrl = serverVideoUrl;
        }
        
        // 关闭弹窗
        setProcessingModal(prev => ({ ...prev, isOpen: false }));
        
      } catch (error: any) {
        console.error('[双轨制] 视频准备失败:', error);
        setProcessingModal(prev => ({ ...prev, isOpen: false }));
        alert('视频准备失败：' + error.message);
        setKaipaiLoadingId(null);
        return;
      }
      
      setKaipaiLoadingId(null);
    }
    
    // 检查是否都准备好了
    if (!serverVideoUrl) {
      alert('服务器视频准备失败，请重试');
      return;
    }
    
    if (!clientVideoUrl) {
      alert('预览视频准备失败，请重试');
      return;
    }
    
    console.log(`[双轨制] ========== 视频准备完成 ==========`);
    console.log(`[双轨制] 📹 轨道① (ASR/导出): ${serverVideoUrl}`);
    console.log(`[双轨制] 📹 轨道② (预览): ${clientVideoUrl}`);
    
    try {
      console.log(`[双轨制] ========== 创建KaipaiEdit草稿 ==========`);
      
      // 检查serverVideoUrl是否是blob URL（不应该传给ASR）
      if (serverVideoUrl && serverVideoUrl.startsWith('blob:')) {
        console.error(`[双轨制] ❌ 错误: serverVideoUrl是blob URL，不能用于ASR`);
        if (item.oss_url) {
          console.log(`[双轨制] ⚠️ 降级使用oss_url: ${item.oss_url}`);
          serverVideoUrl = item.oss_url;
        } else {
          alert('视频URL格式错误，请重新上传素材');
          return;
        }
      }
      
      // 创建 KaipaiEdit 任务
      const response = await fetch(`${API_BASE_URL}/api/renders/${item.id}/kaipai/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_url: serverVideoUrl,
          needs_transcode: false,
          client_video_url: clientVideoUrl
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '创建剪辑任务失败');
      }
      
      const data = await response.json();
      console.log('[双轨制] KaipaiEdit创建成功:', data);
      
      setKaipaiEditId(data.edit_id);
      setKaipaiVideoUrl(data.video_url);
      setKaipaiClientVideoUrl(clientVideoUrl || data.client_video_url || '');
      setShowKaipaiEditor(true);
    } catch (error: any) {
      alert('创建剪辑任务失败：' + error.message);
      setKaipaiLoadingId(null);
    }
  }, [results, clientRenderState.isEnabled]);

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
        <div className="flex items-center gap-2">
          {/* 客户端渲染状态指示 */}
          {clientRenderState.isEnabled && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-[10px] rounded-full">
              <Cpu size={10} />
              客户端渲染
            </span>
          )}
          <button
            onClick={() => setShowClientRenderPanel(!showClientRenderPanel)}
            className={`p-1.5 rounded-full transition-colors ${clientRenderState.isEnabled ? 'text-green-600 bg-green-50' : 'text-gray-400 hover:text-gray-600'}`}
            title="客户端渲染设置"
          >
            <Cpu size={16} />
          </button>
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              预览生成中 {previewProgress.completed}/{previewProgress.total}
            </span>
          </div>
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
                客户端渲染的视频预览和导出将在浏览器本地完成，速度更快
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-500">检测设备能力...</div>
          )}
        </div>
      )}

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
                          // Video ready - play it (use optimized player with local cache)
                          <OptimizedVideoPlayer
                            itemId={item.id}
                            videoUrl={item.preview_url}
                            isCached={cachedVideos.has(item.id)}
                            apiBaseUrl={API_BASE_URL}
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
          videoUrl={kaipaiVideoUrl}           // 视频①：服务器高质量视频URL（ASR/导出用）
          clientVideoUrl={kaipaiClientVideoUrl} // 视频②：客户端预览视频URL（预览播放用）
          onBack={handleCloseKaipai}
          onSave={handleCloseKaipai}
        />
      )}

      {/* Processing Modal */}
      <ProcessingModal
        isOpen={processingModal.isOpen}
        title={processingModal.title}
        description={processingModal.description}
        showProgress={processingModal.showProgress}
        progress={processingModal.progress}
        type={processingModal.type}
      />
    </div>
  );
}


