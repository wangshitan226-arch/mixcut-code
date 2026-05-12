# OSS存储后的清理策略分析

## 一、当前清理逻辑

### 1.1 触发时机

```
用户修改素材（上传/删除/修改）
    ↓
触发 clear_all_user_renders(user_id)
    ├─ clear_user_render_files(user_id)   # 删除本地文件
    └─ clear_user_renders_db(user_id)     # 删除数据库记录
```

### 1.2 代码位置

| 触发场景 | 文件路径 | 函数 |
|---------|----------|------|
| 生成新组合前 | `backend/routes/generate.py:149` | `clear_user_render_files` |
| 删除素材后 | `backend/routes/materials.py:44` | `clear_all_user_renders` |
| 删除镜头后 | 级联删除 | `clear_all_user_renders` |

### 1.3 设计目的

**核心思想：即用即走，节省服务器资源**
- 用户修改素材 → 旧渲染结果失效 → 立即清理
- 避免磁盘被大量过期视频占满
- 用户需要时重新合成（合成速度快，可接受）

## 二、OSS存储后的变化

### 2.1 存储成本对比

| 方案 | 存储成本 | 清理必要性 |
|------|----------|-----------|
| **本地存储** | 服务器磁盘（贵且有限） | 🔴 必须立即清理 |
| **OSS存储** | ¥0.12/GB/月（便宜且无限） | 🟡 可延迟清理或不清理 |

### 2.2 清理策略选项

#### 选项A：保持现有逻辑（推荐）

```
用户修改素材
    ↓
删除OSS文件 + 删除数据库记录
```

**优点**：
- 逻辑简单，与现有代码一致
- 避免OSS存储费用累积
- 用户无感知（重新合成即可）

**缺点**：
- 用户之前合成的视频丢失
- 如果用户想对比不同素材版本，需要重新合成

**适用场景**：
- 成本敏感
- 用户接受"即用即走"模式
- 合成速度快（用户等待可接受）

#### 选项B：延迟清理（版本保留）

```
用户修改素材
    ↓
保留OSS文件7天
    ↓
7天后自动删除（通过OSS生命周期规则）
```

**优点**：
- 用户有7天时间下载/使用旧版本
- 误操作可恢复
- 自动清理，无需代码实现

**缺点**：
- 增加7天存储成本
- 需要配置OSS生命周期规则
- 数据库记录需要标记"待删除"状态

**适用场景**：
- 用户体验优先
- 合成耗时较长（用户不愿等待）
- 素材修改频率低

#### 选项C：永久保留（版本历史）

```
用户修改素材
    ↓
保留所有历史版本
    ↓
用户可查看/下载历史版本
```

**优点**：
- 完整版本历史
- 用户可随时回溯
- 支持A/B对比测试

**缺点**：
- 存储成本持续累积
- 需要版本管理UI
- 数据库需要存储版本关系

**适用场景**：
- 付费用户功能
- 专业版/企业版
- 素材修改频率极低

## 三、推荐方案：选项A（保持现有逻辑）+ 优化

### 3.1 核心逻辑

**保持"即用即走"理念**，但优化实现：

```python
# backend/utils/oss.py 新增清理函数

def delete_render(self, oss_url: str) -> bool:
    """
    删除OSS上的渲染文件
    
    Args:
        oss_url: OSS文件URL
    
    Returns:
        是否删除成功
    """
    if not self.enabled:
        return False
    
    try:
        # 从URL中提取OSS key
        # URL格式: https://bucket.endpoint/renders/2024/01/15/render_xxx.mp4
        # 或: https://cdn.domain.com/renders/2024/01/15/render_xxx.mp4
        
        if self.cdn_domain and self.cdn_domain in oss_url:
            # CDN URL: https://cdn.domain.com/renders/...
            prefix = f"https://{self.cdn_domain}/"
        else:
            # 直接URL: https://bucket.endpoint/renders/...
            prefix = f"https://{self.bucket_name}.{self.endpoint}/"
        
        if oss_url.startswith(prefix):
            oss_key = oss_url[len(prefix):]
        else:
            # 尝试其他方式解析
            from urllib.parse import urlparse
            parsed = urlparse(oss_url)
            oss_key = parsed.path.lstrip('/')
        
        # 删除OSS文件
        self.bucket.delete_object(oss_key)
        logger.info(f"已删除OSS文件: {oss_key}")
        return True
        
    except Exception as e:
        logger.error(f"删除OSS文件失败: {e}")
        return False
```

### 3.2 修改清理函数

**文件**: `backend/utils/cleanup.py`

