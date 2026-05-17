import React, { useState, useEffect } from 'react';
import {
  ChevronLeft, ChevronRight, User, Mic, Film, Music,
  Palette, FileText, Sparkles, Upload, Plus, Loader2,
  Volume2, Image, Settings2, Play, Check
} from 'lucide-react';
import { useUser } from '../contexts/UserContext';
import type { VideoType } from './VideoTypeSelectScreen';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

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
    showDigitalHuman: true,
    showVoice: true,
    showMaterial: true,
    showIdentity: true,
    showMusic: true,
    showStyle: true,
    showCopySource: true,
    showTitle: true,
    defaultStyle: '网感白橙',
  },
  digital_human_pure: {
    name: '数字人纯口播视频',
    showDigitalHuman: true,
    showVoice: true,
    showMaterial: false,
    showIdentity: true,
    showMusic: false,
    showStyle: false,
    showCopySource: true,
    showTitle: true,
    defaultStyle: '无包装',
  },
  real_human_cut: {
    name: '真人口播视频智剪',
    showDigitalHuman: false,
    showVoice: false,
    showMaterial: true,
    showIdentity: false,
    showMusic: true,
    showStyle: true,
    showCopySource: false,
    showTitle: true,
    defaultStyle: '网感白橙',
  },
  material_mix: {
    name: '素材混剪神器',
    showDigitalHuman: false,
    showVoice: true,
    showMaterial: true,
    showIdentity: false,
    showMusic: true,
    showStyle: true,
    showCopySource: true,
    showTitle: true,
    defaultStyle: '网感白橙',
  },
  mixcut: {
    name: '智能混剪',
    showDigitalHuman: false,
    showVoice: false,
    showMaterial: true,
    showIdentity: false,
    showMusic: true,
    showStyle: true,
    showCopySource: false,
    showTitle: false,
    defaultStyle: '网感白橙',
  },
};

const COPY_SOURCES = ['随机文案', '频道文案', '使用音频', 'AI生成文案'] as const;
const STYLES = ['网感白橙', '科技蓝', '清新绿', '暗黑金', '无包装'] as const;

interface DigitalHuman {
  id: string;
  title: string;
  avatar_id?: string;
  cover_url?: string;
  status: string;
}

