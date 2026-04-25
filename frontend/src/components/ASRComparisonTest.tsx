/**
 * ASR 对比测试组件
 * 对比 Web Speech API 和阿里云 DashScope ASR 的效果
 */

import React, { useState, useRef, useCallback } from 'react';
import { Mic, Play, Loader2, CheckCircle, XCircle, ArrowRight } from 'lucide-react';

interface ASRResult {
  provider: string;
  text: string;
  segments: {
    id: string;
    beginTime: number;
    endTime: number;
    text: string;
    type: 'speech' | 'silence';
    words?: { text: string; beginTime: number; endTime: number }[];
  }[];
  duration: number;
  confidence?: number;
}

export default function ASRComparisonTest() {
  const [isRecording, setIsRecording] = useState(false);
  const [localResult, setLocalResult] = useState<ASRResult | null>(null);
  const [serverResult, setServerResult] = useState<ASRResult | null>(null);
  const [loading, setLoading] = useState({ local: false, server: false });
  const [error, setError] = useState('');
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);

  // 检查 Web Speech API 支持
  const isWebSpeechSupported = 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window;

  // 本地 Web Speech API 识别
  const startLocalASR = useCallback(async () => {
    if (!videoFile) {
      setError('请先选择视频文件');
      return;
    }

    if (!isWebSpeechSupported) {
      setError('浏览器不支持 Web Speech API');
      return;
    }

    setLoading(prev => ({ ...prev, local: true }));
    setError('');

    try {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();

      recognition.lang = 'zh-CN';
      recognition.continuous = true;
      recognition.interimResults = true;

      const segments: ASRResult['segments'] = [];
      let fullText = '';
      let segmentId = 1;
      let startTime = Date.now();

      await new Promise<void>((resolve, reject) => {
        recognition.onresult = (event: any) => {
          const results = event.results;
          const lastResult = results[results.length - 1];
          const transcript = lastResult[0].transcript;

          if (lastResult.isFinal) {
            const endTime = Date.now();
            segments.push({
              id: `local_${segmentId++}`,
              beginTime: startTime,
              endTime: endTime,
              text: transcript,
              type: 'speech',
              words: transcript.split('').map((char: string, i: number) => ({
                text: char,
                beginTime: startTime + (i * 100),
                endTime: startTime + ((i + 1) * 100),
              })),
            });
            fullText += transcript + ' ';
            startTime = endTime;
          }
        };

        recognition.onerror = (event: any) => {
          reject(new Error(`识别错误: ${event.error}`));
        };

        recognition.onend = () => {
          resolve();
        };

        // 开始识别
        recognition.start();

        // 播放视频
        const video = document.createElement('video');
        video.src = URL.createObjectURL(videoFile);
        video.muted = true;

        video.onplay = () => {
          startTime = Date.now();
        };

        video.onended = () => {
          setTimeout(() => {
            recognition.stop();
          }, 1000);
        };

        video.play().catch(reject);
      });

      setLocalResult({
        provider: 'Web Speech API (本地)',
        text: fullText.trim(),
        segments,
        duration: segments.reduce((sum, s) => sum + (s.endTime - s.beginTime), 0),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '本地识别失败');
    } finally {
      setLoading(prev => ({ ...prev, local: false }));
    }
  }, [videoFile]);

  // 模拟服务器 ASR（实际应该调用后端接口）
  const startServerASR = useCallback(async () => {
    if (!videoFile) {
      setError('请先选择视频文件');
      return;
    }

    setLoading(prev => ({ ...prev, server: true }));
    setError('');

    try {
      // 模拟服务器 ASR 结果（实际应该上传到 OSS 然后调用后端）
      await new Promise(resolve => setTimeout(resolve, 2000));

      // 模拟结果
      setServerResult({
        provider: '阿里云 DashScope (服务器)',
        text: '这是一个模拟的服务器 ASR 结果。实际使用时需要先将视频上传到 OSS，然后调用后端 ASR 接口。',
        segments: [
          {
            id: 'server_1',
            beginTime: 0,
            endTime: 3000,
            text: '这是一个模拟的服务器 ASR 结果。',
            type: 'speech',
            words: [
              { text: '这', beginTime: 0, endTime: 200 },
              { text: '是', beginTime: 200, endTime: 400 },
              { text: '一', beginTime: 400, endTime: 600 },
              { text: '个', beginTime: 600, endTime: 800 },
            ],
          },
          {
            id: 'server_2',
            beginTime: 3000,
            endTime: 6000,
            text: '实际使用时需要先将视频上传到 OSS。',
            type: 'speech',
          },
        ],
        duration: 6000,
        confidence: 0.95,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '服务器识别失败');
    } finally {
      setLoading(prev => ({ ...prev, server: false }));
    }
  }, [videoFile]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setVideoFile(file);
      setLocalResult(null);
      setServerResult(null);
      setError('');
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">ASR 对比测试</h1>

      {/* 文件选择 */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">1. 选择视频文件</h2>
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          onChange={handleFileSelect}
          className="hidden"
        />
        <div className="flex items-center gap-4">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            选择视频
          </button>
          {videoFile && (
            <span className="text-gray-600">
              {videoFile.name} ({(videoFile.size / 1024 / 1024).toFixed(2)}MB)
            </span>
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          {error}
        </div>
      )}

      {/* 对比按钮 */}
      {videoFile && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">2. 开始识别对比</h2>
          <div className="flex gap-4">
            <button
              onClick={startLocalASR}
              disabled={loading.local || !isWebSpeechSupported}
              className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {loading.local ? <Loader2 className="animate-spin" size={20} /> : <Mic size={20} />}
              本地 Web Speech API
            </button>
            <button
              onClick={startServerASR}
              disabled={loading.server}
              className="flex items-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              {loading.server ? <Loader2 className="animate-spin" size={20} /> : <Play size={20} />}
              服务器 DashScope ASR
            </button>
          </div>
          {!isWebSpeechSupported && (
            <p className="text-orange-600 mt-2 text-sm">
              ⚠️ 当前浏览器不支持 Web Speech API，请使用 Chrome/Edge
            </p>
          )}
        </div>
      )}

      {/* 结果对比 */}
      {(localResult || serverResult) && (
        <div className="grid grid-cols-2 gap-6">
          {/* 本地结果 */}
          {localResult && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <CheckCircle className="text-green-500" size={20} />
                {localResult.provider}
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-500">完整文本</label>
                  <p className="bg-gray-50 p-3 rounded mt-1">{localResult.text}</p>
                </div>
                <div>
                  <label className="text-sm text-gray-500">识别片段 ({localResult.segments.length})</label>
                  <div className="space-y-2 mt-1 max-h-60 overflow-y-auto">
                    {localResult.segments.map(seg => (
                      <div key={seg.id} className="bg-gray-50 p-2 rounded text-sm">
                        <div className="flex justify-between text-gray-500 text-xs mb-1">
                          <span>{(seg.beginTime / 1000).toFixed(1)}s - {(seg.endTime / 1000).toFixed(1)}s</span>
                          <span>{seg.type}</span>
                        </div>
                        <p>{seg.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  总时长: {(localResult.duration / 1000).toFixed(1)}s
                </div>
              </div>
            </div>
          )}

          {/* 服务器结果 */}
          {serverResult && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <CheckCircle className="text-purple-500" size={20} />
                {serverResult.provider}
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-500">完整文本</label>
                  <p className="bg-gray-50 p-3 rounded mt-1">{serverResult.text}</p>
                </div>
                <div>
                  <label className="text-sm text-gray-500">识别片段 ({serverResult.segments.length})</label>
                  <div className="space-y-2 mt-1 max-h-60 overflow-y-auto">
                    {serverResult.segments.map(seg => (
                      <div key={seg.id} className="bg-gray-50 p-2 rounded text-sm">
                        <div className="flex justify-between text-gray-500 text-xs mb-1">
                          <span>{(seg.beginTime / 1000).toFixed(1)}s - {(seg.endTime / 1000).toFixed(1)}s</span>
                          <span>{seg.type}</span>
                        </div>
                        <p>{seg.text}</p>
                        {seg.words && (
                          <div className="mt-1 text-xs text-gray-400">
                            字数: {seg.words.length}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  总时长: {(serverResult.duration / 1000).toFixed(1)}s
                  {serverResult.confidence && (
                    <span className="ml-2">置信度: {(serverResult.confidence * 100).toFixed(1)}%</span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 差异说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mt-6">
        <h3 className="font-semibold text-blue-900 mb-2">Web Speech API vs DashScope ASR 对比</h3>
        <div className="space-y-2 text-sm text-blue-800">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <strong>Web Speech API (本地)</strong>
              <ul className="list-disc list-inside mt-1 space-y-1">
                <li>完全离线，无需上传</li>
                <li>实时识别，边播放边识别</li>
                <li>仅支持 Chrome/Edge</li>
                <li>无逐字时间戳</li>
                <li>无法检测静音段</li>
                <li>准确度一般</li>
              </ul>
            </div>
            <div>
              <strong>DashScope ASR (服务器)</strong>
              <ul className="list-disc list-inside mt-1 space-y-1">
                <li>需要上传视频到 OSS</li>
                <li>异步处理，需要等待</li>
                <li>支持所有浏览器</li>
                <li>有逐字时间戳</li>
                <li>自动检测静音段</li>
                <li>准确度高</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
