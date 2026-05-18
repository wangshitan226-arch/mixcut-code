/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { 
  Home, Scissors, LayoutGrid, User, TrendingUp, Plus, Check, AlertCircle, Loader2
} from 'lucide-react';
import { UserProvider, useUser } from './contexts/UserContext';
import HomeScreen from './components/HomeScreen';
import EditScreen from './components/EditScreen';
import ResultsScreen from './components/ResultsScreen';
import ProfileScreen from './components/ProfileScreen';
import ChannelsScreen from './components/ChannelsScreen';
import KaipaiEditor from './components/KaipaiEditor';
import TestClientRendering from './components/TestClientRendering';
import ASRComparisonTest from './components/ASRComparisonTest';
import VideoTypeSelectScreen from './components/VideoTypeSelectScreen';
import VideoConfigScreen from './components/VideoConfigScreen';
import DigitalHumanScreen from './components/DigitalHumanScreen';
import CoverGenerator from './components/CoverGenerator';
import AICopyScreen from './components/AICopyScreen';
import AudioRecordScreen from './components/AudioRecordScreen';
import type { VideoType } from './components/VideoTypeSelectScreen';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface Material {
  id: string;
  type: 'video' | 'image';
  url: string;
  thumbnail: string;
  duration?: string;
  name: string;
}

interface Shot {
  id: number;
  name: string;
  sequence: number;
  materials: Material[];
}

interface Combination {
  id: string;
  index: number;
  materials: Material[];
  thumbnails: string[];
  duration: string;
  duration_seconds: number;
  tag: string;
}

// Main App Component wrapped with UserProvider
export default function App() {
  return (
    <UserProvider>
      <AppContent />
    </UserProvider>
  );
}

