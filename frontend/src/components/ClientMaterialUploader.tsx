/**
 * 客户端素材上传组件
 * 集成客户端渲染流程：本地转码 + 上传元数据
 */

import React, { useState, useRef, useCallback } from 'react';
import { Upload, Loader2, CheckCircle, AlertTriangle } from 'lucide-react';
import { processMaterial, ProcessedMaterial } from '../utils/clientMaterialProcessor';
import { isFastTranscodeSupported } from '../utils/webcodecsTranscoder';

interface ClientMaterialUploaderProps {
  userId: string;
  shotId: number;
  onUploadComplete: (material: any) => void;
  onError: (error: string) => void;
}

export default function ClientMaterialUploader({
  userId,
  shotId,
  onUploadComplete,
  onError,
}: ClientMaterialUploaderProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    if (!file.type.startsWith('video/')) {
      onError('请上传视频文件');
      return;
    }

    setIsProcessing(true);
    setProgress(0);
    setStage('准备处理...');

    try {
      // 1. 本地转码
      setStage('正在转码...');
      const processed = await processMaterial(file, {
        quality: 'medium',
        generateThumbnail: true,
        onProgress: (progress, stage) => {
          setProgress(Math.round(progress));
          setStage(stage === 'fast_transcoding' ? '快速转码...' : 
                   stage === 'transcoding' ? '转码中...' : 
                   stage === 'remuxing' ? '封装中...' : '处理中...');
        },
      });

      // 2. 上传到服务器（只上传元数据和缩略图，视频保留在本地）
      setStage('上传元数据...');
      setProgress(90);

      const formData = new FormData();
      formData.append('user_id', userId);
      formData.append('shot_id', shotId.toString());
      formData.append('material_id', processed.id);
      formData.append('duration', processed.duration.toString());
      formData.append('width', processed.width.toString());
      formData.append('height', processed.height.toString());
      formData.append('file_size', processed.size.toString());
      
      // 上传缩略图
      if (processed.thumbnailBlob) {
        formData.append('thumbnail', processed.thumbnailBlob, 'thumbnail.jpg');
      }

      const response = await fetch('/api/materials/metadata', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('上传元数据失败');
      }

      const result = await response.json();

      // 3. 保存视频到本地存储
      setStage('保存到本地...');
      setProgress(95);

      // 视频已保存在 OPFS/IndexedDB 中（processMaterial 内部已处理）

      setProgress(100);
      setStage('完成');

      // 返回素材信息
      onUploadComplete({
        id: processed.id,
        shot_id: shotId,
        name: file.name,
        duration: processed.duration,
        width: processed.width,
        height: processed.height,
        thumbnail_url: result.thumbnail_url,
        is_local: true, // 标记为本地素材
      });

    } catch (error) {
      console.error('处理失败:', error);
      onError(error instanceof Error ? error.message : '处理失败');
    } finally {
      setIsProcessing(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [userId, shotId, onUploadComplete, onError]);

  return (
    <div className="w-full">
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*"
        onChange={handleFileSelect}
        className="hidden"
      />

      {isProcessing ? (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Loader2 size={16} className="animate-spin text-blue-600" />
            <span className="text-sm text-blue-700">{stage}</span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-right text-xs text-blue-600 mt-1">{progress}%</div>
        </div>
      ) : (
        <button
          onClick={() => fileInputRef.current?.click()}
          className="w-full h-32 border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center text-gray-500 hover:border-blue-400 hover:text-blue-600 bg-gray-50 transition-colors"
        >
          <Upload size={24} className="mb-2" />
          <span className="text-sm">点击上传视频</span>
          <span className="text-xs text-gray-400 mt-1">
            {isFastTranscodeSupported() ? '支持快速转码' : '标准转码'}
          </span>
        </button>
      )}
    </div>
  );
}
