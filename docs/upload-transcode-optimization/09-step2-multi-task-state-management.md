# 步骤2: 修改上传状态管理 - 支持多任务跟踪

## 修改文件
- `frontend/src/components/EditScreen.tsx`

## 修改内容

### 1. 添加上传任务类型定义
```typescript
// 上传任务状态
interface UploadTask {
  id: string;              // 任务唯一ID
  shotId: number;          // 所属镜头ID
  file: File;              // 上传的文件
  fileName: string;        // 文件名
  progress: number;        // 进度 0-100
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;          // 错误信息
  materialId?: string;     // 上传成功后返回的素材ID
  transcodeTaskId?: string; // 转码任务ID
  result?: any;            // 上传成功后的完整响应
}
```

### 2. 替换旧的上传状态
**旧代码**:
```typescript
const [uploading, setUploading] = useState<{ shotId: number | null; progress: number }>({ 
  shotId: null, 
  progress: 0 
});
```

**新代码**:
```typescript
// 上传任务管理（新的多任务上传系统）
const [uploadTasks, setUploadTasks] = useState<Map<string, UploadTask>>(new Map());
const [uploadQueue, setUploadQueue] = useState<string[]>([]); // 等待上传的任务ID队列

// 计算正在上传的任务数
const activeUploadCount = React.useMemo(() => {
  return Array.from(uploadTasks.values()).filter(t => t.status === 'uploading').length;
}, [uploadTasks]);

// 计算是否有上传或转码任务
const hasActiveUploads = React.useMemo(() => {
  return uploadTasks.size > 0;
}, [uploadTasks]);

// 兼容旧代码：获取指定镜头的上传进度（用于UI显示）
const getShotUploadProgress = useCallback((shotId: number): { isUploading: boolean; progress: number; count: number } => {
  const shotTasks = Array.from(uploadTasks.values()).filter(t => t.shotId === shotId);
  if (shotTasks.length === 0) {
    return { isUploading: false, progress: 0, count: 0 };
  }
  const totalProgress = shotTasks.reduce((sum, t) => sum + t.progress, 0);
  return {
    isUploading: true,
    progress: Math.round(totalProgress / shotTasks.length),
    count: shotTasks.length
  };
}, [uploadTasks]);
```

### 3. 更新 hasTranscodingMaterials 逻辑
现在同时检查上传任务和转码任务：
```typescript
const hasTranscodingMaterials = React.useMemo(() => {
  // 检查是否有素材正在上传（包括pending和uploading状态）
  const isUploading = Array.from(uploadTasks.values()).some(t => 
    t.status === 'pending' || t.status === 'uploading' || t.status === 'processing'
  );
  
  // 检查是否有素材正在转码
  const isTranscoding = shots.some(shot => 
    shot.materials.some(mat => 
      mat.transcode_status === 'processing' || transcodingMaterials.has(mat.id)
    )
  );
  
  return isUploading || isTranscoding;
}, [shots, transcodingMaterials, uploadTasks]);
```

## 关键改进

1. **支持多任务**: 从单任务跟踪改为 Map 结构，支持任意数量的上传任务
2. **队列管理**: 添加了 uploadQueue 用于管理等待中的任务
3. **并发控制**: activeUploadCount 用于控制并发数
4. **兼容层**: getShotUploadProgress 函数兼容旧的UI显示逻辑
5. **状态细分**: 任务状态细分为 pending/uploading/processing/completed/failed
