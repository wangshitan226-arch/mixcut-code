import React, { useState, useRef, useEffect } from 'react';
import {
  ChevronLeft, Upload, Mic, Video, CheckCircle2,
  Loader2, AlertCircle, Plus, Trash2, User, Play, Info, Sparkles
} from 'lucide-react';
import { uploadToOSSDirect } from '../utils/ossUpload';
import { useUser } from '../contexts/UserContext';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface VoiceItem {
  id: string;
  title: string;
  clone_voice_id?: string;
  audio_url?: string;
  status: string;
  created_at: string;
}

interface DigitalHumanScreenProps {
  onBack: () => void;
  onDigitalHumanCreated?: () => void;
}

type Step = 'upload' | 'voice' | 'authorize';

export default function DigitalHumanScreen({ onBack, onDigitalHumanCreated }: DigitalHumanScreenProps) {
  const { user } = useUser();
  const [currentStep, setCurrentStep] = useState<Step>('upload');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedVideoUrl, setUploadedVideoUrl] = useState('');
  const [localVideoUrl, setLocalVideoUrl] = useState('');
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [selectedVoiceName, setSelectedVoiceName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [dhTitle, setDhTitle] = useState('');
  const [createError, setCreateError] = useState('');
  const [userVoices, setUserVoices] = useState<VoiceItem[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (user?.id) loadUserVoices();
    return () => { if (localVideoUrl) URL.revokeObjectURL(localVideoUrl); };
  }, [user?.id]);

  const loadUserVoices = async () => {
    if (!user?.id) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/users/${user.id}/voice-clones`);
      if (resp.ok) {
        const data = await resp.json();
        setUserVoices((data.voice_clones || []).filter((v: VoiceItem) => v.status === 'ready'));
      }
    } catch (e) { console.error('[DigitalHuman] Load voices error:', e); }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !user?.id) return;
    if (file.size > 200 * 1024 * 1024) { alert('视频文件不能超过200MB'); return; }

    if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
    setLocalVideoUrl(URL.createObjectURL(file));

    setIsUploading(true); setUploadProgress(0); setCreateError('');
    try {
      const filename = `avatar_${user.id.slice(0, 8)}_${Date.now()}.${file.name.split('.').pop()}`;
      const result = await uploadToOSSDirect(file, filename, user.id, (progress) => setUploadProgress(progress));
      if (!result.success) throw new Error('上传失败');
      setUploadedVideoUrl(result.url);
    } catch (err: any) {
      setCreateError(err.message || '视频上传失败');
    } finally {
      setIsUploading(false);
    }
  };

  const handleVoiceSelect = (voiceId: string, voiceName: string) => {
    setSelectedVoice(voiceId);
    setSelectedVoiceName(voiceName);
  };

  const handleCreate = async () => {
    if (!user?.id || !dhTitle.trim()) { alert('请输入数字人名称'); return; }
    setIsCreating(true); setCreateError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/digital-humans`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id, title: dhTitle.trim(),
          video_url: uploadedVideoUrl, voice_id: selectedVoice, voice_name: selectedVoiceName,
        }),
      });
      const responseData = await response.json();
      if (!response.ok) throw new Error(responseData.error || '创建数字人失败');
      onDigitalHumanCreated?.(); onBack();
    } catch (err: any) { setCreateError(err.message || '创建失败'); } finally { setIsCreating(false); }
  };

  const allVoices = userVoices.map(v => ({ id: v.clone_voice_id || v.id, name: v.title, isCustom: true }));

  return (
    <div className="fixed inset-0 z-[200] bg-white flex flex-col">
      <header className="flex items-center gap-2 px-4 h-14 shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">新建数字人</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-6">
          {/* Step 1: 上传视频 */}
          <div className={`rounded-2xl p-4 border-2 transition-all ${currentStep === 'upload' ? 'border-blue-500 bg-blue-50/50' : 'border-gray-100 bg-white'}`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${currentStep === 'upload' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'}`}>1</div>
              <span className="text-sm font-semibold text-gray-800">上传模板视频</span>
              {uploadedVideoUrl && currentStep !== 'upload' && <CheckCircle2 size={16} className="text-green-500 ml-auto" />}
            </div>

            {currentStep === 'upload' ? (
              <div>
                <input ref={fileInputRef} type="file" accept="video/*" onChange={handleFileSelect} className="hidden" />

                {localVideoUrl && uploadedVideoUrl ? (
                  <div className="space-y-3">
                    <div className="relative rounded-xl overflow-hidden bg-black aspect-[9/16] max-h-[280px] mx-auto">
                      <video ref={videoRef} src={localVideoUrl} className="w-full h-full object-contain" controls playsInline />
                    </div>
                    <div className="bg-green-50 rounded-xl p-3 border border-green-100">
                      <div className="flex items-center gap-2"><CheckCircle2 size={14} className="text-green-500" /><span className="text-xs font-medium text-green-700">视频已上传成功</span></div>
                      <p className="text-[11px] text-green-600 mt-1">此视频将作为数字人的模板视频，用于生成对口型视频</p>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => { if (localVideoUrl) URL.revokeObjectURL(localVideoUrl); setLocalVideoUrl(''); setUploadedVideoUrl(''); fileInputRef.current?.click(); }}
                        className="flex-1 py-2.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors">
                        重新选择
                      </button>
                      <button onClick={() => setCurrentStep('voice')}
                        className="flex-1 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 transition-colors">
                        下一步
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <button onClick={() => fileInputRef.current?.click()} disabled={isUploading}
                      className="w-full py-8 border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center gap-2 bg-gray-50 hover:bg-gray-100 transition-colors disabled:opacity-50">
                      {isUploading ? (
                        <><Loader2 size={32} className="animate-spin text-blue-500" /><span className="text-sm text-blue-600 font-medium">上传中 {uploadProgress}%</span>
                          <div className="w-32 h-1.5 bg-gray-200 rounded-full overflow-hidden mt-1"><div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${uploadProgress}%` }} /></div></>
                      ) : (
                        <><Upload size={32} className="text-gray-400" /><span className="text-sm text-gray-500 font-medium">选择视频文件</span></>
                      )}
                    </button>
                    <div className="mt-3 bg-blue-50 rounded-xl p-3 border border-blue-100">
                      <div className="flex items-start gap-2"><Info size={14} className="text-blue-500 mt-0.5 shrink-0" /><div>
                        <p className="text-xs font-medium text-blue-700">视频将作为数字人的"模板视频"</p>
                        <p className="text-[11px] text-blue-500 mt-1">生成数字人视频时，系统会保留视频中人物的面部表情和动作，仅替换口型来匹配你的文案语音</p>
                      </div></div>
                    </div>
                    <div className="mt-2 space-y-1">
                      <p className="text-[11px] text-gray-400">• 视频长度5-60秒，人物正面出镜</p>
                      <p className="text-[11px] text-gray-400">• 面部无遮挡，光线充足，背景简洁</p>
                      <p className="text-[11px] text-gray-400">• 建议200MB以内，MP4格式最佳</p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs text-green-600"><CheckCircle2 size={14} />模板视频已上传</div>
            )}
          </div>

          {/* Step 2: 选择声音 */}
          <div className={`rounded-2xl p-4 border-2 transition-all ${currentStep === 'voice' ? 'border-blue-500 bg-blue-50/50' : currentStep === 'upload' ? 'border-gray-100 bg-white opacity-50' : 'border-gray-100 bg-white'}`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${currentStep === 'voice' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'}`}>2</div>
              <span className="text-sm font-semibold text-gray-800">选择声音</span>
              {currentStep === 'authorize' && <CheckCircle2 size={16} className="text-green-500 ml-auto" />}
            </div>

            {currentStep === 'voice' ? (
              <div className="space-y-2">
                {allVoices.length === 0 ? (
                  <div className="text-center py-6">
                    <Mic size={28} className="text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500 mb-1">暂无可用声音</p>
                    <p className="text-xs text-gray-400">请先在首页"我的声音"中添加声音</p>
                  </div>
                ) : (
                  allVoices.map((voice) => (
                    <button key={voice.id} onClick={() => handleVoiceSelect(voice.id, voice.name)}
                      className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${selectedVoice === voice.id ? 'border-blue-500 bg-blue-50' : 'border-gray-100 bg-white'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${selectedVoice === voice.id ? 'bg-blue-500' : 'bg-gray-200'}`}>
                        <Mic size={14} className={selectedVoice === voice.id ? 'text-white' : 'text-gray-500'} />
                      </div>
                      <div className="flex-1 text-left">
                        <span className={`text-xs font-medium ${selectedVoice === voice.id ? 'text-blue-700' : 'text-gray-700'}`}>{voice.name}</span>
                        {voice.isCustom && <span className="text-[10px] text-purple-500 ml-2">我的声音</span>}
                      </div>
                      {selectedVoice === voice.id && <CheckCircle2 size={16} className="text-blue-500" />}
                    </button>
                  ))
                )}
                <div className="flex gap-2 mt-2">
                  <button onClick={() => { setSelectedVoice(null); setSelectedVoiceName(''); setCurrentStep('authorize'); }}
                    className="flex-1 py-2.5 text-sm font-medium text-gray-500 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors">
                    稍后选择
                  </button>
                  <button onClick={() => selectedVoice && setCurrentStep('authorize')} disabled={!selectedVoice}
                    className="flex-1 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:bg-gray-300">
                    下一步
                  </button>
                </div>
              </div>
            ) : currentStep === 'authorize' ? (
              <div className="flex items-center gap-2 text-xs text-green-600">
                <CheckCircle2 size={14} />
                {selectedVoiceName ? `声音: ${selectedVoiceName}` : '稍后选择声音'}
              </div>
            ) : (
              <p className="text-xs text-gray-400">请先完成上一步</p>
            )}
          </div>

          {/* Step 3: 命名并创建 */}
          <div className={`rounded-2xl p-4 border-2 transition-all ${currentStep === 'authorize' ? 'border-blue-500 bg-blue-50/50' : 'border-gray-100 bg-white opacity-50'}`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${currentStep === 'authorize' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'}`}>3</div>
              <span className="text-sm font-semibold text-gray-800">命名并创建</span>
            </div>

            {currentStep === 'authorize' ? (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">数字人名称</label>
                  <input type="text" value={dhTitle} onChange={(e) => setDhTitle(e.target.value)}
                    placeholder="给你的数字人取个名字"
                    className="w-full px-4 py-3 text-sm bg-gray-50 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>

                <div className="bg-purple-50 rounded-xl p-3 border border-purple-100">
                  <div className="flex items-start gap-2"><Sparkles size={14} className="text-purple-500 mt-0.5 shrink-0" /><div>
                    <p className="text-xs font-medium text-purple-700">创建后你可以：</p>
                    <p className="text-[11px] text-purple-500 mt-1">• 在视频创作中选择此数字人，输入文案即可生成对口型视频</p>
                    <p className="text-[11px] text-purple-500">• 在网感模板中选择数字人模板进行渲染</p>
                  </div></div>
                </div>

                {createError && <div className="bg-red-50 rounded-xl p-3 border border-red-100"><p className="text-xs text-red-600">{createError}</p></div>}

                <button onClick={handleCreate} disabled={isCreating || !dhTitle.trim()}
                  className="w-full bg-gradient-to-r from-purple-500 to-indigo-600 text-white py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-purple-200 active:scale-[0.98] transition-transform disabled:opacity-50">
                  {isCreating ? <><Loader2 size={18} className="animate-spin" />创建中...</> : <><Plus size={18} />创建数字人</>}
                </button>
              </div>
            ) : (
              <p className="text-xs text-gray-400">请先完成上一步</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
