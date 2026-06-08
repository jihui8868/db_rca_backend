# 数据源管理系统

## 概述

新增数据源管理系统，用于集中维护和管理数据库连接配置。每个ChatSession不再直接存储连接信息，而是引用一个DataSource的ID。

## 核心变化

### 1. 新增 DataSource 模型

**文件**: `app/models/data_source.py`

```python
class DataSource(Base):
    __tablename__ = "data_sources"
    
    id = Column(String(36), primary_key=True, default=generate_uuid7)  # UUID7
    name = Column(String(255), nullable=False)
    db_type = Column(String(50), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    database_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(String(10), nullable=False, default="true")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 2. ChatSession 更新

**旧结构**：
```python
class ChatSession(Base):
    db_type = Column(String(50), nullable=False, default="unknown")
    db_connection_string = Column(String(512), nullable=True)
```

**新结构**：
```python
class ChatSession(Base):
    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False)
    data_source = relationship("DataSource", back_populates="chat_sessions")
```

### 3. 数据库关系

```
DataSource (1) ←→ (many) ChatSession
    ↓
ChatSession (1) ←→ (many) ChatMessage
            ↓
             (1) ↔ (1) AnalysisReport
            ↓
             → User
```

## API 端点

### 数据源管理 (`/api/data-sources`)

```
POST   /api/data-sources              # 创建数据源
GET    /api/data-sources              # 列表数据源（分页）
GET    /api/data-sources/{id}         # 获取数据源详情
PUT    /api/data-sources/{id}         # 更新数据源
DELETE /api/data-sources/{id}         # 删除数据源
```

### 会话管理 (`/api/sessions`)

```
POST   /api/sessions                  # 创建会话（现在需要 data_source_id）
GET    /api/sessions                  # 列表会话
GET    /api/sessions/{id}             # 获取会话详情
DELETE /api/sessions/{id}             # 删除会话
```

## 使用示例

### 1. 创建数据源

```bash
POST /api/data-sources
{
  "name": "生产MySQL库",
  "db_type": "mysql",
  "host": "192.168.1.1",
  "port": 3306,
  "username": "admin",
  "password": "secret123",
  "database_name": "prod_db",
  "description": "线上数据库"
}

响应:
{
  "id": "01234567-89ab-cdef-0123-456789abcdef",  # UUID7
  "name": "生产MySQL库",
  "db_type": "mysql",
  "host": "192.168.1.1",
  "port": 3306,
  "username": "admin",
  "password": "secret123",
  "database_name": "prod_db",
  "description": "线上数据库",
  "is_active": "true",
  "created_at": "2026-06-08T10:00:00",
  "updated_at": "2026-06-08T10:00:00"
}
```

### 2. 创建会话并关联数据源

```bash
POST /api/sessions
{
  "user_id": "user-uuid7",
  "data_source_id": "01234567-89ab-cdef-0123-456789abcdef"
}

响应:
{
  "id": "session-uuid7",
  "user_id": "user-uuid7",
  "data_source_id": "01234567-89ab-cdef-0123-456789abcdef",
  "status": "created",
  "log_filename": null,
  "created_at": "2026-06-08T10:00:00",
  "updated_at": "2026-06-08T10:00:00"
}
```

### 3. 列表数据源

```bash
GET /api/data-sources?skip=0&limit=10

响应:
{
  "data_sources": [
    {
      "id": "...",
      "name": "生产MySQL库",
      "db_type": "mysql",
      ...
    }
  ],
  "total": 1
}
```

## 文件清单

### 新建文件

- ✅ `app/models/data_source.py` - DataSource 模型
- ✅ `app/crud/data_source.py` - DataSource CRUD 操作
- ✅ `app/schemas/data_source.py` - DataSource API Schemas
- ✅ `app/router/data_sources.py` - DataSource API 路由

### 修改文件

- ✅ `app/models/chat_session.py` - 添加 data_source_id 外键
- ✅ `app/models/__init__.py` - 导入 DataSource
- ✅ `app/schemas/session.py` - 更新 SessionCreate/SessionResponse
- ✅ `app/crud/session.py` - 使用 data_source_id
- ✅ `app/router/chat.py` - 从 data_source 获取连接信息
- ✅ `main.py` - 注册 data_sources 路由

## 优势

1. **配置复用**：多个会话可复用同一数据源配置
2. **统一管理**：数据库连接信息集中管理，易于更新
3. **权限控制**：可在数据源级别进行访问控制
4. **审计追踪**：完整的数据源创建/修改日志
5. **支持多数据库**：同时支持多个数据库连接
6. **灵活扩展**：可添加更多连接参数（连接池、超时等）

## 字段说明

### DataSource

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID7 | 数据源唯一ID |
| name | String | 数据源名称（用于识别） |
| db_type | String | 数据库类型（mysql/postgresql/oracle等） |
| host | String | 数据库主机名或IP地址 |
| port | Integer | 数据库端口号 |
| username | String | 数据库用户名 |
| password | String | 数据库密码 |
| database_name | String | 数据库名称 |
| description | Text | 描述信息 |
| is_active | String | 是否激活（true/false） |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### ChatSession

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID7 | 会话ID |
| user_id | UUID7 | 用户ID（FK） |
| data_source_id | UUID7 | 数据源ID（FK） |
| status | String | 会话状态 |
| log_filename | String | 日志文件名 |
| log_filepath | String | 日志文件路径 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

## 数据迁移（如有现有数据）

如果存在旧的 ChatSession 数据需要迁移：

```sql
-- 如果存在旧的 chat_sessions 数据（带有 db_type 和 db_connection_string）
-- 需要手动迁移到 DataSource 表
-- 这通常需要应用程序逻辑来解析连接字符串或从其他来源获取连接参数

-- 示例：将旧数据迁移到新的 DataSource
-- 假设原有连接字符串为 mysql://user:pass@host:port/db 格式

INSERT INTO data_sources (id, name, db_type, host, port, username, password, database_name, is_active)
VALUES (
  '<uuid7>',
  'Migrated_Source',
  'mysql',
  '192.168.1.1',
  3306,
  'admin',
  'password',
  'database_name',
  'true'
);

-- 然后更新 chat_sessions
UPDATE chat_sessions
SET data_source_id = '<uuid7>'
WHERE id = '<session_id>';
```

## 后续扩展建议

1. **连接池管理**：在 DataSource 中配置连接池参数
2. **连接测试**：添加测试连接的 API 端点
3. **凭证加密**：对 connection_string 进行加密存储
4. **访问权限**：基于 RBAC 的数据源访问控制
5. **监控告警**：数据源连接状态监控
