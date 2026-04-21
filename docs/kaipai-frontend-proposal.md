# 开拍式网感剪辑前端优化方案

## 一、问题分析

### 当前 editor_v3.html 的流程
```
上传视频 → 输入OSS URL → 开始识别 → 等待识别完成 → 文字快剪
```

### 我们的目标流程
```
混剪结果页 → 选中视频 → 直接进入文字快剪（视频已存在，无需上传）
```

### 关键差异

| 环节 | editor_v3.html | 我们需要 |
|------|----------------|----------|
| 视频来源 | 用户上传 | 混剪结果已存在 |
| 视频URL | 需要输入OSS URL | 直接使用render的file_path |
| 识别启动 | 用户点击"开始识别" | 自动启动或已预识别 |
| 页面结构 | 独立完整页面 | 嵌入ResultsScreen的编辑器 |

## 二、优化后的前端架构

### 2.1 组件结构

```
frontend/src/components/kaipai/
├── KaipaiEditor.tsx           # 主编辑器（简化版）
├── VideoPlayer.tsx            # 视频播放器（复用现有）
├── TranscriptEditor.tsx       # 文字快剪核心组件
│   ├── SegmentList.tsx        # 片段列表
│   ├── SegmentItem.tsx        # 单个片段
│   └── WordEditor.tsx         # 字级编辑
├── Toolbar.tsx                # 工具栏（删静音/删语气词/删除）
└── hooks/
    ├── useTranscription.ts    # 语音识别状态管理
    └── useSegments.ts         # 片段操作管理
```

### 2.2 核心流程设计

```
ResultsScreen
    ↓ 用户点击【网感剪辑】按钮
调用 POST /api/renders/<id>/kaipai/edit
    ↓
创建 KaipaiEdit 记录
    ↓
弹出/跳转到 KaipaiEditor
    ├─ 视频直接使用 render.file_path
    ├─ 自动启动语音识别（如果未识别过）
    └─ 显示识别结果和编辑界面
```

## 三、KaipaiEditor 组件设计

### 3.1 简化后的界面结构

```tsx
// KaipaiEditor.tsx 核心结构
<div className="kaipai-editor">
  {/* 顶部导航 */}
  <header>
    <button onClick={onBack}>返回</button>
    <span>文字快剪 #{version}</span>
    <button onClick={handleSave}>保存</button>
  </header>
  
  {/* 视频预览区 */}
  <div className="video-preview">
    <video src={videoUrl} controls />
    <div className="subtitle-overlay">{currentSubtitle}</div>
  </div>
  
  {/* 文字快剪区 */}
  <div className="transcript-editor">
    {loading ? (
      <LoadingState />
    ) : (
      <>
        <Toolbar 
          onDeleteSilence={selectAllSilence}
          onDeleteFiller={selectAllFiller}
          onDeleteSelected={deleteSelected}
        />
        <SegmentList 
          segments={segments}
          onToggle={toggleSegment}
          onJump={jumpToTime}
        />
      </>
    )}
  </div>
</div>
```

### 3.2 与 editor_v3.html 的差异对比

| 功能 | editor_v3.html | 新 KaipaiEditor |
|------|----------------|-----------------|
| 上传流程 | UploadPage 组件 | ❌ 移除 |
| OSS URL输入 | 手动输入 | ❌ 移除，自动使用render路径 |
| 视频预览 | 独立实现 | ✅ 复用现有VideoPlayer |
| 语音识别 | 用户手动启动 | ✅ 自动启动 |
| 识别等待 | 全屏loading | ✅ 局部loading，可预览视频 |
| 片段编辑 | 完整功能 | ✅ 保留核心功能 |
| 字级编辑 | 支持 | ✅ 保留 |
| 模板/字幕/BGM | 界面占位 | ⚠️ 第一阶段先不做 |

## 四、具体实现方案

### 4.1 ResultsScreen 修改

