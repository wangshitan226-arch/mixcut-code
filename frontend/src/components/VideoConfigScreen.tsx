import React, { useState, useEffect, useRef } from 'react';
import {
  ChevronLeft, User, Mic, Film, Music,
  Palette, FileText, Sparkles, Upload, Plus, Loader2,
  Volume2, Play, Check, AlertCircle
} from 'lucide-react';
import { useUser } from '../contexts/UserContext';
import type { VideoType } from './VideoTypeSelectScreen';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const VIDEO_TYPE_CONFIG: Record<VideoType, {
  name: string;
  showDigitalHuman: boolean;
  showVoice: boolean;
  showMaterial: boolean;
  showIdentity: boolean;
  showMusic: boolean;
  showStyle: boolean;
  showCopySource: boolean;
  showTitle: boolean;
  defaultStyle: string;
}> = {
  digital_human_mix: {
    name: '数字人口播混剪',
    showDigitalHuman: true, showVoice: true, showMaterial: true,
    showIdentity: true, showMusic: true, showStyle: true,
    showCopySource: true, showTitle: true, defaultStyle: '网感白橙',
  },
  digital_human_pure: {
    name: '数字人纯口播视频',
    showDigitalHuman: true, showVoice: true, showMaterial: false,
    showIdentity: true, showMusic: false, showStyle: false,
    showCopySource: true, showTitle: true, defaultStyle: '无包装',
  },
  real_human_cut: {
    name: '真人口播视频智剪',
    showDigitalHuman: false, showVoice: false, showMaterial: true,
    showIdentity: false, showMusic: true, showStyle: true,
    showCopySource: false, showTitle: true, defaultStyle: '网感白橙',
  },
  material_mix: {
    name: '素材混剪神器',
    showDigitalHuman: false, showVoice: true, showMaterial: true,
    showIdentity: false, showMusic: true, showStyle: true,
    showCopySource: true, showTitle: true, defaultStyle: '网感白橙',
  },
  mixcut: {
    name: '智能混剪',
    showDigitalHuman: false, showVoice: false, showMaterial: true,
    showIdentity: false, showMusic: true, showStyle: true,
    showCopySource: false, showTitle: false, defaultStyle: '网感白橙',
  },
};

const COPY_SOURCES = ['自己写', 'AI生成文案'] as const;
const STYLES = ['网感白橙', '科技蓝', '清新绿', '暗黑金', '无包装'] as const;

interface DigitalHuman {
  id: string; title: string; cover_url?: string; video_url?: string;
  status: string; voice_id?: string; voice_name?: string;
}
interface VoiceItem {
  id: string; name: string; isSystem?: boolean; isCustom?: boolean;
}
interface DhTemplate {
  id: string; name: string; description: string; category: string;
}

interface VideoConfigScreenProps {
  videoType: VideoType;
  onBack: () => void;
  onOpenDigitalHuman: () => void;
  onGenerate: (config: VideoConfig) => void;
  onGoToMixcut: () => void;
}

export interface VideoConfig {
  videoType: VideoType;
  digitalHumanId?: string;
  voiceId?: string;
  templateId?: string;
  materialIds?: string[];
  identity?: string;
  musicId?: string;
  style: string;
  copySource?: string;
  title?: string;
  copyText?: string;
}

