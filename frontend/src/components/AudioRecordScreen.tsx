import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeft, Mic, Play, Pause, RotateCcw, Check, Volume2, AlertTriangle, Loader2, Upload, Radio, Search } from 'lucide-react';
import { uploadToOSSDirect } from '../utils/ossUpload';
import { useUser } from '../contexts/UserContext';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface AudioRecordScreenProps {
  onBack: () => void;
  onVoiceCreated?: () => void;
}

interface SystemVoice {
  id: string;
  name: string;
  gender: string;
  style: string;
  scenario: string;
}

const CLONE_REF_TEXT = '你好，我是你的专属AI克隆声音。I am your exclusive AI clone voice.';
const RECORDING_TIPS = [
  '请在安静环境中录制，确保周围没有明显噪音',
  '录制时长至少10秒，建议15-20秒效果最佳',
  '用自然、平稳的语气朗读，无需刻意模仿其他声音',
  '尽量保持与平时说话一致的语速和音调',
];

type SaveStage = 'idle' | 'uploading' | 'cloning' | 'done' | 'error';
type InputMode = 'choose' | 'record' | 'upload' | 'system';
type TabType = 'clone' | 'system';

export default function AudioRecordScreen({ onBack, onVoiceCreated }: AudioRecordScreenProps) {
  const { user } = useUser();
  const [showDisclaimer, setShowDisclaimer] = useState(true);
  const [dontShowAgain, setDontShowAgain] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('system');
  const [inputMode, setInputMode] = useState<InputMode>('choose');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [voiceName, setVoiceName] = useState('');
  const [saveStage, setSaveStage] = useState<SaveStage>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState('');

  const [systemVoices, setSystemVoices] = useState<SystemVoice[]>([]);
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [selectedSystemVoice, setSelectedSystemVoice] = useState<SystemVoice | null>(null);
  const [previewingVoiceId, setPreviewingVoiceId] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [voiceSearch, setVoiceSearch] = useState('');
  const [voiceFilter, setVoiceFilter] = useState<string>('all');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const dismissed = localStorage.getItem('audio_disclaimer_dismissed');
    if (dismissed === 'true') setShowDisclaimer(false);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      if (previewAudioRef.current) {
        previewAudioRef.current.pause();
        previewAudioRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (activeTab === 'system') loadSystemVoices();
  }, [activeTab]);

  const loadSystemVoices = async () => {
    setLoadingVoices(true);
    try {
      const resp = await fetch(`${API_BASE_URL}/api/system-voices`);
      if (resp.ok) {
        const data = await resp.json();
        setSystemVoices(data.voices || []);
      }
    } catch (e) {
      console.error('Load system voices error:', e);
    } finally {
      setLoadingVoices(false);
    }
  };

  const previewSystemVoice = async (voice: SystemVoice) => {
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
      previewAudioRef.current = null;
    }
    if (previewingVoiceId === voice.id) {
      setPreviewingVoiceId(null);
      return;
    }

    setPreviewLoading(true);
    setPreviewingVoiceId(voice.id);
    try {
      const resp = await fetch(`${API_BASE_URL}/api/system-voices/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice_id: voice.id }),
      });
      const data = await resp.json();
      if (data.audio_url) {
        const audio = new Audio(data.audio_url);
        previewAudioRef.current = audio;
        audio.onended = () => setPreviewingVoiceId(null);
        audio.play();
      }
    } catch (e) {
      console.error('Preview voice error:', e);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleConfirmDisclaimer = () => {
    if (dontShowAgain) localStorage.setItem('audio_disclaimer_dismissed', 'true');
    setShowDisclaimer(false);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRecorder.start(1000);
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = setInterval(() => { setRecordingTime(prev => prev + 1); }, 1000);
    } catch (err) {
      alert('无法访问麦克风，请检查权限设置');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) { alert('音频文件不能超过50MB'); return; }
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['wav', 'mp3', 'm4a', 'ogg', 'flac', 'aac', 'webm'].includes(ext || '')) {
      alert('请上传 WAV、MP3、M4A 等音频格式文件'); return;
    }
    setAudioBlob(file);
    setAudioUrl(URL.createObjectURL(file));
    setInputMode('upload');
  };

  const handleRetake = () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(null); setAudioUrl(''); setRecordingTime(0);
    setIsPlaying(false); setSaveStage('idle'); setUploadProgress(0);
    setErrorMsg(''); setInputMode('choose');
  };

  const togglePlay = () => {
    if (!audioRef.current) {
      audioRef.current = new Audio(audioUrl);
      audioRef.current.onended = () => setIsPlaying(false);
    }
    if (isPlaying) { audioRef.current.pause(); setIsPlaying(false); }
    else { audioRef.current.play(); setIsPlaying(true); }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSaveClone = async () => {
    if (!voiceName.trim()) { alert('请给声音取个名字'); return; }
    if (!audioBlob || !user?.id) return;
    setSaveStage('uploading'); setErrorMsg('');
    try {
      const ext = audioBlob.type.includes('wav') ? 'wav' : audioBlob.type.includes('mp3') ? 'mp3' : audioBlob.type.includes('webm') ? 'webm' : 'm4a';
      const filename = `voice_${user.id.slice(0, 8)}_${Date.now()}.${ext}`;
      const uploadResult = await uploadToOSSDirect(audioBlob, filename, user.id, (progress) => setUploadProgress(progress));
      if (!uploadResult.success) throw new Error('上传到OSS失败');
      setSaveStage('cloning');
      const response = await fetch(`${API_BASE_URL}/api/voice-clones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, title: voiceName.trim(), audio_url: uploadResult.url, target_model: 'cosyvoice-v2', ref_text: CLONE_REF_TEXT }),
      });
      const responseData = await response.json();
      if (!response.ok) throw new Error(responseData.error || '语音克隆请求失败');
      setSaveStage('done'); onVoiceCreated?.();
    } catch (err: any) { setSaveStage('error'); setErrorMsg(err.message || '保存失败'); }
  };

  const handleSaveSystemVoice = async () => {
    if (!selectedSystemVoice || !user?.id) return;
    const name = voiceName.trim() || selectedSystemVoice.name;
    setSaveStage('cloning'); setErrorMsg('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/voice-clones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          title: name,
          audio_url: '',
          target_model: 'cosyvoice-v2',
          ref_text: '',
          system_voice_id: selectedSystemVoice.id,
          is_system_voice: true,
        }),
      });
      const responseData = await response.json();
      if (!response.ok) throw new Error(responseData.error || '保存失败');
      setSaveStage('done'); onVoiceCreated?.();
    } catch (err: any) { setSaveStage('error'); setErrorMsg(err.message || '保存失败'); }
  };

  const hasRecording = !!audioBlob;
  const isSaving = saveStage === 'uploading' || saveStage === 'cloning';

  const filteredVoices = systemVoices.filter(v => {
    if (voiceFilter !== 'all' && v.gender !== voiceFilter) return false;
    if (voiceSearch && !v.name.includes(voiceSearch) && !v.style.includes(voiceSearch) && !v.scenario.includes(voiceSearch)) return false;
    return true;
  });

  const scenarioGroups = Array.from(new Set(systemVoices.map(v => v.scenario)));

  return (
    <div className="fixed inset-0 z-[100] bg-white flex flex-col">
      <header className="flex items-center gap-2 px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 hover:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">选择声音</h1>
        {hasRecording && saveStage === 'idle' && activeTab === 'clone' && (
          <button onClick={handleRetake} className="ml-auto flex items-center gap-1 text-sm text-blue-600 font-medium px-2 py-1 rounded-lg hover:bg-blue-50 transition-colors">
            <RotateCcw size={14} /> 重新选择
          </button>
        )}
      </header>

      <div className="flex border-b border-gray-100 shrink-0">
        <button
          onClick={() => { setActiveTab('system'); setSaveStage('idle'); }}
          className={`flex-1 py-3 text-sm font-semibold text-center transition-colors relative ${activeTab === 'system' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <div className="flex items-center justify-center gap-1.5"><Radio size={16} /> 系统语音</div>
          {activeTab === 'system' && <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 bg-blue-600 rounded-full" />}
        </button>
        <button
          onClick={() => { setActiveTab('clone'); setSaveStage('idle'); }}
          className={`flex-1 py-3 text-sm font-semibold text-center transition-colors relative ${activeTab === 'clone' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <div className="flex items-center justify-center gap-1.5"><Mic size={16} /> 克隆声音</div>
          {activeTab === 'clone' && <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 bg-blue-600 rounded-full" />}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === 'system' ? (
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="flex-1 relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text" value={voiceSearch} onChange={(e) => setVoiceSearch(e.target.value)}
                  placeholder="搜索语音..." className="w-full pl-9 pr-3 py-2 text-sm bg-gray-50 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-1 shrink-0">
                {['all', 'male', 'female'].map(g => (
                  <button key={g} onClick={() => setVoiceFilter(g)}
                    className={`px-3 py-2 text-xs rounded-lg font-medium transition-colors ${voiceFilter === g ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
                  >{g === 'all' ? '全部' : g === 'male' ? '男声' : '女声'}</button>
                ))}
              </div>
            </div>

            {loadingVoices ? (
              <div className="flex items-center justify-center py-12"><Loader2 size={24} className="animate-spin text-blue-500" /><span className="ml-2 text-sm text-gray-500">加载语音列表...</span></div>
            ) : (
              <div className="space-y-4">
                {scenarioGroups.map(scenario => {
                  const voicesInGroup = filteredVoices.filter(v => v.scenario === scenario);
                  if (voicesInGroup.length === 0) return null;
                  return (
                    <div key={scenario}>
                      <h4 className="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">{scenario}</h4>
                      <div className="space-y-2">
                        {voicesInGroup.map(voice => (
                          <div key={voice.id}
                            onClick={() => setSelectedSystemVoice(voice === selectedSystemVoice ? null : voice)}
                            className={`flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all active:scale-[0.99] ${
                              selectedSystemVoice?.id === voice.id ? 'border-blue-500 bg-blue-50' : 'border-gray-100 bg-white hover:border-gray-200'
                            }`}
                          >
                            <button onClick={(e) => { e.stopPropagation(); previewSystemVoice(voice); }}
                              className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                                previewingVoiceId === voice.id ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                              }`}
                            >
                              {previewLoading && previewingVoiceId === voice.id ? <Loader2 size={16} className="animate-spin" /> :
                               previewingVoiceId === voice.id ? <Pause size={16} /> : <Play size={14} className="ml-0.5" />}
                            </button>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-800">{voice.name}</p>
                              <p className="text-xs text-gray-400">{voice.style} · {voice.gender === 'male' ? '男声' : voice.gender === 'female' ? '女声' : '中性'}</p>
                            </div>
                            {selectedSystemVoice?.id === voice.id && <Check size={18} className="text-blue-600 shrink-0" />}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {selectedSystemVoice && (
              <div className="mt-6 space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-800 mb-2">声音名称（可选）</h3>
                  <input type="text" value={voiceName} onChange={(e) => setVoiceName(e.target.value)}
                    placeholder={selectedSystemVoice.name} disabled={isSaving}
                    className="w-full px-4 py-3 text-sm bg-gray-50 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  />
                </div>
                {saveStage === 'cloning' && (
                  <div className="bg-purple-50 rounded-xl p-4 border border-purple-100">
                    <div className="flex items-center gap-3"><Loader2 size={20} className="animate-spin text-purple-500" /><p className="text-sm font-medium text-purple-700">保存中...</p></div>
                  </div>
                )}
                {saveStage === 'done' && (
                  <div className="bg-green-50 rounded-xl p-4 border border-green-100">
                    <div className="flex items-center gap-3"><Check size={20} className="text-green-500" /><p className="text-sm font-medium text-green-700">系统语音已添加！</p></div>
                  </div>
                )}
                {saveStage === 'error' && (
                  <div className="bg-red-50 rounded-xl p-4 border border-red-100"><p className="text-sm text-red-700">{errorMsg}</p></div>
                )}
                <button onClick={handleSaveSystemVoice} disabled={isSaving || saveStage === 'done'}
                  className="w-full bg-blue-600 text-white py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-transform disabled:opacity-50"
                >
                  {isSaving ? <><Loader2 size={18} className="animate-spin" /> 保存中...</> : saveStage === 'done' ? <><Check size={18} /> 已添加</> : '使用此语音'}
                </button>
                {saveStage === 'done' && <button onClick={onBack} className="w-full bg-gray-100 text-gray-700 py-3 rounded-xl font-medium text-sm">返回</button>}
              </div>
            )}
          </div>
        ) : (
          <div className="p-4">
            {!hasRecording ? (
              <div>
                <div className="bg-gray-50 rounded-2xl p-4 border border-gray-100 mb-6">
                  <h3 className="text-sm font-semibold text-gray-800 mb-2">录音提示</h3>
                  <div className="space-y-2">
                    {RECORDING_TIPS.map((tip, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <span className="text-xs text-blue-600 font-bold mt-0.5">{i + 1}.</span>
                        <p className="text-xs text-gray-500 leading-relaxed">{tip}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <button onClick={() => { setInputMode('upload'); fileInputRef.current?.click(); }}
                    className="w-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white py-4 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-blue-200 active:scale-[0.98] transition-transform"
                  ><Upload size={20} /> 上传音频文件</button>
                  <p className="text-center text-[10px] text-gray-400">支持 WAV、MP3、M4A 格式，建议10秒以上</p>
                  <div className="flex items-center gap-3 my-4"><div className="flex-1 h-px bg-gray-200" /><span className="text-xs text-gray-400">或者</span><div className="flex-1 h-px bg-gray-200" /></div>
                  <div className="flex flex-col items-center">
                    <button onClick={() => { setInputMode('record'); startRecording(); }}
                      className="w-16 h-16 rounded-full flex items-center justify-center transition-all active:scale-95 bg-gray-100 hover:bg-gray-200"
                    ><Mic size={28} className="text-gray-600" /></button>
                    <p className="mt-2 text-xs text-gray-500">浏览器录音</p>
                  </div>
                </div>
                <input ref={fileInputRef} type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.aac" onChange={handleFileSelect} className="hidden" />
              </div>
            ) : isRecording ? (
              <div className="flex flex-col items-center justify-center py-20">
                <button onClick={stopRecording} className="w-20 h-20 rounded-full bg-red-500 shadow-lg shadow-red-200 animate-pulse flex items-center justify-center">
                  <Mic size={36} className="text-white" />
                </button>
                <p className="mt-4 text-red-500 font-medium">录制中 {formatTime(recordingTime)}</p>
                <p className="mt-1 text-xs text-gray-400">点击停止</p>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="bg-gray-50 rounded-2xl p-4 border border-gray-100">
                  <div className="flex items-center gap-3">
                    <button onClick={togglePlay} disabled={isSaving} className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center disabled:opacity-50">
                      {isPlaying ? <Pause size={18} className="text-white" /> : <Play size={18} className="text-white ml-0.5" />}
                    </button>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{inputMode === 'upload' ? '上传的音频' : '录制的音频'}</p>
                      <p className="text-xs text-gray-400">{(audioBlob.size / 1024).toFixed(0)} KB</p>
                    </div>
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-gray-800 mb-2">声音名称</h3>
                  <input type="text" value={voiceName} onChange={(e) => setVoiceName(e.target.value)}
                    placeholder="请给你的声音取个好听的名字" disabled={isSaving}
                    className="w-full px-4 py-3 text-sm bg-gray-50 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  />
                </div>
                {saveStage === 'uploading' && (
                  <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
                    <div className="flex items-center gap-3">
                      <Loader2 size={20} className="animate-spin text-blue-500" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-blue-700">上传音频中...</p>
                        <div className="w-full h-1.5 bg-blue-200 rounded-full mt-2 overflow-hidden">
                          <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${uploadProgress}%` }} />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                {saveStage === 'cloning' && (
                  <div className="bg-purple-50 rounded-xl p-4 border border-purple-100">
                    <div className="flex items-center gap-3"><Loader2 size={20} className="animate-spin text-purple-500" /><div><p className="text-sm font-medium text-purple-700">AI声音克隆中...</p><p className="text-xs text-purple-400 mt-1">预计1-5分钟完成</p></div></div>
                  </div>
                )}
                {saveStage === 'done' && (
                  <div className="bg-green-50 rounded-xl p-4 border border-green-100">
                    <div className="flex items-center gap-3"><Check size={20} className="text-green-500" /><div><p className="text-sm font-medium text-green-700">声音克隆已提交！</p><p className="text-xs text-green-400 mt-1">完成后可在首页"我的声音"中查看</p></div></div>
                  </div>
                )}
                {saveStage === 'error' && (
                  <div className="bg-red-50 rounded-xl p-4 border border-red-100"><p className="text-sm font-medium text-red-700">保存失败</p><p className="text-xs text-red-400 mt-1">{errorMsg}</p></div>
                )}
                <button onClick={handleSaveClone} disabled={isSaving || saveStage === 'done'}
                  className="w-full bg-blue-600 text-white py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-transform disabled:opacity-50"
                >
                  {isSaving ? <><Loader2 size={18} className="animate-spin" />{saveStage === 'uploading' ? '上传中...' : '克隆中...'}</> : saveStage === 'done' ? <><Check size={18} />已提交</> : '保存声音'}
                </button>
                {saveStage === 'done' && <button onClick={onBack} className="w-full bg-gray-100 text-gray-700 py-3 rounded-xl font-medium text-sm">返回首页</button>}
              </div>
            )}
          </div>
        )}
      </div>

      {showDisclaimer && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl p-6 mx-4 max-w-sm w-full">
            <div className="flex items-center justify-center mb-4">
              <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center"><AlertTriangle size={24} className="text-amber-600" /></div>
            </div>
            <h3 className="text-lg font-bold text-gray-900 text-center mb-3">提示</h3>
            <p className="text-sm text-gray-600 text-center leading-relaxed mb-6">
              请确保您录制或上传的音频已经过本人授权，且符合法律法规，不可用于制作诈骗语音、伪造他人发言等违法用途
            </p>
            <button onClick={handleConfirmDisclaimer} className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold text-sm active:scale-[0.98] transition-transform">确定</button>
            <div className="flex items-center justify-center mt-4">
              <button onClick={() => setDontShowAgain(!dontShowAgain)} className="flex items-center gap-2 text-xs text-gray-400">
                <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${dontShowAgain ? 'bg-blue-500 border-blue-500' : 'border-gray-300'}`}>
                  {dontShowAgain && <Check size={10} className="text-white" />}
                </div>
                记住选择，下次不再提示
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
