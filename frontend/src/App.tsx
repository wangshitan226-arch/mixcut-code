/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { 
  Home, Scissors, LayoutGrid
} from 'lucide-react';
import HomeScreen from './components/HomeScreen';
import EditScreen from './components/EditScreen';
import ResultsScreen from './components/ResultsScreen';

const API_BASE_URL = 'http://localhost:3002';

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

export default function App() {
  const [mainTab, setMainTab] = useState<'home' | 'edit' | 'results'>('home');
  const [projectId, setProjectId] = useState<number | null>(null);
  const [shots, setShots] = useState<Shot[]>([]);
  const [combinations, setCombinations] = useState<Combination[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Create or get existing project
  useEffect(() => {
    const initProject = async () => {
      // Check if we have a saved project ID
      const savedProjectId = localStorage.getItem('mixcut_project_id');
      
      if (savedProjectId) {
        // Try to fetch existing project
        try {
          const response = await fetch(`${API_BASE_URL}/api/projects/${savedProjectId}`);
          if (response.ok) {
            const project = await response.json();
            setProjectId(project.id);
            setShots(project.shots);
            return;
          } else {
            // Project not found, clear localStorage
            localStorage.removeItem('mixcut_project_id');
          }
        } catch (e) {
          console.log('Failed to fetch existing project');
          localStorage.removeItem('mixcut_project_id');
        }
      }
      
      // Create new project
      try {
        const response = await fetch(`${API_BASE_URL}/api/projects`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: '我的混剪项目' })
        });
        
        if (response.ok) {
          const project = await response.json();
          setProjectId(project.id);
          localStorage.setItem('mixcut_project_id', project.id.toString());
          
          // Create default shots
          await createDefaultShots(project.id);
        }
      } catch (e) {
        console.error('Failed to create project:', e);
      }
    };
    
    initProject();
  }, []);

  const createDefaultShots = async (pid: number) => {
    const defaultShots = ['镜头1', '镜头2', '镜头3'];
    const newShots: Shot[] = [];
    
    for (const name of defaultShots) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/projects/${pid}/shots`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name })
        });
        
        if (response.ok) {
          const shot = await response.json();
          newShots.push(shot);
        }
      } catch (e) {
        console.error('Failed to create shot:', e);
      }
    }
    
    setShots(newShots);
  };

  // Refresh shots data from backend
  const refreshShots = async () => {
    if (!projectId) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}`);
      if (response.ok) {
        const project = await response.json();
        setShots(project.shots);
      }
    } catch (e) {
      console.error('Failed to refresh shots:', e);
    }
  };

  const [selectedQuality, setSelectedQuality] = useState<'low' | 'medium' | 'high' | 'ultra'>('medium');

  const handleSynthesize = async () => {
    if (!projectId) {
      alert('项目未初始化');
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
      // Generate combinations only (no pre-rendering)
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          limit: 1000 
        })
      });

      if (!response.ok) {
        throw new Error('生成组合失败');
      }

      const data = await response.json();
      setCombinations(data.combinations);
      setMainTab('results');
    } catch (error) {
      console.error('合成失败:', error);
      alert('合成失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddShot = async () => {
    if (!projectId) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/shots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: `镜头${shots.length + 1}` })
      });
      
      if (response.ok) {
        const shot = await response.json();
        setShots([...shots, shot]);
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
      }
    } catch (e) {
      console.error('Failed to delete material:', e);
    }
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
          projectId ? (
            <EditScreen 
              projectId={projectId}
              shots={shots}
              onBack={() => setMainTab('home')} 
              onSynthesize={handleSynthesize}
              onAddShot={handleAddShot}
              onDeleteShot={handleDeleteShot}
              onDeleteMaterial={handleDeleteMaterial}
              onRefresh={refreshShots}
              isLoading={isLoading}
              selectedQuality={selectedQuality}
              onQualityChange={setSelectedQuality}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
              <p className="text-sm">加载中...</p>
            </div>
          )
        )}
        {mainTab === 'results' && (
          <ResultsScreen 
            onBack={() => setMainTab('edit')} 
            combinations={combinations}
            defaultQuality={selectedQuality}
          />
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
      </div>
    </div>
  );
}