```tsx
// ResultsScreen.tsx

// 1. 添加网感剪辑按钮
<div className="video-card">
  {/* ... 现有内容 ... */}
  
  <div className="actions">
    <button onClick={(e) => handleDownload(item, e)}>
      <Download size={12} />
    </button>
    
    {/* 新增：网感剪辑入口 */}
    <button 
      onClick={(e) => handleKaipaiEdit(item, e)}
      className="kaipai-btn"
      title="网感剪辑"
    >
      <Scissors size={12} />
    </button>
  </div>
</div>

// 2. 处理函数
const handleKaipaiEdit = async (item: ResultItem, e: React.MouseEvent) => {
  e.stopPropagation();
  
  try {
    // 创建剪辑任务
    const response = await fetch(
      `${API_BASE_URL}/api/renders/${item.id}/kaipai/edit`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' } }
    );
    
    if (!response.ok) throw new Error('创建剪辑任务失败');
    
    const data = await response.json();
    
    // 打开编辑器（弹窗或新页面）
    setKaipaiEditorOpen(true);
    setKaipaiEditData({
      editId: data.edit_id,
      renderId: item.id,
      videoUrl: `${API_BASE_URL}${data.video_url}`,
      version: data.version
    });
    
  } catch (error) {
    console.error('进入网感剪辑失败:', error);
    alert('进入网感剪辑失败，请重试');
  }
};
```

### 4.2 KaipaiEditor 完整实现

