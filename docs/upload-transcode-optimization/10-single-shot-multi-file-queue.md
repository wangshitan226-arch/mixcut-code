# 单镜头多文件上传+队列方案

## 需求理解

用户希望在**单个镜头**中：
1. 一次选择**多个文件**
2. 文件按**队列顺序**上传（串行处理）
3. 前端显示**当前上传**和**等待中**的文件

## 方案设计

### 核心逻辑
- 用户选择多个文件 → 加入上传队列
- 一次只上传**一个文件**（串行）
- 前端显示：当前上传进度 + 等待文件数
- 完成后自动开始下一个

### 数据结构

```typescript
interface UploadQueueItem {
  id: string;           // 任务ID
  file: File;           // 文件
  fileName: string;     // 文件名
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  progress: number;     // 0-100
  error?: string;       // 错误信息
}

// 状态管理
const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
const [currentUploadId, setCurrentUploadId] = useState<string | null>(null);
const [isProcessingQueue, setIsProcessingQueue] = useState(false);
```

### 队列处理流程

```
用户选择3个文件
    ↓
加入队列：[文件1, 文件2, 文件3]
    ↓
开始处理文件1（状态：uploading）
文件2、3等待（状态：pending）
    ↓
文件1完成 → 自动开始文件2
    ↓
全部完成 → 队列清空
```

### UI显示

#### 添加按钮区域
```
┌─────────────────────────┐
│  添加素材               │
│                         │
│  正在上传: 文件1.mp4    │
│  [==========>    ] 60%  │
│                         │
│  等待中: 2个文件        │
│  • 文件2.mp4            │
│  • 文件3.mp4            │
└─────────────────────────┘
```

#### 全局按钮
- 有文件在上传或等待时禁用
- 显示："上传中 (1/3)"

## 实现步骤

### 1. 修改文件输入支持多选
```tsx
<input
  type="file"
  multiple  // 添加多选支持
  accept="video/*,image/*"
  ...
/>
```

### 2. 修改 handleFileSelect
- 遍历所有选择的文件
- 为每个文件创建队列项
- 加入队列
- 触发队列处理

### 3. 实现队列处理函数
```typescript
const processQueue = async () => {
  if (isProcessingQueue) return;
  if (uploadQueue.length === 0) return;
  
  setIsProcessingQueue(true);
  
  // 找到第一个pending的文件
  const pendingItem = uploadQueue.find(item => item.status === 'pending');
  if (!pendingItem) {
    setIsProcessingQueue(false);
    return;
  }
  
  // 开始上传
  setCurrentUploadId(pendingItem.id);
  await uploadFile(pendingItem);
  
  // 上传完成，继续处理下一个
  setIsProcessingQueue(false);
  processQueue(); // 递归处理下一个
};
```

### 4. 修改上传函数
- 接收队列项而不是File
- 更新队列项的进度和状态
- 完成后更新队列

### 5. 更新UI显示
- 显示当前上传文件名和进度
- 显示等待文件列表
- 显示完成/失败状态

## 效果说明

### 场景1：选择3个文件上传
1. 文件选择器关闭
2. 3个文件加入队列
3. 文件1开始上传，显示进度
4. 显示"等待中: 2个文件"
5. 文件1完成 → 自动开始文件2
6. 全部完成后，按钮恢复正常

### 场景2：上传过程中选择更多文件
1. 新文件加入队列末尾
2. 当前上传不受影响
3. 新文件在当前完成后自动开始

### 场景3：某个文件上传失败
1. 该文件标记为failed
2. 继续处理下一个文件
3. 失败文件显示重试按钮

## 优点

1. **简单可靠**：串行上传，不会导致后端压力过大
2. **用户体验好**：可以看到所有选择的文件和状态
3. **错误隔离**：单个文件失败不影响其他文件
4. **易于实现**：不需要复杂的并发控制

## 后端影响

- 无需修改后端代码
- 每个文件仍然是独立的 /api/upload 请求
- 串行处理不会增加后端并发压力
