import React from 'react';
import { Loader2, Download, Scissors } from 'lucide-react';

interface ProcessingModalProps {
  isOpen: boolean;
  title: string;
  description?: string;
  showProgress?: boolean;
  progress?: number;
  type: 'download' | 'kaipai';
}

export default function ProcessingModal({
  isOpen,
  title,
  description,
  showProgress = false,
  progress = 0,
  type
}: ProcessingModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl p-8 max-w-sm w-full mx-4 shadow-2xl">
        <div className="flex flex-col items-center text-center">
          {/* Icon */}
          <div className="w-16 h-16 rounded-full bg-blue-50 flex items-center justify-center mb-4">
            {type === 'download' ? (
              <Download size={28} className="text-blue-600" />
            ) : (
              <Scissors size={28} className="text-purple-600" />
            )}
          </div>

          {/* Title */}
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {title}
          </h3>

          {/* Description */}
          {description && (
            <p className="text-sm text-gray-500 mb-6">
              {description}
            </p>
          )}

          {/* Progress Bar */}
          {showProgress && (
            <div className="w-full mb-4">
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ease-out ${
                    type === 'download' ? 'bg-blue-500' : 'bg-purple-500'
                  }`}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                {progress}%
              </p>
            </div>
          )}

          {/* Loading Animation */}
          {!showProgress && (
            <div className="flex items-center gap-2 text-gray-400">
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">请稍候...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
