import React from 'react';

interface LoadingOverlayProps {
  progress: number;
  title: string;
  subtitle?: string;
  videoUrl?: string;
}

export default function LoadingOverlay({ progress, title, subtitle, videoUrl }: LoadingOverlayProps) {
  return (
    <div className="fixed inset-0 z-[200] bg-black/90 flex flex-col items-center justify-center">
      {/* 手机框预览 */}
      <div className="relative">
        {/* 百分比数字 */}
        <div className="absolute -top-16 left-1/2 -translate-x-1/2 text-white text-5xl font-light">
          {Math.round(progress)}%
        </div>
        
        {/* 手机外框 */}
        <div className="w-[200px] h-[356px] bg-gray-800 rounded-[32px] p-2 shadow-2xl">
          {/* 屏幕区域 */}
          <div className="w-full h-full bg-black rounded-[24px] overflow-hidden">
            {videoUrl ? (
              <video
                src={videoUrl}
                className="w-full h-full object-cover opacity-60"
                muted
                playsInline
              />
            ) : (
              <div className="w-full h-full bg-gray-900" />
            )}
          </div>
        </div>
        
        {/* 底部文字 */}
        <div className="absolute -bottom-20 left-1/2 -translate-x-1/2 text-center">
          <p className="text-white text-lg font-medium mb-2">{title}</p>
          {subtitle && (
            <p className="text-gray-400 text-sm">{subtitle}</p>
          )}
        </div>
      </div>
    </div>
  );
}
