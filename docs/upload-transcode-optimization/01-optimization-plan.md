# 素材上传转码优化方案

## 优化背景

当前素材上传采用双轨并行制架构，但用户交互存在以下问题：
1. 素材卡片不显示转码状态，用户无法直观感知转码进度
2. 上传完成后进度条消失，但服务器转码可能仍在进行
3. 双轨进度计算可能不准确
4. 转码失败没有视觉反馈
5. WebSocket断开后无感知

## 优化目标

提升用户上传素材时的体验，让用户清晰了解每个素材的处理状态。

## 优化步骤

### 步骤1: 素材卡片添加转码状态指示器
**优先级**: P0 (最高)
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 在素材卡片上叠加显示转码状态
- 转码中: 显示旋转加载图标 + "转码中"文字
- 转码完成: 正常显示
- 转码失败: 显示错误图标 + 重试按钮

### 步骤2: 添加全局转码进度面板
**优先级**: P0
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 在页面顶部添加转码进度面板
- 显示当前正在转码的素材列表
- 显示每个素材的转码进度百分比

### 步骤3: 优化双轨进度显示逻辑
**优先级**: P1
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 分别显示浏览器轨道和服务器轨道的进度
- 或者统一显示为"处理中"直到双轨都完成

### 步骤4: 添加转码失败处理
**优先级**: P1
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 素材卡片显示错误状态
- 提供重试转码的按钮
- 显示失败原因

### 步骤5: WebSocket状态可视化
**优先级**: P2
**文件**: `frontend/src/components/EditScreen.tsx`

**修改内容**:
- 显示连接状态指示器
- 断开时提示用户

### 步骤6: 清理未使用的ClientMaterialUploader组件
**优先级**: P2
**文件**: `frontend/src/components/ClientMaterialUploader.tsx`

**修改内容**:
- 确认组件未被使用后删除
- 或者整合到EditScreen中

## 技术实现要点

### 状态管理
- 使用 `transcodingMaterials` Set 跟踪正在转码的素材
- 使用 `transcodeProgress` Map 存储每个素材的转码进度
- WebSocket 接收实时进度更新

### UI组件
- 使用 Lucide React 图标库显示状态图标
- 使用 Tailwind CSS 进行样式设计
- 保持与现有设计风格一致

### 错误处理
- 转码失败时显示错误信息
- 提供重试机制
- 记录错误日志

## 预期效果

1. 用户可以清晰看到每个素材的转码状态
2. 上传和转码进度更加透明
3. 转码失败时可以及时处理
4. 整体用户体验提升

## 相关文件

- `frontend/src/components/EditScreen.tsx` - 主要修改文件
- `frontend/src/components/ClientMaterialUploader.tsx` - 待清理文件
- `backend/routes/upload.py` - 后端上传接口
- `backend/websocket.py` - WebSocket通知
