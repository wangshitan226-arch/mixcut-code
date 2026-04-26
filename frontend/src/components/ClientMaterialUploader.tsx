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
      // 双轨并行制：同时启动浏览器转码和服务器转码
      setStage('双轨并行处理中...');

      // 轨道1: 浏览器 WebCodecs 本地转码 (视频② - 用于预览)
      const browserTrackPromise = processMaterial(file, {
        quality: 'medium',
        generateThumbnail: true,
        onProgress: (progress, stage) => {
          // 浏览器轨道进度占 0-50%
          setProgress(Math.round(progress * 0.5));
        },
      });

      // 轨道2: 服务器 FFmpeg 转码 (视频① - 用于ASR和导出)
      // 使用已有接口 /api/upload，它会自动保存到 uploads/ 并启动 FFmpeg 转码到 unified/
      const serverTrackPromise = (async () => {
        const formData = new FormData();
        formData.append('user_id', userId);
        formData.append('shotId', shotId.toString());
        formData.append('file', file);
        formData.append('quality', 'medium');

        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error('上传原始视频到本地失败');
        }

        return response.json();
      })();

      // 等待双轨都完成
      const [processed, serverResult] = await Promise.all([
        browserTrackPromise,
        serverTrackPromise
      ]);

      setProgress(100);
      setStage('双轨处理完成');

      // 返回素材信息（包含双轨数据）
      onUploadComplete({
        id: processed.id,
        shot_id: shotId,
        name: file.name,
        duration: processed.duration,
        width: processed.width,
        height: processed.height,
        thumbnail_url: serverResult.thumbnail_url,
        is_local: true,
        // 双轨数据
        browser_video_url: processed.videoUrl,  // 视频②: 浏览器本地转码结果
        server_video_path: serverResult.file_path,  // 视频①: 服务器原始文件路径
        server_unified_path: serverResult.unified_path,  // 视频①: 服务器 FFmpeg 转码结果
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