interface VoiceClone {
  id: string;
  title: string;
  clone_voice_id?: string;
  status: string;
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
  const [selectedStyle, setSelectedStyle] = useState<string>(config.defaultStyle);
  const [selectedCopySource, setSelectedCopySource] = useState<string>('随机文案');
  const [title, setTitle] = useState('');
  const [copyText, setCopyText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const [digitalHumans, setDigitalHumans] = useState<DigitalHuman[]>([]);
  const [userVoices, setUserVoices] = useState<VoiceClone[]>([]);

  useEffect(() => {
    if (user?.id) {
      loadDigitalHumans();
      loadVoices();
    }
  }, [user?.id]);

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
      const resp = await fetch(`${API_BASE_URL}/api/users/${user.id}/voice-clones`);
      if (resp.ok) {
        const data = await resp.json();
        setUserVoices((data.voice_clones || []).filter((v: VoiceClone) => v.status === 'ready'));
      }
    } catch (e) { console.error('Load voices error:', e); }
  };

  const allVoices = [
    ...userVoices.map(v => ({ id: v.clone_voice_id || v.id, name: v.title, isCustom: true })),
  ];

  const handleGenerate = () => {
    setIsGenerating(true);
    onGenerate({
      videoType,
      digitalHumanId: selectedDigitalHuman || undefined,
      voiceId: selectedVoice || undefined,
      style: selectedStyle,
      copySource: selectedCopySource,
      title: title || undefined,
      copyText: copyText || undefined,
    });
  };

  if (videoType === 'mixcut') {
    onGoToMixcut();
    return null;
  }

  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      <header className="flex items-center gap-2 px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">{config.name}</h1>
      </header>

      <div className="flex-1 overflow-y-auto pb-32">
        {config.showDigitalHuman && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <User size={16} className="text-purple-500" />
                <span className="text-sm font-semibold text-gray-800">选择数字人</span>
              </div>
              <button
                onClick={onOpenDigitalHuman}
                className="flex items-center gap-1 text-xs text-blue-600 font-medium"
              >
                <Plus size={14} />
                新建数字人
              </button>
            </div>
            <div className="flex gap-3 overflow-x-auto pb-1">
              {digitalHumans.map((dh) => (
                <button
                  key={dh.id}
                  onClick={() => setSelectedDigitalHuman(dh.id)}
                  className={`shrink-0 flex flex-col items-center gap-1.5 transition-all ${
                    selectedDigitalHuman === dh.id ? 'scale-105' : ''
                  }`}
                >
                  <div className={`w-14 h-14 rounded-full overflow-hidden border-2 ${
                    selectedDigitalHuman === dh.id ? 'border-purple-500 shadow-md' : 'border-gray-200'
                  }`}>
                    {dh.cover_url ? (
                      <img src={dh.cover_url} alt={dh.title} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-purple-100 to-indigo-100 flex items-center justify-center">
                        <User size={20} className="text-purple-400" />
                      </div>
                    )}
                  </div>
                  <span className={`text-[10px] font-medium ${
                    selectedDigitalHuman === dh.id ? 'text-purple-600' : 'text-gray-600'
                  }`}>
                    {dh.title}
                  </span>
                </button>
              ))}
              {digitalHumans.length === 0 && (
                <div className="flex items-center justify-center w-full py-4 text-xs text-gray-400">
                  暂无就绪的数字人，请先创建
                </div>
              )}
              <button
                onClick={onOpenDigitalHuman}
                className="shrink-0 flex flex-col items-center gap-1.5"
              >
                <div className="w-14 h-14 rounded-full border-2 border-dashed border-gray-300 flex items-center justify-center">
                  <Plus size={20} className="text-gray-400" />
                </div>
                <span className="text-[10px] text-gray-400 font-medium">新建</span>
              </button>
            </div>
          </div>
        )}

        {config.showVoice && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Mic size={16} className="text-blue-500" />
                <span className="text-sm font-semibold text-gray-800">选择声音</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {allVoices.map((voice) => (
                <button
                  key={voice.id}
                  onClick={() => setSelectedVoice(voice.id)}
                  className={`flex items-center gap-2 p-2.5 rounded-xl border transition-all ${
                    selectedVoice === voice.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-100 bg-gray-50'
                  }`}
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    selectedVoice === voice.id ? 'bg-blue-500' : 'bg-gray-200'
                  }`}>
                    <Volume2 size={14} className={selectedVoice === voice.id ? 'text-white' : 'text-gray-500'} />
                  </div>
                  <div className="flex-1 text-left min-w-0">
                    <span className={`text-xs font-medium block truncate ${
                      selectedVoice === voice.id ? 'text-blue-700' : 'text-gray-700'
                    }`}>
                      {voice.name}
                    </span>
                    {voice.isCustom && (
                      <span className="text-[9px] text-purple-500">我的克隆</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {config.showMaterial && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Film size={16} className="text-orange-500" />
                <span className="text-sm font-semibold text-gray-800">选择素材</span>
              </div>
              <button className="text-xs text-gray-400 font-medium">不使用素材 &gt;</button>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              <button className="shrink-0 w-20 h-28 border-2 border-dashed border-gray-200 rounded-xl flex flex-col items-center justify-center gap-1 bg-gray-50">
                <Upload size={18} className="text-gray-400" />
                <span className="text-[10px] text-gray-400">上传素材</span>
              </button>
            </div>
          </div>
        )}

        {config.showIdentity && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <User size={16} className="text-green-500" />
                <span className="text-sm font-semibold text-gray-800">填写身份</span>
              </div>
              <button className="text-xs text-gray-400 font-medium">无</button>
            </div>
            <input
              type="text"
              placeholder="例如：资深理财师、美食博主、健身教练..."
              className="w-full px-3 py-2.5 text-sm bg-gray-50 rounded-xl border border-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
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
                <div className="w-8 h-8 rounded-full flex items-center justify-center bg-gray-200">
                  <Play size={14} className="text-gray-500 ml-0.5" />
                </div>
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
                <button
                  key={style}
                  onClick={() => setSelectedStyle(style)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    selectedStyle === style
                      ? 'bg-indigo-500 text-white'
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {style}
                </button>
              ))}
            </div>
          </div>
        )}

        {config.showCopySource && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <FileText size={16} className="text-amber-500" />
              <span className="text-sm font-semibold text-gray-800">文案来源</span>
            </div>
            <div className="flex gap-2 mb-3">
              {COPY_SOURCES.map((source) => (
                <button
                  key={source}
                  onClick={() => setSelectedCopySource(source)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    selectedCopySource === source
                      ? 'bg-amber-500 text-white'
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {source}
                </button>
              ))}
            </div>
            <textarea
              value={copyText}
              onChange={(e) => setCopyText(e.target.value)}
              placeholder="请输入或粘贴你的文案..."
              className="w-full px-3 py-2.5 text-sm bg-gray-50 rounded-xl border border-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-24"
            />
          </div>
        )}

        {config.showTitle && (
          <div className="bg-white mx-3 mt-3 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={16} className="text-blue-500" />
              <span className="text-sm font-semibold text-gray-800">输入标题</span>
            </div>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="请输入视频标题..."
              className="w-full px-3 py-2.5 text-sm bg-gray-50 rounded-xl border border-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}
      </div>

      <div className="absolute bottom-16 left-0 right-0 bg-white border-t border-gray-100 p-3 flex items-center gap-2">
        <button className="flex items-center gap-1 px-3 py-2.5 bg-gray-100 text-gray-600 rounded-xl text-xs font-medium">
          <Settings2 size={14} />
          高级设置
        </button>
        <button className="flex items-center gap-1 px-3 py-2.5 bg-gray-100 text-gray-600 rounded-xl text-xs font-medium">
          <Play size={14} />
          试听效果
        </button>
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className="flex-1 bg-gradient-to-r from-blue-500 to-indigo-600 text-white py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-transform disabled:opacity-50"
        >
          {isGenerating ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              生成中...
            </>
          ) : (
            <>
              <Sparkles size={16} />
              生成视频
            </>
          )}
        </button>
      </div>
    </div>
  );
}
