# 多文件上传优化方案（方案A - 最小改动）

## 背景

当前上传功能存在以下问题：
1. 上传状态只能跟踪一个任务
2. 多镜头同时上传时状态会互相覆盖
3. 用户无法同时在多个镜头上传素材

## 优化目标（方案A）

1. ✅ 支持**多镜头同时上传**（每个镜头可以同时有上传任务）
2. ✅ 每个镜头的上传进度独立显示
3. ✅ 保持单文件选择（降低改动风险）
4. ❌ 不实现多文件选择（留给后续优化）
5. ❌ 不实现上传队列（保持简单）

## 与方案B的区别

| 功能 | 方案A（当前） | 方案B（完整版） |
|------|--------------|----------------|
| 多镜头同时上传 | ✅ 支持 | ✅ 支持 |
| 多文件选择 | ❌ 不支持 | ✅ 支持 |
| 上传队列 | ❌ 无 | ✅ 有 |
| 并发控制 | ❌ 无限制 | ✅ 最多2个 |
| 代码改动量 | 小 | 大 |
| 风险 | 低 | 中 |

## 实现步骤（方案A）

### 步骤1: 修改上传状态管理
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 将 `uploading` 从单对象改为 Map 结构
- Key: shotId, Value: { progress, fileName }
- 支持同时跟踪每个镜头的上传任务

### 步骤2: 更新上传函数
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 修改上传函数使用新的 Map 状态
- 每个镜头的上传独立跟踪

### 步骤3: 更新UI显示
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 每个镜头的添加按钮显示自己的上传进度
- 全局按钮显示总体状态

## 数据结构（方案A简化版）

### ShotUploadStatus
```typescript
interface ShotUploadStatus {
  progress: number;        // 进度 0-100
  fileName: string;        // 文件名
  status: 'uploading' | 'completed' | 'failed';
}
```

### 状态管理
```typescript
// 每个镜头的上传状态 Map<shotId, status>
const [shotUploads, setShotUploads] = useState<Map<number, ShotUploadStatus>>(new Map());

// 检查指定镜头是否正在上传
const isShotUploading = (shotId: number): boolean => {
  const upload = shotUploads.get(shotId);
  return upload?.status === 'uploading';
};

// 检查是否有任何镜头正在上传
const hasAnyUpload = (): boolean => {
  return Array.from(shotUploads.values()).some(u => u.status === 'uploading');
};
```

## 效果说明

### 场景1：在镜头A上传素材
- 镜头A的添加按钮显示进度条
- 镜头B、C的添加按钮保持可用
- 开始合成按钮禁用

### 场景2：同时在镜头A和镜头B上传
- 镜头A的添加按钮显示自己的进度
- 镜头B的添加按钮显示自己的进度
- 两个上传任务并行进行
- 开始合成按钮禁用

### 场景3：镜头A上传完成，镜头B仍在上传
- 镜头A的添加按钮恢复正常
- 镜头B的添加按钮继续显示进度
- 开始合成按钮仍然禁用（因为镜头B还在上传）

## 用户体验改进

1. **并行上传**: 可以在不同镜头同时上传素材，提高效率
2. **独立进度**: 每个镜头的上传进度独立显示，互不干扰
3. **简单可靠**: 改动小，风险低，易于测试

## 后续可扩展（方案B）

如果需要更强大的功能，后续可以升级为方案B：
1. 支持多文件选择
2. 添加上传队列
3. 限制并发数
4. 支持取消上传
