import React, { useState, useEffect, useRef } from 'react';
import { ChevronLeft, FileText, User, PenLine, Languages, MapPin, Users, Store, Loader2, Send, Copy, Check } from 'lucide-react';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

interface AICopyTool {
  id: string;
  name: string;
  desc: string;
  icon: React.ReactNode;
  placeholder: string;
  inputLabel: string;
}

const TOOLS: AICopyTool[] = [
  {
    id: 'extract',
    name: '视频文案提取',
    desc: '复刻爆款视频文案，让你轻松破播10w+',
    icon: <FileText size={24} />,
    placeholder: '粘贴抖音分享链接或视频URL...',
    inputLabel: '视频链接',
  },
  {
    id: 'persona',
    name: '人设文案生成',
    desc: '快速生成IP人设文案，赢得客户信任！',
    icon: <User size={24} />,
    placeholder: '描述你的IP人设、行业、目标受众...',
    inputLabel: '人设描述',
  },
  {
    id: 'rewrite',
    name: '文案改写',
    desc: '智能改写/扩写/缩写',
    icon: <PenLine size={24} />,
    placeholder: '粘贴需要改写的文案...',
    inputLabel: '原始文案',
  },
  {
    id: 'translate',
    name: '翻译',
    desc: '快速精准翻译',
    icon: <Languages size={24} />,
    placeholder: '输入需要翻译的文案...',
    inputLabel: '待翻译文案',
  },
  {
    id: 'local_traffic',
    name: '同城流量',
    desc: '快速获取本地精准流量',
    icon: <MapPin size={24} />,
    placeholder: '描述你的门店/业务和所在城市...',
    inputLabel: '业务描述',
  },
  {
    id: 'franchise',
    name: '招商加盟文案',
    desc: '快速生成爆款招商加盟文案',
    icon: <Users size={24} />,
    placeholder: '描述你的品牌、加盟政策、目标人群...',
    inputLabel: '品牌信息',
  },
  {
    id: 'store',
    name: '门店获客文案',
    desc: '快速生成吸引客户的门店文案',
    icon: <Store size={24} />,
    placeholder: '描述你的门店、产品/服务、目标客户...',
    inputLabel: '门店信息',
  },
];

const STATUS_LABELS: Record<string, string> = {
  pending: '准备中...',
  resolving: '解析链接...',
  downloading: '下载视频...',
  extracting: '提取音频...',
  transcribing: '语音识别中...',
  rewriting: 'AI改写文案中...',
};

interface AICopyScreenProps {
  onBack: () => void;
}

