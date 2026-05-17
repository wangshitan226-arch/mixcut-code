import React, { useState, useRef, useEffect } from 'react';
import {
  ChevronLeft, Upload, Mic, Video, CheckCircle2,
  Loader2, AlertCircle, Plus, Trash2, User
} from 'lucide-react';
import { uploadToOSSDirect } from '../utils/ossUpload';
import { useUser } from '../contexts/UserContext';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

interface DigitalHumanItem {
  id: string;
  title: string;
  avatar_id?: string;
  video_url?: string;
  cover_url?: string;
  voice_id?: string;
  voice_name?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

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
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [selectedVoiceName, setSelectedVoiceName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [dhTitle, setDhTitle] = useState('');
  const [createError, setCreateError] = useState('');
  const [userVoices, setUserVoices] = useState<VoiceItem[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (user?.id) {
      loadUserVoices();
    }
  }, [user?.id]);

  const loadUserVoices = async () => {
    if (!user?.id) return;
    try {
      console.log('[DigitalHuman] Loading user voices for:', user.id);
      const resp = await fetch(`${API_BASE_URL}/api/users/${user.id}/voice-clones`);
      if (resp.ok) {
        const data = await resp.json();
        const readyVoices = (data.voice_clones || []).filter((v: VoiceItem) => v.status === 'ready');
        console.log('[DigitalHuman] Loaded voices:', readyVoices.length, 'ready out of', (data.voice_clones || []).length, 'total');
        setUserVoices(readyVoices);
      } else {
        console.error('[DigitalHuman] Load voices error:', resp.status, await resp.text());
      }
    } catch (e) {
      console.error('[DigitalHuman] Load voices error:', e);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !user?.id) return;

    console.log('[DigitalHuman] Selected file:', file.name, 'size:', (file.size / 1024 / 1024).toFixed(2), 'MB');

    if (file.size > 200 * 1024 * 1024) {
      alert('视频文件不能超过200MB');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setCreateError('');

    try {
      const filename = `avatar_${user.id.slice(0, 8)}_${Date.now()}.${file.name.split('.').pop()}`;
      console.log('[DigitalHuman] Uploading to OSS:', filename);
      const result = await uploadToOSSDirect(file, filename, user.id, (progress) => {
        console.log('[DigitalHuman] Upload progress:', progress + '%');
        setUploadProgress(progress);
      });

      if (!result.success) {
        throw new Error('上传失败');
      }

      console.log('[DigitalHuman] OSS upload successful, URL:', result.url);
      setUploadedVideoUrl(result.url);
      setCurrentStep('voice');
    } catch (err: any) {
      console.error('[DigitalHuman] Upload error:', err);
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
    if (!user?.id || !dhTitle.trim()) {
      alert('请输入数字人名称');
      return;
    }

    setIsCreating(true);
    setCreateError('');

    try {
      const requestBody = {
        user_id: user.id,
        title: dhTitle.trim(),
        video_url: uploadedVideoUrl,
        voice_id: selectedVoice,
        voice_name: selectedVoiceName,
      };
      console.log('[DigitalHuman] Creating digital human:', JSON.stringify(requestBody, null, 2));

      const response = await fetch(`${API_BASE_URL}/api/digital-humans`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      console.log('[DigitalHuman] Create response status:', response.status);
      const responseData = await response.json();
      console.log('[DigitalHuman] Create response data:', responseData);

      if (!response.ok) {
        throw new Error(responseData.error || '创建数字人失败');
      }

      console.log('[DigitalHuman] Digital human created successfully!');
      onDigitalHumanCreated?.();
      onBack();
    } catch (err: any) {
      console.error('[DigitalHuman] Create error:', err);
      setCreateError(err.message || '创建失败');
    } finally {
      setIsCreating(false);
    }
  };

  const allVoices = [
    ...userVoices.map(v => ({ id: v.clone_voice_id || v.id, name: v.title, isCustom: true })),
  ];

  return (
    <div className="fixed inset-0 z-[200] bg-white flex flex-col">
      <header className="flex items-center gap-2 px-4 h-14 shrink-0 border-b border-gray-100">
        <button
          onClick={onBack}
          className="p-2 -ml-2 text-gray-700 active:bg-gray-100 rounded-full transition-colors"
        >
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">新建数字人</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-6">
          <div className={`rounded-2xl p-4 border-2 transition-all ${
            currentStep === 'upload' ? 'border-blue-500 bg-blue-50/50' : 'border-gray-100 bg-white'
          }`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                currentStep === 'upload' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                1
              </div>
              <span className="text-sm font-semibold text-gray-800">上传训练视频</span>
              {currentStep !== 'upload' && (
                <CheckCircle2 size={16} className="text-green-500 ml-auto" />
              )}
            </div>

            {currentStep === 'upload' ? (
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="w-full py-8 border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center gap-2 bg-gray-50 hover:bg-gray-100 transition-colors disabled:opacity-50"
                >
                  {isUploading ? (
                    <>
                      <Loader2 size={32} className="animate-spin text-blue-500" />
                      <span className="text-sm text-blue-600 font-medium">上传中 {uploadProgress}%</span>
                      <div className="w-32 h-1.5 bg-gray-200 rounded-full overflow-hidden mt-1">
                        <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${uploadProgress}%` }} />
                      </div>
                    </>
                  ) : (
                    <>
                      <Upload size={32} className="text-gray-400" />
                      <span className="text-sm text-gray-500 font-medium">选择视频文件</span>
                    </>
                  )}
                </button>
                <div className="mt-3 space-y-1">
                  <p className="text-[11px] text-gray-400">• 视频长度5-60秒</p>
                  <p className="text-[11px] text-gray-400">• 建议200MB以内</p>
                  <p className="text-[11px] text-gray-400">• 单人出镜，面部无遮挡</p>
                  <p className="text-[11px] text-gray-400">• 光线充足，背景简洁</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs text-green-600">
                <CheckCircle2 size={14} />
                视频已上传
              </div>
            )}
          </div>

          <div className={`rounded-2xl p-4 border-2 transition-all ${
            currentStep === 'voice' ? 'border-blue-500 bg-blue-50/50' :
            currentStep === 'upload' ? 'border-gray-100 bg-white opacity-50' : 'border-gray-100 bg-white'
          }`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                currentStep === 'voice' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                2
              </div>
              <span className="text-sm font-semibold text-gray-800">选择声音</span>
              {currentStep === 'authorize' && (
                <CheckCircle2 size={16} className="text-green-500 ml-auto" />
              )}
            </div>

            {currentStep === 'voice' ? (
              <div className="space-y-2">
                {allVoices.length === 0 ? (
                  <div className="text-center py-8">
                    <Mic size={32} className="text-gray-300 mx-auto mb-3" />
                    <p className="text-sm text-gray-500 mb-1">暂无可用声音</p>
                    <p className="text-xs text-gray-400">请先在首页"我的声音"中录制并克隆声音</p>
                  </div>
                ) : (
                  <>
                  {allVoices.map((voice) => (
                  <button
                    key={voice.id}
                    onClick={() => handleVoiceSelect(voice.id, voice.name)}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${
                      selectedVoice === voice.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-100 bg-white'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      selectedVoice === voice.id ? 'bg-blue-500' : 'bg-gray-200'
                    }`}>
                      <Mic size={14} className={selectedVoice === voice.id ? 'text-white' : 'text-gray-500'} />
                    </div>
                    <div className="flex-1 text-left">
                      <span className={`text-xs font-medium ${
                        selectedVoice === voice.id ? 'text-blue-700' : 'text-gray-700'
                      }`}>
                        {voice.name}
                      </span>
                      {voice.isCustom && (
                        <span className="text-[10px] text-purple-500 ml-2">我的克隆</span>
                      )}
                    </div>
                    {selectedVoice === voice.id && (
                      <CheckCircle2 size={16} className="text-blue-500" />
                    )}
                  </button>
                ))}
                <button
                  onClick={() => selectedVoice && setCurrentStep('authorize')}
                  disabled={!selectedVoice}
                  className="w-full mt-2 bg-blue-500 text-white py-2.5 rounded-xl text-sm font-medium disabled:opacity-50 disabled:bg-gray-300"
                >
                  下一步
                </button>
                </>
                )}
              </div>
            ) : currentStep === 'authorize' ? (
              <div className="flex items-center gap-2 text-xs text-green-600">
                <CheckCircle2 size={14} />
                声音已选择: {selectedVoiceName}
              </div>
            ) : (
              <p className="text-xs text-gray-400">请先完成上一步</p>
            )}
          </div>

          <div className={`rounded-2xl p-4 border-2 transition-all ${
            currentStep === 'authorize' ? 'border-blue-500 bg-blue-50/50' : 'border-gray-100 bg-white opacity-50'
          }`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                currentStep === 'authorize' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                3
              </div>
              <span className="text-sm font-semibold text-gray-800">命名并创建</span>
            </div>

            {currentStep === 'authorize' ? (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">数字人名称</label>
                  <input
                    type="text"
                    value={dhTitle}
                    onChange={(e) => setDhTitle(e.target.value)}
                    placeholder="给你的数字人取个名字"
                    className="w-full px-4 py-3 text-sm bg-gray-50 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                {createError && (
                  <div className="bg-red-50 rounded-xl p-3 border border-red-100">
                    <p className="text-xs text-red-600">{createError}</p>
                  </div>
                )}

                <button
                  onClick={handleCreate}
                  disabled={isCreating || !dhTitle.trim()}
                  className="w-full bg-gradient-to-r from-purple-500 to-indigo-600 text-white py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-purple-200 active:scale-[0.98] transition-transform disabled:opacity-50"
                >
                  {isCreating ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      创建中...
                    </>
                  ) : (
                    <>
                      <Plus size={18} />
                      创建数字人
                    </>
                  )}
                </button>

                <p className="text-[11px] text-gray-400 text-center">
                  创建后数字人将进入训练状态，预计10-30分钟完成
                </p>
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
