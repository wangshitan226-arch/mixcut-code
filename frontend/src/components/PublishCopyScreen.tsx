import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ChevronLeft,
  Loader2,
  Copy,
  Check,
  ExternalLink
} from 'lucide-react';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

interface PublishCopyScreenProps {
  editId: string;
  videoText: string;
  extractedTitle: string;
  extractedKeywords: string[];
  outputVideoUrl: string;
  onBack: () => void;
}

type Platform = 'xiaohongshu' | 'shipinhao';

export default function PublishCopyScreen({
  editId,
  videoText: initialVideoText,
  extractedTitle,
  extractedKeywords,
  outputVideoUrl,
  onBack
}: PublishCopyScreenProps) {
  const [videoText, setVideoText] = useState(initialVideoText);
  const [platform, setPlatform] = useState<Platform>('xiaohongshu');
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [generatedCopy, setGeneratedCopy] = useState<{
    title: string;
    intro: string;
    hashtags: string[];
    fullText: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const platforms = [
    { id: 'xiaohongshu' as Platform, name: '小红书' },
    { id: 'shipinhao' as Platform, name: '视频号' }
  ];

  // 平台特定的提示词
  const platformPrompts: Record<Platform, { name: string; style: string; titleLimit: string; introLimit: string }> = {
    xiaohongshu: {
      name: '小红书',
      style: '活泼亲切，多用emoji，适合年轻女性用户',
      titleLimit: '20字以内',
      introLimit: '100字以内'
    },
    shipinhao: {
      name: '视频号',
      style: '真诚自然，适合微信生态，注重实用价值',
      titleLimit: '25字以内',
      introLimit: '120字以内'
    }
  };

  const handleGenerate = async () => {
    if (!videoText.trim() || videoText.trim().length < 10) {
      setError('视频文案内容太短');
      return;
    }

    setIsGenerating(true);
    setProgress(0);
    setError('');

    const progressInterval = setInterval(() => {
      setProgress(prev => prev >= 90 ? prev : prev + Math.random() * 15);
    }, 500);

    try {
      const response = await fetch(`${API_BASE_URL}/api/kaipai/${editId}/generate-copy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_text: videoText, platform })
      });

      clearInterval(progressInterval);
      setProgress(100);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '生成失败');
      }

      const data = await response.json();
      
      if (data.success) {
        setGeneratedCopy({
          title: data.title,
          intro: data.intro,
          hashtags: data.hashtags,
          fullText: data.full_text
        });
      }
    } catch (err: any) {
      setError(err.message || '生成失败');
    } finally {
      setTimeout(() => {
        setIsGenerating(false);
        setProgress(0);
      }, 500);
    }
  };

  const handleCopy = async () => {
    if (!generatedCopy) return;
    
    try {
      await navigator.clipboard.writeText(generatedCopy.fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textArea = document.createElement('textarea');
      textArea.value = generatedCopy.fullText;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handlePublish = () => {
    if (!generatedCopy) return;
    
    // 根据平台跳转到对应链接
    if (platform === 'xiaohongshu') {
      // 小红书创作者中心
      window.open('https://creator.xiaohongshu.com/publish/publish', '_blank');
    } else if (platform === 'shipinhao') {
      // 视频号助手
      window.open('https://channels.weixin.qq.com/platform/post/create', '_blank');
    }
  };

  const currentPlatform = platforms.find(p => p.id === platform);

  return (
    <div className="fixed inset-0 z-[100] bg-white flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 text-gray-700 hover:bg-gray-100 rounded-full">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900">一键生成发布文案</h1>
        <div className="w-10" />
      </header>

      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="bg-red-50 text-red-600 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {/* 平台选择 */}
        <div className="px-4 py-4 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-700 mb-3">选择发布平台</h3>
          <div className="flex gap-3">
            {platforms.map(p => (
              <button
                key={p.id}
                onClick={() => {
                  setPlatform(p.id);
                  setGeneratedCopy(null);
                }}
                className={`flex-1 py-3 rounded-lg text-sm font-medium border transition-all ${
                  platform === p.id
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-200'
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        {/* 视频文案输入 */}
        <div className="px-4 py-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-700">视频文案</h3>
            <span className="text-xs text-gray-400">{videoText.length}/4000</span>
          </div>
          <textarea
            value={videoText}
            onChange={(e) => setVideoText(e.target.value)}
            className="w-full h-40 p-4 bg-gray-50 rounded-lg text-sm text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="请输入视频文案..."
            maxLength={4000}
          />
        </div>

        {/* 生成结果 */}
        {generatedCopy && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="px-4 py-4"
          >
            <div className="bg-gray-50 rounded-lg p-4 space-y-4">
              <div>
                <span className="text-xs text-gray-500">标题</span>
                <p className="text-base font-medium text-gray-900 mt-1">{generatedCopy.title}</p>
              </div>
              
              <div>
                <span className="text-xs text-gray-500">简介</span>
                <p className="text-sm text-gray-700 mt-1 leading-relaxed">{generatedCopy.intro}</p>
              </div>
              
              <div>
                <span className="text-xs text-gray-500">话题标签</span>
                <p className="text-sm text-blue-600 mt-1">
                  {generatedCopy.hashtags.map(tag => `#${tag}`).join(' ')}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* 底部按钮 */}
      <div className="bg-white border-t border-gray-100 p-4 space-y-3">
        {isGenerating && (
          <div className="mb-2">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>深度写稿中...</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {!generatedCopy ? (
          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="w-full bg-blue-600 text-white font-medium py-3.5 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isGenerating ? (
              <Loader2 size={18} className="animate-spin" />
            ) : null}
            生成{currentPlatform?.name}文案
          </button>
        ) : (
          <div className="flex gap-3">
            <button
              onClick={handleCopy}
              className="flex-1 bg-gray-100 text-gray-700 font-medium py-3 rounded-lg flex items-center justify-center gap-2"
            >
              {copied ? <Check size={18} className="text-green-600" /> : <Copy size={18} />}
              {copied ? '已复制' : '复制文案'}
            </button>
            <button
              onClick={handlePublish}
              className="flex-1 bg-blue-600 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2"
            >
              <ExternalLink size={18} />
              去{currentPlatform?.name}发布
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