export default function VideoConfigScreen({ videoType, onBack, onOpenDigitalHuman, onGenerate, onGoToMixcut }: VideoConfigScreenProps) {
  const { user } = useUser();
  const config = VIDEO_TYPE_CONFIG[videoType];

  const [selectedDigitalHuman, setSelectedDigitalHuman] = useState<string | null>(null);
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [selectedStyle, setSelectedStyle] = useState<string>(config.defaultStyle);
  const [selectedCopySource, setSelectedCopySource] = useState<string>('自己写');
  const [title, setTitle] = useState('');
  const [copyText, setCopyText] = useState('');
  const [identity, setIdentity] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [validationError, setValidationError] = useState('');

  const [digitalHumans, setDigitalHumans] = useState<DigitalHuman[]>([]);
  const [allVoices, setAllVoices] = useState<VoiceItem[]>([]);
  const [dhTemplates, setDhTemplates] = useState<DhTemplate[]>([]);

  const [isGeneratingCopy, setIsGeneratingCopy] = useState(false);
  const [previewingVoiceId, setPreviewingVoiceId] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (user?.id) { loadDigitalHumans(); loadVoices(); }
    if (config.showDigitalHuman) loadDhTemplates();
  }, [user?.id, videoType]);

  const loadDhTemplates = async () => {
    try {
      const category = videoType === 'digital_human_pure' ? 'digital_human_pure' : 'digital_human_mix';
      const resp = await fetch(`${API_BASE_URL}/api/kaipai/templates?category=${category}`);
      if (resp.ok) { const data = await resp.json(); setDhTemplates(data.templates || []); }
    } catch (e) { console.error('Load DH templates error:', e); }
  };

  const loadDigitalHumans = async () => {
    if (!user?.id) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/users/${user.id}/digital-humans`);
      if (resp.ok) {
        const data = await resp.json();
        setDigitalHumans((data.digital_humans || []).filter((dh: DigitalHuman) => dh.status === 'ready'));
      }
    } catch (e) { console.error('Load digital humans error:', e); }
  };

  const loadVoices = async () => {
    if (!user?.id) return;
    try {
      const [cloneResp, systemResp] = await Promise.all([
        fetch(`${API_BASE_URL}/api/users/${user.id}/voice-clones`),
        fetch(`${API_BASE_URL}/api/system-voices`)
      ]);
      const voices: VoiceItem[] = [];
      if (cloneResp.ok) {
        const data = await cloneResp.json();
        for (const v of (data.voice_clones || []).filter((v: any) => v.status === 'ready')) {
          voices.push({ id: v.clone_voice_id || v.id, name: v.title, isCustom: true });
        }
      }
      if (systemResp.ok) {
        const data = await systemResp.json();
        for (const v of (data.voices || [])) {
          voices.push({ id: v.id, name: `${v.name}（${v.style}）`, isSystem: true });
        }
      }
      setAllVoices(voices);
    } catch (e) { console.error('Load voices error:', e); }
  };

  const handlePreviewVoice = async (voice: VoiceItem) => {
    if (previewAudioRef.current) { previewAudioRef.current.pause(); previewAudioRef.current = null; }
    if (previewingVoiceId === voice.id) { setPreviewingVoiceId(null); return; }
    setPreviewLoading(true); setPreviewingVoiceId(voice.id);
    try {
      const resp = await fetch(`${API_BASE_URL}/api/system-voices/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice_id: voice.id }),
      });
      const data = await resp.json();
      if (data.audio_url) {
        const audio = new Audio(data.audio_url);
        previewAudioRef.current = audio;
        audio.onended = () => setPreviewingVoiceId(null);
        audio.play();
      }
    } catch (e) { console.error('Preview voice error:', e); }
    finally { setPreviewLoading(false); }
  };

  const handleAIGenerateCopy = async () => {
    if (!copyText.trim() && !identity.trim()) {
      setValidationError('请先输入身份或主题，AI才能生成文案');
      return;
    }
    setIsGeneratingCopy(true); setValidationError('');
    try {
      const prompt = identity
        ? `你是一位${identity}，请为短视频写一段口播文案，要求：口语化、有感染力、30秒以内能读完。主题：${copyText || '分享专业知识'}`
        : `请为短视频写一段口播文案，要求：口语化、有感染力、30秒以内能读完。主题：${copyText}`;
      const resp = await fetch(`${API_BASE_URL}/api/ai/copy`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: 'persona', input: identity || copyText || '短视频口播' }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.result) { setCopyText(data.result); }
        else if (data.error) { setValidationError(data.error); }
      } else {
        const text = await resp.text();
        try { const d = JSON.parse(text); setValidationError(d.error || 'AI生成失败'); }
        catch { setValidationError('AI生成失败'); }
      }
    } catch (e) { setValidationError('网络错误，请重试'); }
    finally { setIsGeneratingCopy(false); }
  };

  const handleGenerate = () => {
    setValidationError('');
    if (config.showDigitalHuman && !selectedDigitalHuman) {
      setValidationError('请选择数字人'); return;
    }
    if (config.showVoice && !selectedVoice) {
      setValidationError('请选择声音'); return;
    }
    if (config.showCopySource && !copyText.trim()) {
      setValidationError('请输入文案内容'); return;
    }
    setIsGenerating(true);
    onGenerate({
      videoType,
      digitalHumanId: selectedDigitalHuman || undefined,
      voiceId: selectedVoice || undefined,
      templateId: selectedTemplate || undefined,
      style: selectedStyle,
      copySource: selectedCopySource,
      title: title || undefined,
      copyText: copyText || undefined,
      identity: identity || undefined,
    });
  };

  if (videoType === 'mixcut') { onGoToMixcut(); return null; }

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      <header className="flex items-center gap-2 px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">{config.name}</h1>
      </header>

      <div className="flex-1 overflow-y-auto pb-36">
        {config.showDigitalHuman && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <User size={16} className="text-purple-500" />
                <span className="text-sm font-semibold text-gray-800">选择数字人</span>
              </div>
              <button onClick={onOpenDigitalHuman} className="flex items-center gap-1 text-xs text-blue-600 font-medium">
                <Plus size={14} /> 新建数字人
              </button>
            </div>
            <div className="flex gap-3 overflow-x-auto pb-1">
              {digitalHumans.map((dh) => (
                <button key={dh.id} onClick={() => setSelectedDigitalHuman(dh.id)}
                  className={`shrink-0 flex flex-col items-center gap-1.5 transition-all ${selectedDigitalHuman === dh.id ? 'scale-105' : ''}`}>
                  <div className={`w-14 h-14 rounded-full overflow-hidden border-2 ${selectedDigitalHuman === dh.id ? 'border-purple-500 shadow-md' : 'border-gray-200'}`}>
                    {dh.cover_url ? <img src={dh.cover_url} alt={dh.title} className="w-full h-full object-cover" />
                      : <div className="w-full h-full bg-gradient-to-br from-purple-100 to-indigo-100 flex items-center justify-center"><User size={20} className="text-purple-400" /></div>}
                  </div>
                  <span className={`text-[10px] font-medium ${selectedDigitalHuman === dh.id ? 'text-purple-600' : 'text-gray-600'}`}>{dh.title}</span>
                </button>
              ))}
              {digitalHumans.length === 0 && <div className="flex items-center justify-center w-full py-4 text-xs text-gray-400">暂无就绪的数字人，请先创建</div>}
              <button onClick={onOpenDigitalHuman} className="shrink-0 flex flex-col items-center gap-1.5">
                <div className="w-14 h-14 rounded-full border-2 border-dashed border-gray-300 flex items-center justify-center"><Plus size={20} className="text-gray-400" /></div>
                <span className="text-[10px] text-gray-400 font-medium">新建</span>
              </button>
            </div>
          </div>
        )}

        {config.showDigitalHuman && dhTemplates.length > 0 && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Palette size={16} className="text-indigo-500" />
              <span className="text-sm font-semibold text-gray-800">渲染模板</span>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {dhTemplates.map((tpl) => (
                <button key={tpl.id} onClick={() => setSelectedTemplate(tpl.id === selectedTemplate ? null : tpl.id)}
                  className={`shrink-0 w-[80px] rounded-xl border-2 p-2 transition-all ${selectedTemplate === tpl.id ? 'border-indigo-500 bg-indigo-50' : 'border-gray-100 bg-gray-50'}`}>
                  <div className={`w-full h-[60px] rounded-lg mb-1.5 flex items-center justify-center ${selectedTemplate === tpl.id ? 'bg-indigo-100' : 'bg-gray-200'}`}>
                    <Sparkles size={18} className={selectedTemplate === tpl.id ? 'text-indigo-500' : 'text-gray-400'} />
                  </div>
                  <p className={`text-[10px] font-medium text-center truncate ${selectedTemplate === tpl.id ? 'text-indigo-600' : 'text-gray-600'}`}>
                    {tpl.name.replace('数字人口播混剪-', '').replace('数字人纯口播', '纯口播')}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}

        {config.showVoice && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Mic size={16} className="text-blue-500" />
              <span className="text-sm font-semibold text-gray-800">选择声音</span>
            </div>
            {allVoices.length === 0 ? (
              <div className="text-center py-4 text-xs text-gray-400">暂无可用声音，请先添加声音</div>
            ) : (
              <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                {allVoices.map((voice) => (
                  <button key={voice.id} onClick={() => setSelectedVoice(voice.id)}
                    className={`flex items-center gap-2 p-2.5 rounded-xl border transition-all ${selectedVoice === voice.id ? 'border-blue-500 bg-blue-50' : 'border-gray-100 bg-gray-50'}`}>
                    <div onClick={(e) => { e.stopPropagation(); handlePreviewVoice(voice); }}
                      className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${previewingVoiceId === voice.id ? 'bg-blue-500 text-white' : selectedVoice === voice.id ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'}`}>
                      {previewLoading && previewingVoiceId === voice.id ? <Loader2 size={12} className="animate-spin" />
                        : previewingVoiceId === voice.id ? <span className="text-[10px]">⏸</span>
                        : selectedVoice === voice.id ? <Check size={12} /> : <Volume2 size={12} />}
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <span className={`text-[11px] font-medium block truncate ${selectedVoice === voice.id ? 'text-blue-700' : 'text-gray-700'}`}>{voice.name}</span>
                      {voice.isCustom && <span className="text-[9px] text-purple-500">我的克隆</span>}
                      {voice.isSystem && <span className="text-[9px] text-green-500">系统语音</span>}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {config.showIdentity && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <User size={16} className="text-green-500" />
              <span className="text-sm font-semibold text-gray-800">填写身份</span>
            </div>
            <input type="text" value={identity} onChange={(e) => setIdentity(e.target.value)}
              placeholder="例如：资深理财师、美食博主、健身教练..."
              className="w-full px-3 py-2.5 text-sm bg-gray-50 rounded-xl border border-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        )}

        {config.showCopySource && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <FileText size={16} className="text-amber-500" />
              <span className="text-sm font-semibold text-gray-800">文案内容</span>
            </div>
            <div className="flex gap-2 mb-3">
              {COPY_SOURCES.map((source) => (
                <button key={source} onClick={() => setSelectedCopySource(source)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${selectedCopySource === source ? 'bg-amber-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
                  {source}
                </button>
              ))}
            </div>
            <textarea value={copyText} onChange={(e) => setCopyText(e.target.value)}
              placeholder={selectedCopySource === 'AI生成文案' ? '输入主题或关键词，AI将为你生成文案...' : '请输入或粘贴你的文案...'}
              className="w-full px-3 py-2.5 text-sm bg-gray-50 rounded-xl border border-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-28" />
            {selectedCopySource === 'AI生成文案' && (
              <button onClick={handleAIGenerateCopy} disabled={isGeneratingCopy}
                className="mt-2 w-full py-2 bg-gradient-to-r from-amber-400 to-orange-500 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1 disabled:opacity-50">
                {isGeneratingCopy ? <><Loader2 size={14} className="animate-spin" /> AI生成中...</> : <><Sparkles size={14} /> AI生成文案</>}
              </button>
            )}
          </div>
        )}

        {config.showTitle && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={16} className="text-blue-500" />
              <span className="text-sm font-semibold text-gray-800">视频标题</span>
            </div>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="请输入视频标题..."
              className="w-full px-3 py-2.5 text-sm bg-gray-50 rounded-xl border border-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        )}

        {config.showMaterial && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Film size={16} className="text-orange-500" />
              <span className="text-sm font-semibold text-gray-800">选择素材</span>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              <button className="shrink-0 w-20 h-28 border-2 border-dashed border-gray-200 rounded-xl flex flex-col items-center justify-center gap-1 bg-gray-50">
                <Upload size={18} className="text-gray-400" />
                <span className="text-[10px] text-gray-400">上传素材</span>
              </button>
            </div>
          </div>
        )}

        {config.showMusic && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Music size={16} className="text-pink-500" />
              <span className="text-sm font-semibold text-gray-800">选择音乐</span>
            </div>
            <div className="space-y-2">
              <button className="w-full flex items-center gap-3 p-2.5 rounded-xl border border-gray-100 bg-gray-50">
                <div className="w-8 h-8 rounded-full flex items-center justify-center bg-gray-200"><Play size={14} className="text-gray-500 ml-0.5" /></div>
                <span className="text-xs font-medium text-gray-700 flex-1 text-left">不使用音乐</span>
              </button>
            </div>
          </div>
        )}

        {config.showStyle && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Palette size={16} className="text-indigo-500" />
              <span className="text-sm font-semibold text-gray-800">视频风格</span>
            </div>
            <div className="flex gap-2 flex-wrap">
              {STYLES.map((style) => (
                <button key={style} onClick={() => setSelectedStyle(style)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${selectedStyle === style ? 'bg-indigo-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
                  {style}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {validationError && (
        <div className="mx-3 mb-2 bg-red-50 rounded-xl p-3 border border-red-100 flex items-center gap-2">
          <AlertCircle size={14} className="text-red-500 shrink-0" />
          <span className="text-xs text-red-600">{validationError}</span>
        </div>
      )}

      <div className="absolute bottom-16 left-0 right-0 bg-white border-t border-gray-100 p-3">
        <button onClick={handleGenerate} disabled={isGenerating}
          className="w-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-transform disabled:opacity-50">
          {isGenerating ? <><Loader2 size={16} className="animate-spin" /> 生成中...</> : <><Sparkles size={16} /> 生成视频</>}
        </button>
      </div>
    </div>
  );
}
