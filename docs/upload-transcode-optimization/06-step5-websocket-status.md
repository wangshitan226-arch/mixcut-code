# 优化步骤5: WebSocket状态可视化

## 修改文件
- `frontend/src/components/EditScreen.tsx`

## 修改内容

### 1. 添加WebSocket状态管理
```typescript
const [wsStatus, setWsStatus] = useState<'connected' | 'disconnected' | 'connecting'>('connecting');
```

### 2. 更新WebSocket事件监听
```typescript
socket.on('connect', () => {
  console.log('[WebSocket] Connected:', socket.id);
  setWsStatus('connected');
  // ...
});

socket.on('disconnect', () => {
  console.log('[WebSocket] Disconnected');
  setWsStatus('disconnected');
});

socket.on('connect_error', (error) => {
  console.error('[WebSocket] Connection error:', error);
  setWsStatus('disconnected');
});
```

### 3. 添加状态指示器UI
在页面标题旁边添加一个小圆点指示器：

```typescript
{/* WebSocket状态指示器 */}
{wsStatus === 'connected' ? (
  <span className="w-2 h-2 rounded-full bg-green-500" title="实时连接正常" />
) : wsStatus === 'connecting' ? (
  <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" title="连接中..." />
) : (
  <span className="w-2 h-2 rounded-full bg-red-500" title="实时连接断开，使用轮询模式" />
)}
```

## 状态说明

| 状态 | 颜色 | 说明 |
|------|------|------|
| 已连接 | 绿色 | WebSocket连接正常，可以实时接收转码通知 |
| 连接中 | 黄色（闪烁） | 正在尝试连接WebSocket |
| 已断开 | 红色 | WebSocket连接断开，将使用轮询模式获取状态 |

## 用户体验改进

1. **连接状态透明**: 用户可以知道实时通知是否可用
2. **故障感知**: WebSocket断开时用户会知道正在使用轮询模式
3. **无干扰**: 使用小圆点指示器，不占用太多空间
4. **悬停提示**: 鼠标悬停时显示详细说明
