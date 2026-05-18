import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  ChevronLeft,
  Loader2,
  Download,
  Image as ImageIcon,
  RefreshCw,
  Upload
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface CoverGeneratorProps {
  editId: string;
  videoUrl: string;
  originalVideoUrl?: string;  // 原始视频URL（无字幕/贴画，用于截图）
  videoText: string;
  extractedTitle: string;
  onBack: () => void;
}

export default function CoverGenerator({
  editId,
  videoUrl,
  originalVideoUrl,
  videoText,
  extractedTitle,
  onBack
}: CoverGeneratorProps) {
  const [step, setStep] = useState<'frame' | 'generating' | 'result'>('frame');
  const [videoFrame, setVideoFrame] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [subtitle, setSubtitle] = useState('');
  const [description, setDescription] = useState('');
  const [generatedCover, setGeneratedCover] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // 截取视频帧（使用原始视频，无字幕/贴画）
  const captureFrame = async () => {
    // 优先使用原始视频URL（无渲染效果），否则使用渲染后的视频
    const sourceUrl = originalVideoUrl || videoUrl;
    if (!sourceUrl) return;

    console.log('[CoverGenerator] 使用视频源:', originalVideoUrl ? '原始视频（无字幕）' : '渲染后视频');

    const video = document.createElement('video');
    video.src = sourceUrl;
    video.crossOrigin = 'anonymous';

    await new Promise((resolve, reject) => {
      video.onloadedmetadata = () => resolve(null);
      video.onerror = () => reject(new Error('视频加载失败'));
    });

    // 截取第1秒的帧（避免黑屏/片头）
    const captureTime = Math.min(1, video.duration / 3);
    video.currentTime = captureTime;

    await new Promise((resolve, reject) => {
      video.onseeked = () => resolve(null);
      video.onerror = () => reject(new Error('视频跳转失败'));
    });

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx?.drawImage(video, 0, 0);

    const frameDataUrl = canvas.toDataURL('image/jpeg', 0.9);
    setVideoFrame(frameDataUrl);

    // 上传到OSS
    await uploadFrame(frameDataUrl);
  };

  // 上传帧到OSS
  const uploadFrame = async (dataUrl: string) => {
    setIsUploading(true);
    try {
      const response = await fetch(dataUrl);
      const blob = await response.blob();

      const formData = new FormData();
      formData.append('file', blob, 'frame.jpg');

      const uploadResponse = await fetch(`${API_BASE_URL}/api/kaipai/${editId}/upload-frame`, {
        method: 'POST',
        body: formData
      });

      if (!uploadResponse.ok) {
        throw new Error('上传失败');
      }

      const data = await uploadResponse.json();
      if (data.success) {
        // 使用本地变量保存URL，避免React状态异步问题
        const ossUrl = data.url;
        setVideoFrame(ossUrl);
        console.log('[CoverGenerator] 截图上传成功:', ossUrl);
        // 上传成功后自动分析文案生成标题，传入URL避免状态异步问题
        await analyzeVideoText(ossUrl);
      }
    } catch (err: any) {
      setError('上传截图失败: ' + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  // 使用 DeepSeek 生成封面标题（专用API，与发布文案分开）
  const analyzeVideoText = async (frameUrl?: string) => {
    if (!videoText) {
      setError('没有视频文案');
      return;
    }

    // 使用传入的URL或当前状态中的URL
    const currentFrameUrl = frameUrl || videoFrame;
    if (!currentFrameUrl) {
      setError('视频截图未准备好，请重试');
      return;
    }

    setIsAnalyzing(true);
    setError('');

    try {
      // 调用专门的封面标题生成API（不是发布文案API）
      const response = await fetch(`${API_BASE_URL}/api/kaipai/${editId}/generate-cover-title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_text: videoText
        })
      });

      if (!response.ok) {
        throw new Error('生成封面标题失败');
      }

      const data = await response.json();
      if (data.success) {
        const mainTitle = data.title || '';
        const account = extractedTitle || '探店账号';  // 使用ASR提取的标题或默认账号

        setTitle(mainTitle);
        setSubtitle(account ? `@${account}` : '');
        setDescription(mainTitle);  // 描述使用简短标题

        // 自动生成封面
        await generateCoverWithData(mainTitle, account, mainTitle, currentFrameUrl);
      }
    } catch (err: any) {
      setError('生成封面标题失败: ' + err.message);
      setIsAnalyzing(false);
    }
  };

  // 生成封面（使用分析后的数据）
  const generateCoverWithData = async (mainTitle: string, account: string, desc: string, frameUrl?: string) => {
    // 使用传入的URL或当前状态中的URL
    const currentFrameUrl = frameUrl || videoFrame;
    console.log('[CoverGenerator] 生成封面参数:', { videoFrame: !!currentFrameUrl, mainTitle, account, desc });

    if (!currentFrameUrl) {
      setError('缺少视频截图，请重试');
      setIsAnalyzing(false);
      return;
    }

    if (!mainTitle) {
      setError('DeepSeek 未生成标题，请检查视频文案');
      setIsAnalyzing(false);
      return;
    }

    setIsGenerating(true);
    setIsAnalyzing(false);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/kaipai/${editId}/generate-cover-doubao`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_frame_url: currentFrameUrl,
          title: mainTitle,
          subtitle: account ? `@${account}` : `@${mainTitle.slice(0, 10)}`,
          description: desc || mainTitle
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '生成失败');
      }
      
      const data = await response.json();
      if (data.success) {
        setGeneratedCover(data.cover_url);
        setStep('result');
      }
    } catch (err: any) {
      setError(err.message || '生成封面失败');
    } finally {
      setIsGenerating(false);
    }
  };

  // 下载封面
  const downloadCover = async () => {
    if (!generatedCover) return;
    
    try {
      const response = await fetch(generatedCover);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cover_${editId.slice(0, 8)}_${Date.now()}.jpg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      alert('下载失败');
    }
  };

  // 初始截取帧
  useEffect(() => {
    if (videoUrl && step === 'frame') {
      captureFrame();
    }
  }, [videoUrl]);

  return (
    <div className="fixed inset-0 z-[100] bg-white flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 text-gray-700 hover:bg-gray-100 rounded-full">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900">AI生成封面</h1>
        <div className="w-10" />
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="bg-red-50 text-red-600 px-4 py-3 text-sm mb-4 rounded-lg">
            {error}
          </div>
        )}

        {/* 步骤1: 截取视频帧 */}
        {step === 'frame' && (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
              {isUploading ? (
                <Loader2 size={32} className="text-blue-600 animate-spin" />
              ) : (
                <ImageIcon size={32} className="text-blue-600" />
              )}
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {isUploading ? '正在截取视频画面...' : '准备生成封面'}
            </h3>
            <p className="text-sm text-gray-500 text-center">
              正在从视频中截取最佳画面
            </p>
          </div>
        )}

        {/* 步骤2: AI分析中 */}
        {(isAnalyzing || isGenerating) && (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-20 h-20 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {isAnalyzing ? 'AI正在分析视频文案...' : 'AI正在生成封面...'}
            </h3>
            <p className="text-sm text-gray-500 text-center">
              {isAnalyzing ? '正在提取关键信息生成标题' : '正在添加文字和美化效果'}<br />
              大约需要10-30秒
            </p>
            {title && (
              <div className="mt-4 px-4 py-2 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-700">生成标题：{title}</p>
              </div>
            )}
          </div>
        )}

        {/* 步骤3: 生成中 */}
        {step === 'generating' && (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-20 h-20 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">AI正在生成封面...</h3>
            <p className="text-sm text-gray-500 text-center">
              正在添加文字和美化效果<br />
              大约需要10-30秒
            </p>
          </div>
        )}

        {/* 步骤4: 生成结果 */}
        {step === 'result' && generatedCover && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-4"
          >
            <div className="bg-gray-50 rounded-xl p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3 text-center">生成完成</h3>
              <div className="aspect-[9/16] max-w-[280px] mx-auto rounded-xl overflow-hidden shadow-lg bg-black">
                <img src={generatedCover} alt="生成的封面" className="w-full h-full object-cover" />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setStep('info')}
                className="flex-1 bg-gray-100 text-gray-700 font-medium py-3 rounded-lg flex items-center justify-center gap-2"
              >
                <RefreshCw size={18} />
                重新生成
              </button>
              <button
                onClick={downloadCover}
                className="flex-1 bg-blue-600 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2"
              >
                <Download size={18} />
                下载封面
              </button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
