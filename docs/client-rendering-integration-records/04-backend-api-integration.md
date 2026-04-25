# 后端 API 集成记录

## 修改时间
2026-04-25

## 修改文件
- `backend/models.py`
- `backend/routes/upload.py`

## 集成概述
为支持客户端渲染模式，后端需要新增素材元数据接口，并在数据库模型中扩展客户端渲染相关字段。

## 详细修改内容

### 1. 数据库模型扩展（models.py）

**Material 模型新增字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_local` | Boolean | 是否为客户端本地渲染素材 |
| `local_material_id` | String(36) | 客户端本地素材ID（关联本地存储） |
| `width` | Integer | 视频宽度 |
| `height` | Integer | 视频高度 |
| `file_size` | BigInteger | 文件大小（字节） |

**修改代码：**
```python
class Material(db.Model):
    # ... 原有字段 ...
    
    # 客户端渲染相关字段
    is_local = db.Column(db.Boolean, default=False)
    local_material_id = db.Column(db.String(36), nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
```

### 2. 新增元数据上传接口（upload.py）

**`POST /api/materials/metadata`**

**功能：**
- 接收客户端渲染模式下素材的元数据
- 不接收视频文件（视频保留在浏览器本地）
- 保存素材信息到数据库，标记为 `is_local=True`

**请求参数（FormData）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |
| `shot_id` | string | 是 | 镜头ID |
| `material_id` | string | 是 | 客户端生成的素材ID |
| `duration` | string | 否 | 视频时长（秒） |
| `width` | string | 否 | 视频宽度 |
| `height` | string | 否 | 视频高度 |
| `file_size` | string | 否 | 文件大小（字节） |
| `thumbnail` | file | 否 | 缩略图文件 |

**响应数据：**
```json
{
  "id": "素材ID",
  "type": "video",
  "url": "local",
  "thumbnail": "/uploads/thumbnails/xxx_thumb.jpg",
  "duration": "0:30",
  "originalName": "local_video.mp4",
  "is_local": true,
  "transcode_status": "completed",
  "message": "素材元数据已保存（客户端本地渲染）"
}
```

**实现逻辑：**
1. 验证用户和镜头权限
2. 处理缩略图上传（保存到服务器）
3. 创建 Material 记录，标记 `is_local=True`
4. `file_path` 和 `unified_path` 设置为 `'local'`
5. 清除用户的旧渲染结果
6. 返回素材信息

**代码位置：** `backend/routes/upload.py:252-367`

### 3. 数据库迁移说明

由于新增了数据库字段，需要执行数据库迁移：

```bash
# 如果使用 Flask-Migrate
flask db migrate -m "Add client rendering fields to Material"
flask db upgrade

# 或者手动执行 SQL
ALTER TABLE materials ADD COLUMN is_local BOOLEAN DEFAULT FALSE;
ALTER TABLE materials ADD COLUMN local_material_id VARCHAR(36) NULL;
ALTER TABLE materials ADD COLUMN width INTEGER NULL;
ALTER TABLE materials ADD COLUMN height INTEGER NULL;
ALTER TABLE materials ADD COLUMN file_size BIGINT NULL;
```

## 与前端集成

前端 `EditScreen.tsx` 中的 `handleClientSideUpload` 函数会调用此接口：

```typescript
const response = await fetch(`${API_BASE_URL}/api/materials/metadata`, {
  method: 'POST',
  body: formData, // 包含元数据和缩略图
});
```

## 降级策略

如果 `/api/materials/metadata` 接口返回 404（不存在），前端会自动降级到原有的 `/api/upload` 接口：

```typescript
if (!response.ok) {
  console.warn('[ClientRender] 元数据接口不可用，降级到服务器上传');
  await handleServerSideUpload(file, shotId);
  return;
}
```

## 待办事项

- [ ] 执行数据库迁移（添加新字段）
- [ ] 测试元数据接口的完整流程
- [ ] 确保缩略图生成逻辑正确
- [ ] 考虑本地素材的删除逻辑（不需要删除服务器文件）

## 相关文档

- [client-side-rendering-integration.md](../client-side-rendering-integration.md)
- [01-editscreen-integration.md](./01-editscreen-integration.md)
