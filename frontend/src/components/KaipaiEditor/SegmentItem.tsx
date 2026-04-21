import React, { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, VolumeX, X } from 'lucide-react';
import type { SegmentItemProps, Word } from './types';

const LONG_PRESS_DURATION = 500; // 长按触发时间（毫秒）

export default function SegmentItem({
  segment,
  isSelected,
  onToggle,
  onJump,
  onEdit,
  onToggleExpand,
  onWordEdit,
}: SegmentItemProps) {
  const [editingWord, setEditingWord] = useState<Word | null>(null);
  const [editText, setEditText] = useState('');
  const [isPressing, setIsPressing] = useState(false);
  const pressTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isLongPressRef = useRef(false);

  // 处理长按开始
  const handlePressStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      console.log('[SegmentItem] Press start', segment.id);
      // 阻止默认行为，防止文本选择
      if ('preventDefault' in e) {
        e.preventDefault();
      }
      
      isLongPressRef.current = false;
      setIsPressing(true);

      pressTimerRef.current = setTimeout(() => {
        console.log('[SegmentItem] Long press triggered!', segment.id);
        isLongPressRef.current = true;
        setIsPressing(false);
        onEdit(segment); // 触发编辑
      }, LONG_PRESS_DURATION);
    },
    [segment, onEdit]
  );

  // 处理长按结束
  const handlePressEnd = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      console.log('[SegmentItem] Press end, isLongPress:', isLongPressRef.current);
      // 阻止默认行为
      if ('preventDefault' in e) {
        e.preventDefault();
      }
      
      if (pressTimerRef.current) {
        clearTimeout(pressTimerRef.current);
        pressTimerRef.current = null;
      }
      setIsPressing(false);

      // 如果不是长按，则触发跳转
      if (!isLongPressRef.current) {
        console.log('[SegmentItem] Short press, jumping to', segment.beginTime);
        onJump(segment.beginTime);
      }
    },
    [segment.beginTime, onJump]
  );

  // 处理鼠标离开/移出
  const handlePressLeave = useCallback(() => {
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }
    setIsPressing(false);
  }, []);

  // 处理字编辑
  const handleWordClick = (word: Word, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingWord(word);
    setEditText(word.text);
  };

  const saveWordEdit = () => {
    if (editingWord && editText.trim()) {
      onWordEdit(segment.id, editingWord.beginTime, editText.trim());
    }
    setEditingWord(null);
  };

  const isSilence = segment.type === 'silence';

  return (
    <motion.div
      animate={{
        scale: isPressing ? 0.98 : 1,
        backgroundColor: isPressing ? 'rgba(59, 130, 246, 0.1)' : undefined,
      }}
      transition={{ duration: 0.1 }}
      className={`mb-3 p-3 rounded-xl border-2 transition-all ${
        isSelected
          ? 'border-blue-500 bg-blue-50'
          : isSilence
          ? 'border-gray-300 bg-gray-100'
          : 'border-gray-200 bg-white'
      }`}
    >
      <div className="flex items-start gap-3">
        {/* 选择框 */}
        <div
          onClick={(e) => {
            e.stopPropagation();
            onToggle(segment.id);
          }}
          className={`w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 cursor-pointer transition-all ${
            isSelected
              ? 'bg-blue-600 border-blue-600'
              : isSilence
              ? 'border-gray-400'
              : 'border-gray-300 hover:border-blue-400'
          }`}
        >
          {isSelected && <Check size={14} className="text-white" />}
        </div>

        {/* 内容区域 - 支持长按 */}
        <div
          className="flex-1 select-none cursor-pointer"
          onMouseDown={handlePressStart}
          onMouseUp={handlePressEnd}
          onMouseLeave={handlePressLeave}
          onTouchStart={handlePressStart}
          onTouchEnd={handlePressEnd}
          onTouchCancel={handlePressLeave}
          onContextMenu={(e) => e.preventDefault()}
        >
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`text-xs font-mono px-2 py-0.5 rounded ${
                isSilence
                  ? 'bg-gray-300 text-gray-600'
                  : 'text-gray-400 bg-gray-100'
              }`}
            >
              {segment.time}
            </span>
            {isSilence && (
              <span className="bg-gray-400 text-white text-[10px] px-2 py-0.5 rounded">
                静音
              </span>
            )}
            {!isSilence && segment.hasFiller && (
              <span className="bg-orange-100 text-orange-600 text-[10px] px-2 py-0.5 rounded">
                含语气词
              </span>
            )}
          </div>

          <div
            className={`text-[15px] font-medium ${
              isSelected
                ? 'text-gray-400 line-through'
                : isSilence
                ? 'text-gray-500 italic'
                : 'text-gray-800'
            }`}
          >
            {isSilence && <VolumeX size={16} className="inline mr-1" />}
            {segment.text}
          </div>

          {/* 长按提示 */}
          <div className="mt-1 text-[10px] text-gray-400">
            长按编辑字幕
          </div>

          {!isSilence && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand(segment.id);
              }}
              className="mt-2 text-xs text-blue-500 flex items-center gap-1 hover:text-blue-600"
            >
              {segment.expanded ? '收起' : '编辑字级'}
            </button>
          )}
        </div>
      </div>

      {/* 字级编辑 */}
      {!isSilence && (
        <AnimatePresence>
          {segment.expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-3 pt-3 border-t border-gray-100 overflow-hidden"
            >
              <p className="text-xs text-gray-400 mb-2">
                点击字进行编辑，橙色标记为语气词
              </p>
              <div className="flex flex-wrap gap-1">
                {segment.words?.map((word, idx) => (
                  <React.Fragment key={idx}>
                    {editingWord?.beginTime === word.beginTime ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="text"
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveWordEdit();
                            if (e.key === 'Escape') setEditingWord(null);
                          }}
                          className="w-16 px-1 py-0.5 text-sm border border-blue-500 rounded"
                          autoFocus
                        />
                        <button
                          onClick={saveWordEdit}
                          className="text-green-500"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          onClick={() => setEditingWord(null)}
                          className="text-red-500"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <span
                        onClick={(e) => handleWordClick(word, e)}
                        className={`inline-block px-1 py-0.5 rounded cursor-pointer transition-all text-sm ${
                          word.isFiller
                            ? 'bg-orange-100 text-orange-700'
                            : 'hover:bg-blue-50'
                        }`}
                      >
                        {word.text}
                      </span>
                    )}
                  </React.Fragment>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </motion.div>
  );
}
