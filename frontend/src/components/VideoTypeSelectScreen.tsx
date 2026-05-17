import React from 'react';
import { ChevronLeft, User, Video, Scissors, Sparkles, Zap } from 'lucide-react';

export type VideoType = 
  | 'digital_human_mix' 
  | 'digital_human_pure' 
  | 'real_human_cut' 
  | 'material_mix' 
  | 'mixcut';

interface VideoTypeInfo {
  id: VideoType;
  name: string;
  subtitle: string;
  description: string;
  icon: React.ReactNode;
  gradient: string;
  iconBg: string;
  badge?: string;
  badgeColor?: string;
}

const VIDEO_TYPES: VideoTypeInfo[] = [
  {
    id: 'digital_human_mix',
    name: '数字人口播混剪',
    subtitle: '含数字人',
    description: '数字人+文案+素材智能混剪，自动加字幕/标题/特效',
    icon: <User size={28} />,
    gradient: 'from-purple-500 to-indigo-600',
    iconBg: 'bg-purple-500/20',
    badge: '含数字人',
    badgeColor: 'bg-purple-100 text-purple-700',
  },
  {
    id: 'digital_human_pure',
    name: '数字人纯口播视频',
    subtitle: '含数字人',
    description: '无任何标题字幕包装，适合专业剪辑二次创作',
    icon: <User size={28} />,
    gradient: 'from-violet-500 to-purple-600',
    iconBg: 'bg-violet-500/20',
    badge: '含数字人',
    badgeColor: 'bg-violet-100 text-violet-700',
  },
  {
    id: 'real_human_cut',
    name: '真人口播视频智剪',
    subtitle: 'AI自动剪气口',
    description: '上传真人口播+素材，AI自动剪气口、加包装输出网感口播视频',
    icon: <Video size={28} />,
    gradient: 'from-blue-500 to-cyan-600',
    iconBg: 'bg-blue-500/20',
  },
  {
    id: 'material_mix',
    name: '素材混剪神器',
    subtitle: '文案+配音+素材',
    description: '文案+AI配音+多场景素材混剪，一键生成不重复视频',
    icon: <Scissors size={28} />,
    gradient: 'from-orange-500 to-red-500',
    iconBg: 'bg-orange-500/20',
  },
];

interface VideoTypeSelectScreenProps {
  onBack: () => void;
  onSelectType: (type: VideoType) => void;
}

export default function VideoTypeSelectScreen({ onBack, onSelectType }: VideoTypeSelectScreenProps) {
  return (
    <div className="flex flex-col h-full w-full bg-gray-50">
      <header className="flex items-center gap-2 px-4 h-14 bg-white shrink-0 border-b border-gray-100">
        <button onClick={onBack} className="p-2 -ml-2 text-gray-700 active:bg-gray-100 rounded-full transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 text-base">选择视频类型</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="flex items-center gap-2 mb-2 px-1">
          <Sparkles size={16} className="text-blue-500" />
          <span className="text-sm font-medium text-gray-700">创作4种视频</span>
          <span className="text-xs text-gray-400">选择你需要的视频类型</span>
        </div>

        {VIDEO_TYPES.map((vt) => (
          <button
            key={vt.id}
            onClick={() => onSelectType(vt.id)}
            className="w-full bg-white rounded-2xl p-4 shadow-sm border border-gray-100 flex items-start gap-4 active:scale-[0.98] transition-transform text-left"
          >
            <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${vt.gradient} flex items-center justify-center text-white shrink-0`}>
              {vt.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-gray-900 text-sm">{vt.name}</h3>
                {vt.badge && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${vt.badgeColor}`}>
                    {vt.badge}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">{vt.description}</p>
            </div>
            <ChevronLeft size={20} className="text-gray-300 rotate-180 shrink-0 mt-2" />
          </button>
        ))}

        <div className="mt-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-4 border border-blue-100">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={16} className="text-blue-500" />
            <span className="text-sm font-medium text-blue-700">智能混剪</span>
          </div>
          <p className="text-xs text-blue-600 mb-3">批量生成不重复的高质量视频，适合矩阵号批量发布</p>
          <button
            onClick={() => onSelectType('mixcut')}
            className="w-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white py-2.5 rounded-xl font-medium text-sm active:scale-[0.98] transition-transform"
          >
            进入智能混剪
          </button>
        </div>
      </div>
    </div>
  );
}