export default function AICopyScreen({ onBack }: AICopyScreenProps) {
  const [selectedTool, setSelectedTool] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [result, setResult] = useState('');
  const [originalText, setOriginalText] = useState('');
  const [rewrittenText, setRewrittenText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [extractStatus, setExtractStatus] = useState('');
  const [extractProgress, setExtractProgress] = useState('');
  const [copied, setCopied] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const tool = TOOLS.find(t => t.id === selectedTool);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleExtractCopy = async () => {
    if (!inputText.trim()) return;
    setIsLoading(true);
    setOriginalText('');
    setRewrittenText('');
    setExtractStatus('pending');
    setExtractProgress('准备中...');

    try {
      const response = await fetch(`${API_BASE_URL}/api/ai/extract-copy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: inputText }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || '提交失败');
      }

      const data = await response.json();
      const taskId = data.task_id;

      pollRef.current = setInterval(async () => {
        try {
          const statusResp = await fetch(`${API_BASE_URL}/api/ai/extract-copy/${taskId}/status`);
          const statusData = await statusResp.json();

          setExtractStatus(statusData.status);
          setExtractProgress(statusData.progress || STATUS_LABELS[statusData.status] || '');

          if (statusData.status === 'completed') {
            if (pollRef.current) clearInterval(pollRef.current);
            setOriginalText(statusData.original_text || '');
            setRewrittenText(statusData.rewritten_text || '');
            setIsLoading(false);
          } else if (statusData.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            setOriginalText('');
            setRewrittenText('');
            setIsLoading(false);
            alert(statusData.error || '提取失败');
          }
        } catch {
          if (pollRef.current) clearInterval(pollRef.current);
          setIsLoading(false);
          alert('查询状态失败');
        }
      }, 2000);
    } catch (err: any) {
      setIsLoading(false);
      alert(err.message || '提交失败');
    }
  };

  const handleGenerate = async () => {
    if (!inputText.trim()) return;
    setIsLoading(true);
    setResult('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/ai/copy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: selectedTool, input: inputText }),
      });

      if (!response.ok) throw new Error('生成失败');
      const data = await response.json();
      setResult(data.result || '暂无结果');
    } catch (err: any) {
      setResult('生成失败: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleBack = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setSelectedTool(null);
    setInputText('');
    setResult('');
    setOriginalText('');
    setRewrittenText('');
    setIsLoading(false);
    setExtractStatus('');
    setExtractProgress('');
  };

  if (selectedTool && tool) {
    const isExtract = selectedTool === 'extract';

    return (
      <div className="fixed inset-0 z-[100] bg-white flex flex-col">
        <header className="flex items-center gap-2 px-4 h-14 bg-white shrink-0 border-b border-gray-100">
          <button onClick={handleBack} className="p-2 -ml-2 text-gray-700 hover:bg-gray-100 rounded-full transition-colors">
            <ChevronLeft size={24} />
          </button>
          <h1 className="font-semibold text-gray-900 text-base">{tool.name}</h1>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-4">
            <label className="text-sm font-medium text-gray-700 mb-2 block">{tool.inputLabel}</label>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={tool.placeholder}
              className="w-full px-4 py-3 text-sm bg-gray-50 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none h-28"
            />
          </div>

          <button
            onClick={isExtract ? handleExtractCopy : handleGenerate}
            disabled={isLoading || !inputText.trim()}
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-transform disabled:opacity-50 disabled:bg-gray-300"
          >
            {isLoading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                {isExtract ? (extractProgress || '处理中...') : '生成中...'}
              </>
            ) : (
              <>
                <Send size={16} />
                {isExtract ? '提取文案' : '生成文案'}
              </>
            )}
          </button>

          {isExtract && (originalText || rewrittenText) && (
            <div className="mt-6 space-y-4">
              {originalText && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">原视频文案</span>
                    <button
                      onClick={() => handleCopy(originalText, 'original')}
                      className="flex items-center gap-1 text-xs text-blue-600 font-medium px-2 py-1 rounded-lg hover:bg-blue-50 transition-colors"
                    >
                      {copied === 'original' ? <Check size={14} /> : <Copy size={14} />}
                      {copied === 'original' ? '已复制' : '复制'}
                    </button>
                  </div>
                  <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                    <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{originalText}</p>
                  </div>
                </div>
              )}
              {rewrittenText && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-blue-600">AI改写文案</span>
                    <button
                      onClick={() => handleCopy(rewrittenText, 'rewritten')}
                      className="flex items-center gap-1 text-xs text-blue-600 font-medium px-2 py-1 rounded-lg hover:bg-blue-50 transition-colors"
                    >
                      {copied === 'rewritten' ? <Check size={14} /> : <Copy size={14} />}
                      {copied === 'rewritten' ? '已复制' : '复制'}
                    </button>
                  </div>
                  <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
                    <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{rewrittenText}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {!isExtract && result && (
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">生成结果</span>
                <button
                  onClick={() => handleCopy(result, 'result')}
                  className="flex items-center gap-1 text-xs text-blue-600 font-medium px-2 py-1 rounded-lg hover:bg-blue-50 transition-colors"
                >
                  {copied === 'result' ? <Check size={14} /> : <Copy size={14} />}
                  {copied === 'result' ? '已复制' : '复制'}
                </button>
              </div>
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{result}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] bg-gray-50 flex flex-col">
      <header className="flex items-center gap-2 px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 hover:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">AI文案</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-3">
          {TOOLS.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedTool(t.id)}
              className="w-full bg-white rounded-2xl p-4 border border-gray-100 flex items-center gap-4 active:scale-[0.98] transition-transform text-left hover:border-blue-200"
            >
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
                {t.icon}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-bold text-gray-900 text-sm">{t.name}</h3>
                <p className="text-xs text-gray-400 mt-1">{t.desc}</p>
              </div>
              <ChevronLeft size={20} className="text-gray-300 rotate-180 shrink-0" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