```tsx
// components/kaipai/KaipaiEditor.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronLeft, Trash2, VolumeX, Zap, RotateCcw, Scissors } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3002';

interface KaipaiEditorProps {
  editId: string;
  renderId: string;
  videoUrl: string;
  version: number;
  onBack: () => void;
  onSave?: (editId: string) => void;
}

interface Segment {
  id: string;
  time: string;
  beginTime: number;
  endTime: number;
  text: string;
  type: 'speech' | 'silence';
  words?: Word[];
  hasFiller?: boolean;
  selected?: boolean;
  expanded?: boolean;
}

interface Word {
  text: string;
  beginTime: number;
  endTime: number;
  isFiller: boolean;
}

export default function KaipaiEditor({
  editId,
  renderId,
  videoUrl,
  version,
  onBack,
  onSave
}: KaipaiEditorProps) {
  const [loading, setLoading] = useState(true);
  const [loadingText, setLoadingText] = useState('正在识别语音...');
  const [segments, setSegments] = useState<Segment[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  
  // 1. 启动语音识别（组件挂载时自动启动）
  useEffect(() => {
    startTranscription();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [editId]);
  
  const startTranscription = async () => {
    try {
      // 注意：这里需要后端提供视频的直接访问URL
      // 如果视频在本地，需要上传到OSS获取URL
      const response = await fetch(
        `${API_BASE_URL}/api/kaipai/${editId}/transcribe`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            // 后端自动处理视频URL，前端不需要传
          })
        }
      );
      
      if (!response.ok) {
        throw new Error('启动识别失败');
      }
      
      // 开始轮询识别结果
      pollTranscriptionStatus();
      
    } catch (error) {
      console.error('启动识别失败:', error);
      setLoadingText('启动识别失败，请重试');
    }
  };
  
  // 2. 轮询识别状态
  const pollTranscriptionStatus = () => {
    pollingRef.current = setInterval(async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/kaipai/${editId}/transcribe/status`
        );
        const data = await response.json();
        
        if (data.status === 'completed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setLoading(false);
          setSegments(data.result?.sentences || []);
        } else if (data.status === 'failed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setLoadingText('识别失败: ' + (data.error || '未知错误'));
        }
      } catch (error) {
        console.error('轮询失败:', error);
      }
    }, 1000);
  };
  
  // 3. 视频时间更新
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    
    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
    };
    
    video.addEventListener('timeupdate', handleTimeUpdate);
    return () => video.removeEventListener('timeupdate', handleTimeUpdate);
  }, []);
  
  // 4. 获取当前字幕
  const getCurrentSubtitle = () => {
    const currentTimeMs = currentTime * 1000;
    const current = segments.find(
      s => currentTimeMs >= s.beginTime && currentTimeMs <= s.endTime && s.type === 'speech'
    );
    return current?.text || '';
  };
  
  // 5. 片段操作
  const toggleSegment = (id: string) => {
    setSegments(prev => prev.map(s => 
      s.id === id ? { ...s, selected: !s.selected } : s
    ));
  };
  
  const jumpToTime = (beginTime: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = beginTime / 1000;
      videoRef.current.play();
      setIsPlaying(true);
    }
  };
  
  const selectAllSilence = () => {
    setSegments(prev => prev.map(s => 
      s.type === 'silence' ? { ...s, selected: true } : s
    ));
  };
  
  const selectAllFiller = () => {
    setSegments(prev => prev.map(s => 
      s.hasFiller ? { ...s, selected: true } : s
    ));
  };
  
  const clearSelection = () => {
    setSegments(prev => prev.map(s => ({ ...s, selected: false })));
  };
  
  const deleteSelected = () => {
    const selectedCount = segments.filter(s => s.selected).length;
    if (selectedCount === 0) return;
    
    if (confirm(`确定要删除选中的 ${selectedCount} 个片段吗？`)) {
      setSegments(prev => prev.filter(s => !s.selected));
    }
  };
  
  // 6. 保存编辑
  const handleSave = async () => {
    try {
      const removedSegments = segments
        .filter(s => s.selected)
        .map(s => ({
          start: s.beginTime,
          end: s.endTime,
          type: s.type
        }));
      
      const response = await fetch(
        `${API_BASE_URL}/api/kaipai/${editId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ removed_segments: removedSegments })
        }
      );
      
      if (response.ok) {
        onSave?.(editId);
        onBack();
      }
    } catch (error) {
      console.error('保存失败:', error);
      alert('保存失败，请重试');
    }
  };
  
  const selectedCount = segments.filter(s => s.selected).length;
  const savedTime = segments
    .filter(s => s.selected)
    .reduce((acc, s) => acc + (s.endTime - s.beginTime), 0) / 1000;
  
  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-4 h-14 bg-white border-b shrink-0">
        <button onClick={onBack} className="p-2 hover:bg-gray-100 rounded-full">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold">文字快剪 #{version}</h1>
        <button 
          onClick={handleSave}
          className="px-4 py-1.5 bg-blue-600 text-white rounded-full text-sm font-medium"
        >
          保存
        </button>
      </header>
      
      {/* Video Preview */}
      <div className="bg-gray-900 flex items-center justify-center" style={{ height: '35vh' }}>
        <div className="relative h-full aspect-[9/16] bg-black">
          <video
            ref={videoRef}
            src={videoUrl}
            className="w-full h-full object-contain"
            controls
            playsInline
          />
          <div className="absolute bottom-16 left-0 right-0 text-center px-4 pointer-events-none">
            <p className="inline-block text-white text-sm font-bold drop-shadow-lg">
              {getCurrentSubtitle()}
            </p>
          </div>
        </div>
      </div>
      
      {/* Transcript Editor */}
      <div className="flex-1 bg-gray-50 flex flex-col overflow-hidden">
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center">
            <div className="flex gap-1 items-end h-16 mb-4">
              {[...Array(12)].map((_, i) => (
                <div
                  key={i}
                  className="w-1.5 bg-blue-500 rounded-full animate-pulse"
                  style={{
                    height: `${Math.random() * 40 + 8}px`,
                    animationDelay: `${i * 0.1}s`
                  }}
                />
              ))}
            </div>
            <p className="text-gray-600">{loadingText}</p>
          </div>
        ) : (
          <>
            {/* Toolbar */}
            <div className="px-4 py-3 bg-white border-b flex items-center justify-between">
              <div className="text-sm">
                <span className="text-gray-600">已选择 </span>
                <span className="font-semibold text-blue-600">{selectedCount}</span>
                <span className="text-gray-600"> 段，预计节省 </span>
                <span className="font-semibold text-blue-600">{savedTime.toFixed(1)}</span>
                <span className="text-gray-600"> 秒</span>
              </div>
              <button 
                onClick={clearSelection}
                className="text-gray-500 text-sm flex items-center gap-1"
              >
                <RotateCcw size={14} /> 清除
              </button>
            </div>
            
            {/* Segment List */}
            <div className="flex-1 overflow-y-auto p-4">
              {segments.map(segment => (
                <div
                  key={segment.id}
                  onClick={() => jumpToTime(segment.beginTime)}
                  className={`mb-2 p-3 rounded-xl border-2 cursor-pointer transition-all ${
                    segment.selected 
                      ? 'border-blue-500 bg-blue-50' 
                      : segment.type === 'silence'
                        ? 'border-gray-200 bg-gray-100'
                        : 'border-gray-200 bg-white hover:border-blue-300'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSegment(segment.id);
                      }}
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                        segment.selected 
                          ? 'bg-blue-600 border-blue-600' 
                          : 'border-gray-300'
                      }`}
                    >
                      {segment.selected && <span className="text-white text-xs">✓</span>}
                    </div>
                    
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                          {segment.time}
                        </span>
                        {segment.type === 'silence' && (
                          <span className="text-[10px] bg-gray-400 text-white px-1.5 py-0.5 rounded">
                            静音
                          </span>
                        )}
                        {segment.hasFiller && (
                          <span className="text-[10px] bg-orange-100 text-orange-600 px-1.5 py-0.5 rounded">
                            含语气词
                          </span>
                        )}
                      </div>
                      
                      <p className={`text-sm ${
                        segment.selected ? 'text-gray-400 line-through' : 'text-gray-800'
                      }`}>
                        {segment.type === 'silence' && <VolumeX size={14} className="inline mr-1" />}
                        {segment.text}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            {/* Bottom Actions */}
            <div className="p-4 bg-white border-t flex gap-2">
              <button
                onClick={selectAllSilence}
                className="flex-1 py-3 bg-gray-100 rounded-xl text-sm font-medium flex flex-col items-center gap-1"
              >
                <VolumeX size={18} className="text-gray-600" />
                <span className="text-gray-600">删静音</span>
              </button>
              <button
                onClick={selectAllFiller}
                className="flex-1 py-3 bg-gray-100 rounded-xl text-sm font-medium flex flex-col items-center gap-1"
              >
                <Zap size={18} className="text-gray-600" />
                <span className="text-gray-600">删语气词</span>
              </button>
              <button
                onClick={deleteSelected}
                disabled={selectedCount === 0}
                className={`flex-[2] py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2 ${
                  selectedCount > 0 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-400'
                }`}
              >
                <Trash2 size={18} />
                删除 ({selectedCount})
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

### 4.3 ResultsScreen 集成

```tsx
// ResultsScreen.tsx 关键修改

// 1. 添加状态
const [kaipaiEditorOpen, setKaipaiEditorOpen] = useState(false);
const [kaipaiData, setKaipaiData] = useState<{
  editId: string;
  renderId: string;
  videoUrl: string;
  version: number;
} | null>(null);

// 2. 渲染编辑器（弹窗或全屏）
return (
  <div className="results-screen">
    {/* 现有结果列表 */}
    {!kaipaiEditorOpen ? (
      <>
        {/* ... 现有ResultsScreen内容 ... */}
      </>
    ) : kaipaiData ? (
      <KaipaiEditor
        editId={kaipaiData.editId}
        renderId={kaipaiData.renderId}
        videoUrl={kaipaiData.videoUrl}
        version={kaipaiData.version}
        onBack={() => {
          setKaipaiEditorOpen(false);
          setKaipaiData(null);
        }}
        onSave={(editId) => {
          // 刷新版本列表
          console.log('保存成功:', editId);
        }}
      />
    ) : null}
  </div>
);
```

## 五、后端配合修改

### 5.1 自动处理视频URL

后端需要修改，让 `/api/kaipai/<edit_id>/transcribe` 接口自动获取视频URL：

```python
@kaipai_bp.route('/kaipai/<edit_id>/transcribe', methods=['POST'])
def start_transcription(edit_id):
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 自动获取render的视频路径
    render = Render.query.get(edit.render_id)
    if not render or not render.file_path:
        return jsonify({'error': 'Video not found'}), 404
    
    # 如果视频在本地，需要先上传到OSS获取URL
    # 或者使用本地路径（如果ASR支持）
    video_url = f"{request.host_url}renders/{os.path.basename(render.file_path)}"
    
    # 创建ASR任务
    create_asr_task(edit_id, video_url)
    process_asr_task(edit_id, video_url)
    
    edit.status = 'transcribing'
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'transcribing'
    })
```

## 六、总结

### 优化后的流程

```
用户点击【网感剪辑】
    ↓
创建 KaipaiEdit 记录
    ↓
弹出 KaipaiEditor（视频直接使用render路径）
    ↓
自动启动语音识别
    ↓
显示识别结果
    ↓
用户编辑（删片段）
    ↓
保存编辑参数
    ↓
返回 ResultsScreen
```

### 与 editor_v3.html 的主要区别

1. **移除上传流程**：视频直接使用混剪结果
2. **自动启动识别**：不需要用户手动点击"开始识别"
3. **简化界面**：移除OSS URL输入、上传进度等无关元素
4. **集成方式**：作为 ResultsScreen 的一部分，不是独立页面

### 下一步

1. 确认前端方案
2. 同步调整后端API（自动获取视频URL）
3. 开始编码实现
