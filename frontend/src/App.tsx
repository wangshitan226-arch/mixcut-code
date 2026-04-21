/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { 
  Home, Scissors, LayoutGrid, User
} from 'lucide-react';
import { UserProvider, useUser } from './contexts/UserContext';
import HomeScreen from './components/HomeScreen';
import EditScreen from './components/EditScreen';
import ResultsScreen from './components/ResultsScreen';
import ProfileScreen from './components/ProfileScreen';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3002';

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
  const [mainTab, setMainTab] = useState<'home' | 'edit' | 'results' | 'profile'>('home');
  const { user, isLoading: userLoading, setOnLogoutCallback } = useUser();
  const [shots, setShots] = useState<Shot[]>([]);
  const [combinations, setCombinations] = useState<Combination[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedQuality, setSelectedQuality] = useState<'low' | 'medium' | 'high' | 'ultra'>('medium');

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

  return (
    <div className="h-[100dvh] w-full bg-gray-50 overflow-hidden flex flex-col relative">
      {/* Dynamic Content based on Main Tab */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {mainTab === 'home' && <HomeScreen onNavigate={() => setMainTab('edit')} />}
        {mainTab === 'edit' && (
          <EditScreen 
            userId={user!.id}
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
        {mainTab === 'results' && (
          <ResultsScreen 
            onBack={() => setMainTab('edit')} 
            combinations={combinations}
            defaultQuality={selectedQuality}
          />
        )}
        {mainTab === 'profile' && (
          <ProfileScreen onNavigate={(tab) => setMainTab(tab as any)} />
        )}
      </div>

      {/* Bottom Navigation */}
      <div className="bg-white border-t border-gray-200 flex justify-around items-center pb-[env(safe-area-inset-bottom)] pt-2 px-2 h-16 shrink-0 z-50">
        <button 
          onClick={() => setMainTab('home')}
          className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${mainTab === 'home' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <Home size={24} className={mainTab === 'home' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">首页</span>
        </button>
        <button 
          onClick={() => setMainTab('edit')}
          className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${mainTab === 'edit' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <Scissors size={24} className={mainTab === 'edit' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">智能剪辑</span>
        </button>
        <button 
          onClick={() => setMainTab('results')}
          className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${mainTab === 'results' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <LayoutGrid size={24} className={mainTab === 'results' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">作品结果</span>
        </button>
        <button 
          onClick={() => setMainTab('profile')}
          className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${mainTab === 'profile' ? 'text-blue-600' : 'text-gray-400'}`}
        >
          <User size={24} className={mainTab === 'profile' ? 'fill-blue-100' : ''} />
          <span className="text-[10px] font-medium">我的</span>
        </button>
      </div>
    </div>
  );
}
