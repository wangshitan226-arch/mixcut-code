# MixCut 架构重构方案

## 1. 当前问题分析

### 1.1 痛点总结
- **Project 概念冗余**：业务逻辑是"单次混剪任务"，用户用完即走，不需要项目管理
- **ProjectID 混乱**：localStorage 保存的 ID 在服务器上可能不存在，导致 404 错误
- **数据隔离缺失**：多用户共用数据，容易"串台"
- **代码复杂度高**：Project → Shots → Materials 三层关系，增加 bug 概率

### 1.2 业务本质
```
用户打开 → 上传素材 → 生成组合 → 下载视频 → 下次重新开始
```

**结论：不需要 Project，但需要 UserID 做数据隔离**

---

## 2. 重构目标

1. **删除 Project 层**，简化架构
2. **引入 UserID**，实现数据隔离
3. **保持匿名用户**，无需登录注册
4. **降低代码复杂度**，减少 bug

---

## 3. 新架构设计

### 3.1 数据模型

```
User (匿名用户)
  └── Shots (镜头)
        └── Materials (素材)
  └── Renders (生成的视频)
```

### 3.2 数据库表结构

```sql
-- Users 表（匿名用户）
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,  -- UUID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type VARCHAR(20) DEFAULT 'anonymous'
);

-- Shots 表（直接关联 user）
CREATE TABLE shots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL,
    sequence INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Materials 表
CREATE TABLE materials (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    shot_id INTEGER NOT NULL,
    type VARCHAR(20) NOT NULL,  -- 'video' | 'image'
    original_name VARCHAR(255),
    file_path VARCHAR(500) NOT NULL,
    unified_path VARCHAR(500),
    thumbnail_path VARCHAR(500) NOT NULL,
    duration VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shot_id) REFERENCES shots(id) ON DELETE CASCADE
);

-- Renders 表（生成的视频）
CREATE TABLE renders (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    combo_index INTEGER NOT NULL,
    material_ids TEXT NOT NULL,  -- JSON array
    tag VARCHAR(50),
    duration VARCHAR(10),
    duration_seconds FLOAT,
    thumbnail VARCHAR(500),
    file_path VARCHAR(500),
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

---

## 4. API 变更

### 4.1 删除的接口
```
DELETE /api/projects
DELETE /api/projects/{id}
DELETE /api/projects/{id}/shots
```

### 4.2 新增的接口
```
# 用户管理
POST   /api/users              # 创建匿名用户
GET    /api/users/{id}         # 获取用户信息

# Shots（添加 user_id 参数）
GET    /api/shots?user_id=xxx
POST   /api/shots              # body: {user_id, name}
DELETE /api/shots/{id}

# Upload（添加 user_id 参数）
POST   /api/upload             # form: {user_id, shot_id, file, quality}

# Generate（添加 user_id 参数）
POST   /api/generate           # body: {user_id}
GET    /api/renders?user_id=xxx
```

### 4.3 修改的接口
```
# 所有接口都添加 user_id 参数或从 body/form 中获取
# 查询时只返回该 user_id 的数据
```

---

## 5. 前端变更

### 5.1 State 管理
```typescript
// 原来
const [projectId, setProjectId] = useState<number | null>(null);

// 新
const [userId, setUserId] = useState<string>(() => {
  // 从 localStorage 获取或生成新的
  return localStorage.getItem('mixcut_user_id') || generateUUID();
});
```

### 5.2 初始化逻辑
```typescript
// 原来：initProject - 复杂的项目创建/恢复逻辑

// 新：简单的用户初始化
const initUser = async () => {
  const storedUserId = localStorage.getItem('mixcut_user_id');
  
  if (storedUserId) {
    // 检查用户是否存在
    const response = await fetch(`${API_BASE_URL}/api/users/${storedUserId}`);
    if (response.ok) {
      setUserId(storedUserId);
      return;
    }
  }
  
  // 创建新用户
  const response = await fetch(`${API_BASE_URL}/api/users`, {method: 'POST'});
  const user = await response.json();
  setUserId(user.id);
  localStorage.setItem('mixcut_user_id', user.id);
};
```

### 5.3 API 调用
```typescript
// 所有请求都带 user_id
fetch(`${API_BASE_URL}/api/shots?user_id=${userId}`);
fetch(`${API_BASE_URL}/api/upload`, {
  method: 'POST',
  body: formData  // 包含 user_id
});
```

---

## 6. 数据隔离机制

### 6.1 隔离策略
- 每个用户通过 `user_id` 隔离数据
- 所有查询都带 `WHERE user_id = ?`
- 用户只能看到自己的 Shots、Materials、Renders

### 6.2 清理策略
- 用户清缓存 → 生成新 user_id → 旧数据成为"孤儿数据"
- 定期清理：删除 7 天内无关联 user 的 renders 文件
- 或者：保留数据，用户用旧 user_id 可以恢复

---

## 7. 迁移方案

### 7.1 后端迁移步骤
1. 创建新的数据库表结构
2. 实现新的 API 接口
3. 保留旧接口（兼容期）
4. 测试新接口
5. 删除旧接口

### 7.2 前端迁移步骤
1. 添加 user_id 管理逻辑
2. 修改所有 API 调用
3. 删除 project 相关代码
4. 测试完整流程

### 7.3 数据迁移（可选）
```sql
-- 将旧数据迁移到新表
-- 为每个旧 project 创建一个 user
-- 将 shots/materials 关联到新 user
```

---

## 8. 文件结构变更

```
backend/
  app.py                    # 简化后的主文件
  models.py                 # 数据模型（可选拆分）
  routes/
    __init__.py
    users.py               # 用户相关接口
    shots.py               # 镜头相关接口
    materials.py           # 素材相关接口
    renders.py             # 渲染相关接口

frontend/src/
  App.tsx                  # 简化后的主组件
  hooks/
    useUser.ts             # 用户管理 hook
  api/
    client.ts              # API 客户端
```

---

## 9. 优势总结

| 方面 | 原来 | 新方案 |
|------|------|--------|
| 架构层级 | Project → Shots → Materials (3层) | User → Shots → Materials (2层) |
| 数据隔离 | 无 | 有 (user_id) |
| 代码复杂度 | 高 | 低 |
| Bug 概率 | 高 | 低 |
| 用户体验 | 需理解"项目" | 打开即用 |
| 扩展性 | 差 | 好 (后续可添加登录) |

---

## 10. 实施建议

### 阶段 1：快速修复（1天）
- 在现有代码基础上添加 user_id
- 保留 Project 表但不做强制关联
- 让服务器先跑起来

### 阶段 2：完整重构（3-5天）
- 彻底删除 Project
- 重构所有相关代码
- 完整测试

### 阶段 3：优化（1-2天）
- 代码拆分
- 性能优化
- 文档更新

---

## 11. 风险与应对

| 风险 | 应对 |
|------|------|
| 数据丢失 | 提前备份数据库 |
| 功能回归 | 完整测试清单 |
| 用户数据隔离失败 | 严格测试多用户场景 |
| 旧代码残留 | 代码审查 + 清理 |

---

## 12. 结论

**删除 Project，引入 UserID，简化架构，是解决当前混乱的根本方案。**

新架构：
- 更简洁（少一层关系）
- 更可靠（数据隔离）
- 更易维护（代码量少 30%）
- 更易扩展（后续添加登录简单）

建议尽快实施阶段 1，让服务器稳定运行，再逐步完成完整重构。
