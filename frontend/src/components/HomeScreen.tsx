import React from 'react';
import { ChevronLeft, Scissors } from 'lucide-react';

interface HomeScreenProps {
  onNavigate: () => void;
}

export default function HomeScreen({ onNavigate }: HomeScreenProps) {
  return (
    <div className="flex flex-col h-full w-full bg-gray-50 p-4">
      <header className="flex items-center justify-center h-14 shrink-0 mb-2">
        {/* Removed "易媒助手" title */}
      </header>
      
      <div className="flex-1 overflow-y-auto">
        <h2 className="text-sm font-semibold text-gray-800 mb-3 px-1">创作工具</h2>
        
        {/* 智能混剪 Card */}
        <div 
          onClick={onNavigate}
          className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl p-5 shadow-lg shadow-blue-200 text-white flex items-center justify-between active:scale-[0.98] transition-transform cursor-pointer"
        >
          <div className="flex items-center gap-4">
            <div className="bg-white/20 p-3 rounded-xl backdrop-blur-sm">
              <Scissors size={28} className="text-white" />
            </div>
            <div>
              <h3 className="text-lg font-bold tracking-wide">智能混剪</h3>
              <p className="text-blue-100 text-xs mt-1">批量生成不重复的高质量视频</p>
            </div>
          </div>
          <ChevronLeft size={24} className="rotate-180 text-white/80" />
        </div>
      </div>
    </div>
  );
}
