# DataSource 参数化设计

## 设计原则

DataSource 模型采用参数化设计，维护独立的连接参数，而不是直接存储连接字符串。这样可以：

1. **参数分离** - 每个连接参数独立存储和管理
2. **灵活生成** - 根据数据库类型动态生成连接字符串
3. **易于维护** - 单个参数的更新无需重新拼接字符串
4. **安全存储** - 支持后续的加密和权限控制

## 字段说明

### 连接参数字段

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `host` | String | 数据库主机名或IP地址 | `192.168.1.1` 或 `db.example.com` |
| `port` | Integer | 数据库服务端口 | `3306` (MySQL)、`5432` (PostgreSQL) |
| `username` | String | 数据库用户名 | `admin`、`root` |
| `password` | String | 数据库密码 | `secret123` |
| `database_name` | String | 数据库名称 | `production_db`、`test_db` |

### 元数据字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | UUID7 | 数据源唯一标识 |
| `name` | String | 数据源显示名称（用于UI和日志） |
| `db_type` | String | 数据库类型，决定连接字符串格式 |
| `description` | Text | 数据源描述 |
| `is_active` | String | 是否激活（true/false） |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 最后更新时间 |

## 支持的数据库类型

### MySQL

```python
# 参数
{
  "db_type": "mysql",
  "host": "localhost",
  "port": 3306,
  "username": "root",
  "password": "password",
  "database_name": "mydb"
}

# 生成的连接字符串
mysql+pymysql://root:password@localhost:3306/mydb
```

### PostgreSQL

```python
# 参数
{
  "db_type": "postgresql",
  "host": "db.example.com",
  "port": 5432,
  "username": "postgres",
  "password": "secret",
  "database_name": "mydb"
}

# 生成的连接字符串
postgresql://postgres:secret@db.example.com:5432/mydb
```

### Oracle

```python
# 参数
{
  "db_type": "oracle",
  "host": "oracle.example.com",
  "port": 1521,
  "username": "sys",
  "password": "password",
  "database_name": "ORCL"
}

# 生成的连接字符串
oracle://sys:password@oracle.example.com:1521/?service_name=ORCL
```

## 使用流程

### 1. 创建数据源

```bash
POST /api/data-sources
Content-Type: application/json

{
  "name": "生产数据库",
  "db_type": "mysql",
  "host": "prod-db.internal",
  "port": 3306,
  "username": "app_user",
  "password": "secure_password",
  "database_name": "production",
  "description": "线上生产数据库"
}
```

**响应**:
```json
{
  "id": "01abc123-def4-5678-90gh-ijklmnopqrst",
  "name": "生产数据库",
  "db_type": "mysql",
  "host": "prod-db.internal",
  "port": 3306,
  "username": "app_user",
  "password": "secure_password",
  "database_name": "production",
  "description": "线上生产数据库",
  "is_active": "true",
  "created_at": "2026-06-08T10:00:00",
  "updated_at": "2026-06-08T10:00:00"
}
```

### 2. 使用数据源创建会话

```bash
POST /api/sessions
Content-Type: application/json

{
  "user_id": "user-uuid7",
  "data_source_id": "01abc123-def4-5678-90gh-ijklmnopqrst"
}
```

### 3. 内部连接字符串生成

当应用需要连接到数据库时，使用 `build_connection_string()` 函数动态生成连接字符串：

```python
from app.core.utils import build_connection_string

connection_string = build_connection_string(
    db_type="mysql",
    host="prod-db.internal",
    port=3306,
    username="app_user",
    password="secure_password",
    database_name="production"
)

# 结果: mysql+pymysql://app_user:secure_password@prod-db.internal:3306/production
```

## 更新数据源

```bash
PUT /api/data-sources/{id}
Content-Type: application/json

{
  "password": "new_password",
  "is_active": "true"
}
```

只有指定的字段会被更新，其他字段保持不变。

## 实现细节

### 模型定义 (app/models/data_source.py)

```python
class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid7)
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

    chat_sessions = relationship("ChatSession", back_populates="data_source")
```

### Schema 定义 (app/schemas/data_source.py)

```python
class DataSourceCreate(BaseModel):
    name: str
    db_type: str
    host: str
    port: int
    username: str
    password: str
    database_name: str
    description: Optional[str] = None
```

### 工具函数 (app/core/utils.py)

```python
def build_connection_string(
    db_type: str,
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
) -> str:
    """根据数据库类型和参数生成连接字符串"""
    if db_type.lower() == "mysql":
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type.lower() == "postgresql":
        return f"postgresql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type.lower() == "oracle":
        return f"oracle://{username}:{password}@{host}:{port}/?service_name={database_name}"
    else:
        return f"{db_type}://{username}:{password}@{host}:{port}/{database_name}"
```

## 命名规范

遵循 Python 的 snake_case 命名规范：

- `host` - 不是 `hostname` 或 `hostName`
- `port` - 数据库端口
- `username` - 不是 `user` 或 `userName`
- `password` - 不是 `pwd` 或 `pass`
- `database_name` - 不是 `database` 或 `databaseName`

## 安全建议

1. **凭证管理**
   - 考虑在生产环境中加密密码字段
   - 限制 API 响应中密码字段的暴露

2. **访问控制**
   - 在数据源级别实现 RBAC
   - 只允许授权用户查看/修改数据源

3. **审计日志**
   - 记录所有数据源的创建、修改、删除操作
   - 记录谁在何时进行了哪些操作

4. **连接测试**
   - 在创建或修改数据源后测试连接
   - 定期检测数据源的可用性

## 扩展方向

1. **连接池参数** - 在 DataSource 中添加连接池大小、超时等参数
2. **SSL/TLS 支持** - 添加 SSL 证书和相关配置
3. **数据源分类** - 支持为数据源添加标签和分类
4. **连接历史** - 记录每个数据源的连接日志
5. **监控指标** - 收集数据源的连接统计和性能指标