```python
"""
Cleanup utilities for user data - OSS版本
"""
import os
import glob
from config import RENDERS_FOLDER
from extensions import db
from models import Render
# 新增导入
from utils.oss import oss_client


def clear_user_render_files(user_id):
    """
    清理用户的渲染文件
    支持本地文件和OSS文件
    """
    deleted_count = 0
    try:
        print(f"[CLEANUP] ====== START clear_user_render_files ======")
        
        # 1. 查询该用户的所有渲染记录
        renders = Render.query.filter_by(user_id=user_id).all()
        print(f"[CLEANUP] 找到 {len(renders)} 个渲染记录")
        
        for render in renders:
            file_path = render.file_path
            if not file_path:
                continue
            
            if file_path.startswith('http'):
                # OSS文件，调用OSS删除
                print(f"[CLEANUP] 删除OSS文件: {file_path}")
                success = oss_client.delete_render(file_path)
                if success:
                    deleted_count += 1
            else:
                # 本地文件，直接删除
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        print(f"[CLEANUP] 删除本地文件: {file_path}")
                    except Exception as e:
                        print(f"[CLEANUP] 删除本地文件失败: {file_path}, {e}")
        
        # 2. 清理可能遗漏的本地文件（兼容旧数据）
        pattern = os.path.join(RENDERS_FOLDER, f'render_combo_{user_id}_*.mp4')
        files = glob.glob(pattern)
        for filepath in files:
            try:
                os.remove(filepath)
                deleted_count += 1
                print(f"[CLEANUP] 删除遗留文件: {filepath}")
            except Exception as e:
                print(f"[CLEANUP] 删除遗留文件失败: {filepath}, {e}")
        
        print(f"[CLEANUP] 总计删除: {deleted_count} 个文件")
        print(f"[CLEANUP] ====== END clear_user_render_files ======")
        
    except Exception as e:
        print(f"[CLEANUP] ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    return deleted_count


def clear_user_renders_db(user_id):
    """Clear all render records from database for a user"""
    try:
        print(f"[CLEANUP] 清理用户 {user_id} 的数据库记录")
        
        count_before = Render.query.filter_by(user_id=user_id).count()
        result = Render.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        
        print(f"[CLEANUP] 删除 {result} 条数据库记录")
    except Exception as e:
        print(f"[CLEANUP] ERROR: {e}")
        db.session.rollback()


def clear_all_user_renders(user_id):
    """
    清理用户的所有渲染（文件 + 数据库）
    支持本地和OSS存储
    """
    print(f"\n{'='*60}")
    print(f"[CLEANUP] 开始清理用户 {user_id} 的所有渲染")
    print(f"{'='*60}")
    
    # 先删除文件（OSS + 本地）
    file_count = clear_user_render_files(user_id)
    
    # 再删除数据库记录
    clear_user_renders_db(user_id)
    
    print(f"[CLEANUP] 完成: 删除 {file_count} 个文件")
    print(f"{'='*60}\n")
```

### 3.3 修改OSS工具类

**文件**: `backend/utils/oss.py`

```python
# 在OSSClient类中添加删除方法

def delete_render(self, oss_url: str) -> bool:
    """
    根据URL删除OSS文件
    
    Args:
        oss_url: 完整的OSS URL
        
    Returns:
        bool: 是否删除成功
    """
    if not self.enabled:
        logger.info("OSS未启用，跳过删除")
        return False
    
    try:
        # 解析URL获取OSS key
        oss_key = self._extract_key_from_url(oss_url)
        if not oss_key:
            logger.error(f"无法从URL解析OSS key: {oss_url}")
            return False
        
        # 删除文件
        self.bucket.delete_object(oss_key)
        logger.info(f"已删除OSS文件: {oss_key}")
        return True
        
    except Exception as e:
        logger.error(f"删除OSS文件失败: {e}")
        return False


def _extract_key_from_url(self, oss_url: str) -> Optional[str]:
    """从OSS URL中提取key"""
    try:
        from urllib.parse import urlparse
        
        parsed = urlparse(oss_url)
        path = parsed.path
        
        # 移除开头的/
        if path.startswith('/'):
            path = path[1:]
        
        return path
        
    except Exception as e:
        logger.error(f"解析OSS URL失败: {e}")
        return None
```

## 四、OSS生命周期配置（可选）

如果担心清理失败导致费用累积，可以配置OSS生命周期规则：

```xml
<!-- OSS生命周期规则 -->
<LifecycleConfiguration>
  <Rule>
    <ID>delete-old-renders</ID>
    <Prefix>renders/</Prefix>
    <Status>Enabled</Status>
    <Expiration>
      <Days>7</Days>
    </Expiration>
  </Rule>
</LifecycleConfiguration>
```

**作用**：
- 自动删除7天前的渲染文件
- 作为兜底策略，防止代码清理失败
- 不影响正常使用的文件（因为会被重新合成）

## 五、总结

### 推荐策略

| 策略 | 实现 | 说明 |
|------|------|------|
| **立即清理** | 修改 `cleanup.py` | 保持现有逻辑，用户无感知 |
| **OSS兜底** | 配置生命周期规则 | 7天自动删除，防止费用累积 |
| **混合模式** | 代码清理 + OSS规则 | 双重保险，成本可控 |

### 改动清单

| 文件 | 改动内容 |
|------|----------|
| `backend/utils/oss.py` | 添加 `delete_render` 方法 |
| `backend/utils/cleanup.py` | 修改清理逻辑，支持OSS删除 |
| OSS控制台 | 配置生命周期规则（可选） |

### 成本对比

假设月合成1000个视频，平均保留1天：

| 策略 | 存储成本 | 说明 |
|------|----------|------|
| 立即清理 | ¥2/月 | 几乎无存储费用 |
| 7天延迟清理 | ¥14/月 | 可接受范围 |
| 永久保留 | ¥60/月+ | 不推荐 |

**结论**：保持"即用即走"策略，修改清理函数支持OSS删除，可选配置生命周期规则兜底。
