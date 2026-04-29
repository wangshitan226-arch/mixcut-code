# 优化步骤1: 素材卡片添加转码状态指示器

## 修改文件
- `frontend/src/components/EditScreen.tsx`

## 修改内容

### 1. 导入新图标
```typescript
// 添加以下图标导入
import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
```

### 2. 添加转码失败状态管理
```typescript
const [transcodeFailedMaterials, setTranscodeFailedMaterials] = useState<Set<string>>(new Set());
```

### 3. 素材卡片转码状态显示
为每个素材卡片添加了以下状态指示：

#### 转码中状态
- 蓝色边框 (`ring-2 ring-blue-400`)
- 图片透明度降低 (`opacity-60`)
- 蓝色遮罩层显示旋转加载图标
- "转码中"文字标签

#### 转码失败状态
- 红色边框 (`ring-2 ring-red-400`)
- 红色遮罩层显示错误图标
- "转码失败"文字标签

#### 转码完成状态
- 在类型指示器旁显示绿色勾选图标
- 仅对视频素材显示

### 4. 状态判断逻辑
```typescript
const isTranscoding = material.transcode_status === 'processing' || transcodingMaterials.has(material.id);
const isTranscodeFailed = material.transcode_status === 'failed' || transcodeFailedMaterials.has(material.id);
const isTranscodeCompleted = material.transcode_status === 'completed' && !isTranscoding && !isTranscodeFailed;
```

### 5. 更新轮询逻辑处理失败状态
在轮询和立即检查转码状态的逻辑中，添加了：
- 转码完成时清除失败状态
- 转码失败时添加到失败集合
- 转码失败时立即刷新页面状态

## UI效果

### 转码中
- 素材卡片显示蓝色边框
- 图片变暗
- 中央显示旋转的加载图标
- "转码中"文字提示

### 转码失败
- 素材卡片显示红色边框
- 中央显示错误图标
- "转码失败"文字提示

### 转码完成
- 左上角类型图标旁显示绿色勾选
- 表示该视频已完成转码，可以正常使用

## 用户体验改进

1. **实时反馈**: 用户可以立即看到素材的转码状态
2. **视觉区分**: 不同状态使用不同颜色区分（蓝色=处理中，红色=失败，绿色=完成）
3. **减少困惑**: 用户不会再困惑为什么上传完成了还不能合成视频
4. **错误感知**: 转码失败时用户可以立即知道并采取措施