function AppContent() {
  const [mainTab, setMainTab] = useState<'home' | 'edit' | 'results' | 'channels' | 'profile' | 'test' | 'asr-test' | 'video-type-select' | 'video-config' | 'digital-human' | 'ai-copy' | 'audio-record'>('home');
  const { user, isLoading: userLoading, setOnLogoutCallback } = useUser();
  const [shots, setShots] = useState<Shot[]>([]);
  const [combinations, setCombinations] = useState<Combination[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedQuality, setSelectedQuality] = useState<'low' | 'medium' | 'high' | 'ultra'>('medium');
  
  // Kaipai Editor state
  const [showKaipaiEditor, setShowKaipaiEditor] = useState(false);
  const [kaipaiEditId, setKaipaiEditId] = useState<string>('');
  const [kaipaiVideoUrl, setKaipaiVideoUrl] = useState<string>('');

  // Video type & config state
  const [selectedVideoType, setSelectedVideoType] = useState<VideoType>('digital_human_mix');

  // Digital human render state
  const [renderTaskId, setRenderTaskId] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<string>('idle');
  const [renderProgress, setRenderProgress] = useState(0);
  const [renderStage, setRenderStage] = useState('');
  const [renderVideoUrl, setRenderVideoUrl] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [showChannelsModal, setShowChannelsModal] = useState(false);

  // Cover Generator state
  const [showCoverGenerator, setShowCoverGenerator] = useState(false);
  const [coverEditId, setCoverEditId] = useState('');
  const [coverVideoUrl, setCoverVideoUrl] = useState('');
  const [coverOriginalVideoUrl, setCoverOriginalVideoUrl] = useState('');
  const [coverVideoText, setCoverVideoText] = useState('');
  const [coverExtractedTitle, setCoverExtractedTitle] = useState('');

  // Set up logout callback to clear app state
  useEffect(() => {
    setOnLogoutCallback(() => {
      // Clear all user-related state when logging out
      setCombinations([]);
      setShots([]);
      setMainTab('home');
    });

    // Cleanup callback on unmount
    return () => {
      setOnLogoutCallback(undefined);
    };
  }, [setOnLogoutCallback]);

  // Refresh shots data from backend
  const refreshShots = async () => {
    if (!user?.id) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/shots?user_id=${user.id}`);
      if (response.ok) {
        const data = await response.json();
        setShots(data.shots);
      }
    } catch (e) {
      console.error('Failed to refresh shots:', e);
    }
  };

  // Load shots when user is available
  useEffect(() => {
    if (user?.id) {
      refreshShots();
    }
  }, [user?.id]);

  // Load existing renders when entering results tab
  useEffect(() => {
    const loadExistingRenders = async () => {
      if (!user?.id || mainTab !== 'results') return;
      
      try {
        const response = await fetch(`${API_BASE_URL}/api/renders?user_id=${user.id}`);
        if (response.ok) {
          const data = await response.json();
          if (data.combinations && data.combinations.length > 0) {
            setCombinations(data.combinations);
          } else {
            setCombinations([]);
          }
        }
      } catch (e) {
        console.log('Failed to load existing renders:', e);
      }
    };
    
    loadExistingRenders();
  }, [mainTab, user?.id]);

  const handleSynthesize = async () => {
    if (!user?.id) {
      alert('用户未初始化');
      return;
    }

    // Filter out shots without materials
    const validShots = shots.filter(s => (s.materials?.length || 0) > 0);
    
    if (validShots.length === 0) {
      alert('请先为镜头添加素材');
      return;
    }

    setIsLoading(true);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          user_id: user.id,
          limit: 1000 
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        
        // Handle transcoding in progress error
        if (errorData.code === 'TRANSCODING_IN_PROGRESS') {
          const materialNames = errorData.transcoding_materials?.map((m: any) => m.name).join(', ');
          alert(`以下素材正在转码中，请等待转码完成后再生成：\n${materialNames}`);
          return;
        }
        
        throw new Error(errorData.error || '生成组合失败');
      }

      const data = await response.json();
      setCombinations(data.combinations);
      setMainTab('results');
    } catch (error: any) {
      console.error('合成失败:', error);
      alert(error.message || '合成失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddShot = async () => {
    if (!user?.id) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/shots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, name: `镜头${shots.length + 1}` })
      });
      
      if (response.ok) {
        const shot = await response.json();
        setShots([...shots, { ...shot, materials: [] }]);
        // Clear combinations when adding new shot (materials changed)
        setCombinations([]);
      }
    } catch (e) {
      console.error('Failed to add shot:', e);
    }
  };

  const handleDeleteShot = async (shotId: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/shots/${shotId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        setShots(shots.filter(s => s.id !== shotId));
        // Clear combinations when deleting shot (materials changed)
        setCombinations([]);
      }
    } catch (e) {
      console.error('Failed to delete shot:', e);
    }
  };

  const handleDeleteMaterial = async (materialId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/materials/${materialId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        await refreshShots();
        // Clear combinations when deleting material
        setCombinations([]);
      }
    } catch (e) {
      console.error('Failed to delete material:', e);
    }
  };

  // Handle material upload success - clear combinations
  const handleMaterialUploaded = () => {
    // Clear combinations when new material is uploaded
    setCombinations([]);
    refreshShots();
  };

  // Refresh data when entering edit tab
  useEffect(() => {
    if (mainTab === 'edit') {
      refreshShots();
    }
  }, [mainTab]);

  // Listen for openKaipaiEditor event from HomeScreen
  useEffect(() => {
    const handleOpenKaipaiEditor = (e: CustomEvent) => {
      const { editId, videoUrl } = e.detail;
      setKaipaiEditId(editId);
      setKaipaiVideoUrl(videoUrl);
      setShowKaipaiEditor(true);
    };

    window.addEventListener('openKaipaiEditor', handleOpenKaipaiEditor as EventListener);
    return () => {
      window.removeEventListener('openKaipaiEditor', handleOpenKaipaiEditor as EventListener);
    };
  }, []);

  const handleCloseKaipaiEditor = () => {
    setShowKaipaiEditor(false);
    setKaipaiEditId('');
    setKaipaiVideoUrl('');
  };

  // 全局加载状态：UserContext初始化完成前显示加载界面
  if (userLoading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="flex flex-col items-center text-gray-400">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-sm">初始化中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[100dvh] w-full bg-gray-50 overflow-hidden flex flex-col relative">
      {/* Dynamic Content based on Main Tab */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {mainTab === 'home' && <HomeScreen 
          onNavigate={() => setMainTab('edit')} 
          onSelectVideoType={() => setMainTab('video-type-select')}
          onOpenDigitalHuman={() => setMainTab('digital-human')}
          onOpenAICopy={() => setMainTab('ai-copy')}
          onOpenAudioRecord={() => setMainTab('audio-record')}
          onOpenCoverGenerator={(editId, videoUrl, originalVideoUrl, videoText, extractedTitle) => {
            setCoverEditId(editId);
            setCoverVideoUrl(videoUrl);
            setCoverOriginalVideoUrl(originalVideoUrl);
            setCoverVideoText(videoText);
            setCoverExtractedTitle(extractedTitle);
            setShowCoverGenerator(true);
          }}
          userId={user?.id} 
        />}

        {renderStatus !== 'idle' && (
          <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60">
            <div className="bg-white rounded-2xl p-6 mx-4 max-w-sm w-full shadow-2xl">
              {renderStatus === 'completed' ? (
                <div className="text-center">
                  <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                    <Check size={32} className="text-green-500" />
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 mb-2">视频生成完成！</h3>
                  {renderVideoUrl && (
                    <video src={renderVideoUrl.startsWith('http') && !renderVideoUrl.includes('localhost') && !renderVideoUrl.includes('127.0.0.1') ? `${API_BASE_URL}/api/proxy/video?url=${encodeURIComponent(renderVideoUrl)}` : renderVideoUrl} controls className="w-full rounded-xl mb-4 max-h-[300px]" />
                  )}
                  <div className="flex gap-2">
                    <button onClick={() => { setRenderStatus('idle'); setRenderTaskId(null); }}
                      className="flex-1 py-2.5 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium">
                      关闭
                    </button>
                    {renderVideoUrl && (
                      <a href={renderVideoUrl.startsWith('http') && !renderVideoUrl.includes('localhost') && !renderVideoUrl.includes('127.0.0.1') ? `${API_BASE_URL}/api/proxy/video?url=${encodeURIComponent(renderVideoUrl)}` : renderVideoUrl} download className="flex-1 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium text-center">
                        下载视频
                      </a>
                    )}
                  </div>
                </div>
              ) : renderStatus === 'failed' ? (
                <div className="text-center">
                  <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
                    <AlertCircle size={32} className="text-red-500" />
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 mb-2">生成失败</h3>
                  <p className="text-sm text-gray-500 mb-4">{renderError || '未知错误'}</p>
                  <button onClick={() => { setRenderStatus('idle'); setRenderTaskId(null); }}
                    className="w-full py-2.5 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium">
                    关闭
                  </button>
                </div>
              ) : (
                <div className="text-center">
                  <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center mx-auto mb-4">
                    <Loader2 size={36} className="animate-spin text-blue-500" />
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 mb-2">正在生成数字人视频</h3>
                  <p className="text-sm text-gray-500 mb-4">
                    {renderStage === 'synthesizing' ? '语音合成中...' :
                     renderStage === 'videoretalk' ? '生成对口型视频...' :
                     renderStage === 'compositing' ? '合成字幕/音效...' :
                     renderStage === 'ice_rendering' ? '云端渲染中...' :
                     '处理中...'}
                  </p>
                  <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden mb-2">
                    <div className="h-full bg-blue-500 rounded-full transition-all duration-500"
                      style={{ width: `${Math.max(renderProgress, 5)}%` }} />
                  </div>
                  <p className="text-xs text-gray-400">{renderProgress}% · 预计需要2-5分钟</p>
                </div>
              )}
            </div>
          </div>
        )}

        {mainTab === 'edit' && user?.id && (
          <EditScreen 
            userId={user.id}
            shots={shots}
            onBack={() => setMainTab('home')} 
            onSynthesize={handleSynthesize}
            onAddShot={handleAddShot}
            onDeleteShot={handleDeleteShot}
            onDeleteMaterial={handleDeleteMaterial}
            onRefresh={handleMaterialUploaded}
            isLoading={isLoading}
            selectedQuality={selectedQuality}
            onQualityChange={setSelectedQuality}
          />
        )}
        {mainTab === 'edit' && !user?.id && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
            <p className="text-sm">加载中...</p>
          </div>
        )}
        {mainTab === 'results' && (
          <ResultsScreen 
            onBack={() => setMainTab('edit')} 
            combinations={combinations}
            defaultQuality={selectedQuality}
          />
        )}
        {mainTab === 'channels' && user?.id && (
          <ChannelsScreen userId={user.id} onBack={() => setMainTab('results')} />
        )}
        {mainTab === 'profile' && (
          <ProfileScreen onNavigate={(tab) => setMainTab(tab as any)} />
        )}
        {mainTab === 'test' && (
          <TestClientRendering />
        )}
        {mainTab === 'asr-test' && (
          <ASRComparisonTest />
        )}
      </div>

      {/* Kaipai Editor Modal */}
      {showKaipaiEditor && kaipaiEditId && (
        <KaipaiEditor
          editId={kaipaiEditId}
          videoUrl={kaipaiVideoUrl}
          userId={user?.id}
          onBack={handleCloseKaipaiEditor}
          onSave={handleCloseKaipaiEditor}
        />
      )}

      {/* Video Type Select Overlay */}
      {mainTab === 'video-type-select' && (
        <div className="fixed inset-0 z-[100] bg-gray-50">
          <VideoTypeSelectScreen
            onBack={() => setMainTab('home')}
            onSelectType={(type) => {
              if (type === 'mixcut') {
                setMainTab('edit');
              } else {
                setSelectedVideoType(type);
                setMainTab('video-config');
              }
            }}
          />
        </div>
      )}

      {/* Video Config Overlay */}
      {mainTab === 'video-config' && (
        <div className="fixed inset-0 z-[100] bg-gray-50">
          <VideoConfigScreen
            videoType={selectedVideoType}
            onBack={() => setMainTab('video-type-select')}
            onOpenDigitalHuman={() => setMainTab('digital-human')}
            onGenerate={async (config) => {
              console.log('Generating video with config:', config);
              if (config.digitalHumanId && config.copyText) {
                try {
                  setRenderStatus('submitting');
                  setRenderProgress(0);
                  setRenderStage('提交任务...');
                  setRenderError(null);
                  setRenderVideoUrl(null);
                  setMainTab('home');

                  const resp = await fetch(`${API_BASE_URL}/api/digital-human/render`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      user_id: user?.id,
                      digital_human_id: config.digitalHumanId,
                      template_id: config.templateId,
                      text: config.copyText,
                      voice_id: config.voiceId,
                      video_type: selectedVideoType,
                    }),
                  });
                  const data = await resp.json();
                  if (data.success) {
                    const taskId = data.task_id;
                    setRenderTaskId(taskId);
                    setRenderStatus('processing');
                    setRenderStage('语音合成中...');

                    const pollInterval = setInterval(async () => {
                      try {
                        const statusResp = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/status`);
                        if (statusResp.ok) {
                          const statusData = await statusResp.json();
                          setRenderProgress(statusData.progress || 0);
                          setRenderStage(statusData.stage || '');

                          if (statusData.status === 'completed') {
                            clearInterval(pollInterval);
                            setRenderStatus('completed');
                            setRenderVideoUrl(statusData.video_url);
                          } else if (statusData.status === 'failed') {
                            clearInterval(pollInterval);
                            setRenderStatus('failed');
                            setRenderError(statusData.error || '渲染失败');
                          }
                        } else if (statusResp.status === 404) {
                          clearInterval(pollInterval);
                          setRenderStatus('failed');
                          setRenderError('任务不存在或已过期');
                        }
                      } catch (e) {
                        console.error('Poll render status error:', e);
                      }
                    }, 5000);

                    setTimeout(() => {
                      clearInterval(pollInterval);
                      if (renderStatus === 'processing') {
                        setRenderStatus('failed');
                        setRenderError('渲染超时，请稍后在作品列表中查看');
                      }
                    }, 600000);
                  } else {
                    setRenderStatus('failed');
                    setRenderError(data.error || '提交任务失败');
                  }
                } catch (e) {
                  console.error('Digital human render error:', e);
                  setRenderStatus('failed');
                  setRenderError('网络错误');
                }
              }
            }}
            onGoToMixcut={() => setMainTab('edit')}
          />
        </div>
      )}

      {/* Digital Human Overlay */}
      {mainTab === 'digital-human' && (
        <div className="fixed inset-0 z-[100] bg-gray-50">
          <DigitalHumanScreen
            onBack={() => setMainTab('home')}
          />
        </div>
      )}

      {/* AI Copy Overlay */}
      {mainTab === 'ai-copy' && (
        <div className="fixed inset-0 z-[100] bg-gray-50">
          <AICopyScreen
            onBack={() => setMainTab('home')}
          />
        </div>
      )}

      {/* Audio Record Overlay */}
      {mainTab === 'audio-record' && (
        <div className="fixed inset-0 z-[100] bg-gray-50">
          <AudioRecordScreen
            onBack={() => setMainTab('home')}
            onVoiceCreated={() => setMainTab('home')}
          />
        </div>
      )}

      {/* Cover Generator Overlay */}
      {showCoverGenerator && coverEditId && (
        <CoverGenerator
          editId={coverEditId}
          videoUrl={coverVideoUrl}
          originalVideoUrl={coverOriginalVideoUrl}
          videoText={coverVideoText}
          extractedTitle={coverExtractedTitle}
          onBack={() => {
            setShowCoverGenerator(false);
            setCoverEditId('');
            setCoverVideoUrl('');
            setCoverOriginalVideoUrl('');
            setCoverVideoText('');
            setCoverExtractedTitle('');
          }}
        />
      )}

      {/* Bottom Navigation */}
      <div className="bg-white border-t border-gray-200 flex justify-around items-end pb-[env(safe-area-inset-bottom)] px-2 h-16 shrink-0 z-50">
        <button 
          onClick={() => setMainTab('home')}
          className={`flex flex-col items-center justify-center flex-1 h-full space-y-1 ${mainTab === 'home' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <Home size={24} className={mainTab === 'home' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">首页</span>
        </button>
        <button 
          onClick={() => setMainTab('results')}
          className={`flex flex-col items-center justify-center flex-1 h-full space-y-1 ${mainTab === 'results' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <LayoutGrid size={24} className={mainTab === 'results' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">作品</span>
        </button>
        <button 
          onClick={() => setMainTab('video-type-select')}
          className="flex flex-col items-center justify-center flex-1 h-full"
        >
          <div className="w-12 h-12 -mt-6 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-lg shadow-blue-300 border-4 border-white">
            <Plus size={24} className="text-white" />
          </div>
          <span className="text-[10px] font-medium text-blue-600 -mt-0.5">新建</span>
        </button>
        <button 
          onClick={() => {
            setShowChannelsModal(true);
          }}
          className={`flex flex-col items-center justify-center flex-1 h-full space-y-1 ${mainTab === 'channels' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <TrendingUp size={24} className={mainTab === 'channels' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">运营</span>
        </button>
        <button 
          onClick={() => setMainTab('profile')}
          className={`flex flex-col items-center justify-center flex-1 h-full space-y-1 ${mainTab === 'profile' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <User size={24} className={mainTab === 'profile' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">我的</span>
        </button>
      </div>

      {showChannelsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowChannelsModal(false)}>
          <div className="bg-white rounded-2xl p-6 mx-6 max-w-sm w-full shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex flex-col items-center text-center">
              <div className="w-14 h-14 bg-amber-100 rounded-full flex items-center justify-center mb-4">
                <TrendingUp size={28} className="text-amber-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">功能暂未开放</h3>
              <p className="text-sm text-gray-500 mb-6 leading-relaxed">
                视频号运营功能需要本地部署后方可使用。<br />
                请联系管理员获取本地部署方案。
              </p>
              <button
                onClick={() => setShowChannelsModal(false)}
                className="w-full py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                我知道了
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
