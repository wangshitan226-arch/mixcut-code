/**
 * 本地语音识别模块
 * 使用浏览器 Web Speech API（完全离线）
 * 
 * 限制：
 * - 仅 Chrome/Edge 支持较好
 * - 准确度可能不如云端 ASR
 * - 需要用户授权麦克风（或从视频提取音频）
 */

export interface LocalASROptions {
  language?: string;
  onResult?: (text: string, isFinal: boolean) => void;
  onError?: (error: string) => void;
}

export interface LocalASRResult {
  text: string;
  confidence: number;
  segments: {
    text: string;
    startTime: number;
    endTime: number;
    confidence: number;
  }[];
}

/**
 * 检查是否支持 Web Speech API
 */
export function isSpeechRecognitionSupported(): boolean {
  return 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window;
}

/**
 * 从视频文件提取音频并进行语音识别
 * 方案：使用 AudioContext 提取音频，然后用 Web Speech API
 * 
 * 注意：Web Speech API 通常需要实时音频流，处理视频文件较复杂
 * 简化方案：提示用户播放视频时同时识别
 */
export async function transcribeVideoLocal(
  videoFile: File,
  options: LocalASROptions = {}
): Promise<LocalASRResult> {
  const { language = 'zh-CN', onResult, onError } = options;

  if (!isSpeechRecognitionSupported()) {
    throw new Error('浏览器不支持语音识别');
  }

  // 创建 SpeechRecognition 实例
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  const recognition = new SpeechRecognition();

  recognition.lang = language;
  recognition.continuous = true;
  recognition.interimResults = true;

  const segments: LocalASRResult['segments'] = [];
  let fullText = '';

  return new Promise((resolve, reject) => {
    let startTime = Date.now();

    recognition.onresult = (event: any) => {
      const results = event.results;
      const lastResult = results[results.length - 1];
      const transcript = lastResult[0].transcript;
      const confidence = lastResult[0].confidence;

      if (lastResult.isFinal) {
        const endTime = Date.now();
        segments.push({
          text: transcript,
          startTime,
          endTime,
          confidence,
        });
        fullText += transcript + ' ';
        startTime = endTime;

        onResult?.(transcript, true);
      } else {
        onResult?.(transcript, false);
      }
    };

    recognition.onerror = (event: any) => {
      onError?.(event.error);
      reject(new Error(`语音识别错误: ${event.error}`));
    };

    recognition.onend = () => {
      resolve({
        text: fullText.trim(),
        confidence: segments.reduce((sum, s) => sum + s.confidence, 0) / (segments.length || 1),
        segments,
      });
    };

    // 开始识别
    recognition.start();

    // 创建视频元素播放
    const video = document.createElement('video');
    video.src = URL.createObjectURL(videoFile);
    video.muted = true; // 静音播放，避免干扰

    video.onplay = () => {
      startTime = Date.now();
    };

    video.onended = () => {
      recognition.stop();
    };

    video.play().catch(err => {
      recognition.stop();
      reject(err);
    });
  });
}

/**
 * 简单的音频提取（用于测试）
 * 实际生产环境应该用更专业的音频处理库
 */
export async function extractAudioFromVideo(videoFile: File): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.src = URL.createObjectURL(videoFile);

    video.onloadedmetadata = async () => {
      try {
        const stream = (video as any).captureStream();
        const audioTrack = stream.getAudioTracks()[0];
        
        if (!audioTrack) {
          reject(new Error('视频没有音频轨道'));
          return;
        }

        const audioStream = new MediaStream([audioTrack]);
        const mediaRecorder = new MediaRecorder(audioStream);
        const chunks: Blob[] = [];

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            chunks.push(e.data);
          }
        };

        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(chunks, { type: 'audio/webm' });
          resolve(audioBlob);
        };

        mediaRecorder.start();
        video.play();

        video.onended = () => {
          mediaRecorder.stop();
        };
      } catch (err) {
        reject(err);
      }
    };

    video.onerror = () => {
      reject(new Error('视频加载失败'));
    };
  });
}

/**
 * 将本地 ASR 结果转换为标准 Segment 格式
 */
export function convertToSegments(asrResult: LocalASRResult): any[] {
  return asrResult.segments.map((seg, index) => ({
    id: `local_${index}`,
    time: formatTime(seg.startTime),
    beginTime: seg.startTime,
    endTime: seg.endTime,
    text: seg.text,
    words: [], // 本地 ASR 不提供逐字信息
    type: 'speech',
    hasFiller: false,
    selected: false,
    expanded: false,
  }));
}

function formatTime(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}
