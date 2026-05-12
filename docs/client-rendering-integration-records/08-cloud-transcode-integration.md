# 阿里云云端转码集成记录

## 日期
2026-04-25

## 背景
客户端使用 WebCodecs/FFmpeg WASM 转码速度虽快，但质量较差。需要在云端进行高质量转码，以保证 ASR 语音识别和 ICE 模板渲染的输入视频质量。

## 方案设计

### 双轨制策略
| 场景 | 处理方式 | 质量 | 目的 |
|------|----------|------|------|
| **本地预览** | 客户端 WebCodecs 快速转码 | 低（CRF 28, 2Mbps） | 只求快，实时预览 |
| **ASR/ICE渲染** | 阿里云 ICE 云端转码 | 高（CRF 20, 6Mbps） | 专业级质量 |

### 流程
```
用户上传素材
    ↓
客户端快速转码（低质量，仅预览）
    ↓
用户点击"文字快剪"
    ↓
客户端视频上传 OSS
    ↓
提交阿里云云端转码任务（高质量）
    ↓
轮询转码状态
    ↓
转码完成后创建文字快剪草稿
    ↓
ASR 语音识别 / ICE 模板渲染（使用转码后的高质量视频）
```

## 实现修改

### 1. 新增云端转码模块
**文件**: `backend/utils/cloud_transcoder.py`

功能：
- `submit_transcode_job()`: 提交 ICE 转码任务
- `get_transcode_status()`: 查询转码状态
- `transcode_video_sync()`: 同步转码（阻塞等待）
- `submit_transcode_async()`: 异步提交转码
- `get_async_transcode_status()`: 查询异步转码状态

转码参数配置：
```python
quality_configs = {
    'low': {
        'crf': 28, 'preset': 'fast', 
        'video_bitrate': 2000, 'audio_bitrate': 128,
        'width': 720, 'height': 1280
    },
    'medium': {
        'crf': 23, 'preset': 'medium',
        'video_bitrate': 4000, 'audio_bitrate': 192,
        'width': 1080, 'height': 1920
    },
    'high': {
        'crf': 20, 'preset': 'medium',
        'video_bitrate': 6000, 'audio_bitrate': 192,
        'width': 1080, 'height': 1920
    },
    'ultra': {
        'crf': 18, 'preset': 'slow',
        'video_bitrate': 8000, 'audio_bitrate': 256,
        'width': 1080, 'height': 1920
    }
}
```

### 2. 修改创建文字快剪草稿接口
**文件**: `backend/routes/kaipai.py`

在 `create_kaipai_edit` 中添加：
- 检查 `needs_transcode` 参数
- 如果需要转码，提交异步转码任务，返回 `transcoding` 状态
- 前端轮询转码完成后，再次调用创建草稿

### 3. 新增转码状态查询接口
**文件**: `backend/routes/kaipai.py`

新增接口：`GET /api/kaipai/transcode/<task_id>/status`

返回：
```json
{
  "status": "processing|completed|failed",
  "progress": 0-100,
  "output_url": "转码后的URL",
  "error": "错误信息"
}
```

### 4. 修改前端文字快剪入口
**文件**: `frontend/src/components/ResultsScreen.tsx`

在 `handleOpenKaipai` 中：
- 检测是否是客户端渲染视频（Blob URL）
- 传入 `needs_transcode: true`
- 如果返回 `transcoding` 状态，轮询转码进度
- 转码完成后自动创建草稿并打开编辑器

## 阿里云转码优势

1. **专业级编码器**：使用阿里云自研编码器，质量优于浏览器 WebCodecs
2. **CRF 质量控制**：支持 CRF 18-28 范围，CRF 20 为高质量
3. **窄带高清™**：同等画质下节省 20-40% 码率
4. **H.264/H.265/AV1**：多种编码格式可选
5. **音画增强**：支持去噪、色彩增强、超分辨率
6. **不占用服务器资源**：转码在阿里云云端完成

## 成本估算

阿里云 ICE 转码费用：
- 普通转码：约 ¥0.1-0.3/分钟
- 窄带高清 1.0：约 ¥0.15-0.4/分钟
- 窄带高清 2.0：约 ¥0.2-0.5/分钟

示例：5分钟视频，高质量转码，约 ¥1-2

## 测试验证

1. 前端构建成功
2. 需要测试：
   - 客户端渲染视频上传 OSS
   - 云端转码提交成功
   - 轮询转码状态正常
   - 转码完成后 ASR 识别质量提升
   - ICE 模板渲染质量提升

## 后续优化

1. 可以添加转码进度显示 UI
2. 可以支持用户选择转码质量（低/中/高/超清）
3. 可以添加转码失败自动降级机制
