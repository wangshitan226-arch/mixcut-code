import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Check } from 'lucide-react';
import type { EditModalProps } from './types';

export default function EditModal({
  isOpen,
  segment,
  onClose,
  onSave,
}: EditModalProps) {
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isOpen && segment) {
      setText(segment.text);
      // 自动聚焦输入框
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, segment]);

  const handleSave = () => {
    if (segment && text.trim()) {
      onSave(segment.id, text.trim());
    }
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!segment) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* 遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 z-[200]"
          />

          {/* 弹窗 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[90%] max-w-md bg-white rounded-2xl shadow-2xl z-[201] overflow-hidden"
          >
            {/* 头部 */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h3 className="font-semibold text-gray-800">编辑字幕</h3>
              <button
                onClick={onClose}
                className="p-1 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X size={20} className="text-gray-500" />
              </button>
            </div>

            {/* 内容 */}
            <div className="p-4">
              {/* 时间信息 */}
              <div className="flex items-center gap-2 mb-3 text-sm text-gray-500">
                <span className="bg-gray-100 px-2 py-1 rounded font-mono">
                  {segment.time}
                </span>
                <span>•</span>
                <span>{((segment.endTime - segment.beginTime) / 1000).toFixed(1)}秒</span>
              </div>

              {/* 编辑框 */}
              <textarea
                ref={inputRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入字幕内容..."
                className="w-full px-3 py-2 border border-gray-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-800"
                rows={3}
              />

              {/* 提示 */}
              <p className="mt-2 text-xs text-gray-400">
                按 Enter 保存，按 Esc 取消
              </p>
            </div>

            {/* 底部按钮 */}
            <div className="flex gap-2 px-4 pb-4">
              <button
                onClick={onClose}
                className="flex-1 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-medium hover:bg-gray-200 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={!text.trim()}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-1"
              >
                <Check size={18} />
                保存
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
