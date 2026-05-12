# 优化步骤2: 添加全局转码进度面板

## 修改文件
- `frontend/src/components/EditScreen.tsx`

## 修改内容

### 1. 添加状态管理
```typescript
const [transcodeProgressMap, setTranscodeProgressMap] = useState<Map<string, number>>(new Map());
const [showTranscodePanel, setShowTranscodePanel] = useState(false);
```

### 2. 更新轮询逻辑获取进度
在轮询转码状态时，添加进度更新：
```typescript
// 更新进度
if (data.progress !== undefined) {
  setTranscodeProgressMap(prev => new Map(prev).set(mat.id, data.progress));
}
```

### 3. 添加全局转码进度面板UI

#### 面板头部
- 显示总任务数
- 显示处理中数量（蓝色标签）
- 显示失败数量（红色标签）
- 可点击展开/收起

#### 展开内容
- **正在转码的素材列表**:
  - 缩略图
  - 素材名称
  - 进度条（带百分比）
  - 旋转加载图标

- **转码失败的素材列表**:
  - 缩略图
  - 素材名称
  - "转码失败"文字
  - 错误图标

## UI效果

### 面板收起状态
- 显示转码任务总数
- 显示处理中和失败的数量标签
- 右侧箭头指示展开状态

### 面板展开状态
- 显示每个转码任务的详细信息
- 进度条实时更新
- 失败任务用红色背景区分
- 最大高度限制，超出可滚动

## 用户体验改进

1. **全局视角**: 用户可以一眼看到所有转码任务的状态
2. **进度可视化**: 进度条直观显示转码进度
3. **快速定位**: 可以快速找到正在转码或失败的素材
4. **不打扰**: 收起时不占用太多空间
