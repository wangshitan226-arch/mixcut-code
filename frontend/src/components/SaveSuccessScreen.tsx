import React, { useState, useEffect } from 'react';
import { ChevronLeft, FileText, ArrowRight, CheckCircle2, Image as ImageIcon } from 'lucide-react';
import CoverGenerator from './CoverGenerator';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

interface SaveSuccessScreenProps {
  editId: string;
  videoUrl: string;
  onBack: () => void;
  onGenerateCopy: (data: {
    editId: string;
    videoText: string;
    extractedTitle: string;
    extractedKeywords: string[];
    outputVideoUrl: string;
  }) => void;
}

export default function SaveSuccessScreen({
  editId,
  videoUrl,
  onBack,
  onGenerateCopy
}: SaveSuccessScreenProps) {
  const [showCoverGenerator, setShowCoverGenerator] = useState(false);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState<any>(null);
  const [videoText, setVideoText] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const loadDraft = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kaipai/${editId}`);
        if (!response.ok) {
          throw new Error('获取草稿失败');
        }
        const data = await response.json();
        setDraft(data);

        if (data.asr_result?.sentences) {
          const sentences = data.asr_result.sentences;
          const speechSentences = sentences.filter((s: any) => s.type === 'speech');
          const fullText = speechSentences.map((s: any) => s.text).join('\n');
          setVideoText(fullText);
        }

        setLoading(false);
      } catch (err: any) {
        setError(err.message || '加载失败');
        setLoading(false);
      }
    };

    loadDraft();
  }, [editId]);

  const handleGenerateCopy = () => {
    if (!draft) return;

    const metadata = draft.asr_result?.metadata || {};
    
    onGenerateCopy({
      editId,
      videoText,
      extractedTitle: metadata.title || '',
      extractedKeywords: metadata.keywords || [],
      outputVideoUrl: draft.output_video_url || videoUrl
    });
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-[100] bg-white flex flex-col items-center justify-center">
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 border-2 border-gray-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
          <p className="text-gray-600 text-sm">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-[100] bg-white flex flex-col items-center justify-center p-8">
        <div className="text-red-500 mb-4">出错了</div>
        <p className="text-gray-600 text-center mb-6">{error}</p>
        <button
          onClick={onBack}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg"
        >
          返回
        </button>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button
          onClick={onBack}
          className="p-2 text-gray-700 hover:bg-gray-100 rounded-full"
        >
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900">保存成功</h1>
        <div className="w-10" />
      </header>

      {/* 成功提示 */}
      <div className="bg-white px-4 py-6 flex flex-col items-center">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
          <CheckCircle2 size={32} className="text-green-600" />
        </div>
        <h2 className="text-lg font-bold text-gray-900 mb-1">视频已保存</h2>
        <p className="text-sm text-gray-500">您可以继续生成发布文案</p>
      </div>

      {/* 视频预览 - 居中放大 */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex justify-center mb-4">
          <div className="w-full max-w-[280px] aspect-[9/16] bg-black rounded-2xl overflow-hidden shadow-lg">
            {draft?.output_video_url || videoUrl ? (
              <video
                src={draft?.output_video_url || videoUrl}
                className="w-full h-full object-contain"
                controls
                poster={draft?.output_video_url || videoUrl}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400">
                <span className="text-sm">视频加载中...</span>
              </div>
            )}
          </div>
        </div>

        {/* 文案预览 */}
        {videoText && (
          <div className="bg-white rounded-xl p-4 mb-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-800">视频文案</h3>
              <span className="text-xs text-gray-400">{videoText.length}字</span>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-sm text-gray-600 leading-relaxed">
                {videoText.slice(0, 200)}
                {videoText.length > 200 && '...'}
              </p>
            </div>
          </div>
        )}

        {/* 已提取的信息 */}
        {draft?.asr_result?.metadata?.title && (
          <div className="bg-white rounded-xl p-4">
            <h3 className="text-sm font-medium text-gray-800 mb-3">已提取的信息</h3>
            <div className="space-y-2">
              <div>
                <span className="text-xs text-gray-400">标题</span>
                <p className="text-sm text-gray-800 font-medium">
                  {draft.asr_result.metadata.title}
                </p>
              </div>
              {draft.asr_result.metadata.keywords?.length > 0 && (
                <div>
                  <span className="text-xs text-gray-400">关键词</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {draft.asr_result.metadata.keywords.map((keyword: string, idx: number) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 底部按钮 */}
      <div className="bg-white border-t border-gray-100 p-4 space-y-3">
        <div className="flex gap-3">
          <button
            onClick={() => setShowCoverGenerator(true)}
            className="flex-1 bg-gray-100 text-gray-700 font-medium py-3.5 rounded-lg flex items-center justify-center gap-2"
          >
            <ImageIcon size={18} />
            生成封面
          </button>
          <button
            onClick={handleGenerateCopy}
            className="flex-1 bg-blue-600 text-white font-medium py-3.5 rounded-lg flex items-center justify-center gap-2"
          >
            <FileText size={18} />
            生成发布文案
          </button>
        </div>
      </div>

      {/* 封面生成器 */}
      {showCoverGenerator && (
        <CoverGenerator
          editId={editId}
          videoUrl={videoUrl}
          originalVideoUrl={draft?.original_video_url || videoUrl}
          videoText={videoText}
          extractedTitle={draft?.asr_result?.metadata?.title || ''}
          onBack={() => setShowCoverGenerator(false)}
        />
      )}
    </div>
  );
}
