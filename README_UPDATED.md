# DB-RCA 后端更新说明

## 最近更新（V1.1.0）

### 核心改动

#### 1. 数据库升级至PostgreSQL
- 从SQLite迁移到PostgreSQL
- 配置分离为独立参数，便于灵活配置

#### 2. UUID7 全面应用
- 所有表的主键ID由UUID4改为UUID7（使用uuid6包）
- UUID7提供更好的时间有序性和数据库性能

#### 3. 用户和部门管理系统
- **Department模型** - 组织部门管理
- **User模型** - 用户账户管理，关联部门
- **AnalysisSession增强** - 添加user_id，建立用户与分析会话的关联

### 新增API端点

#### 部门管理
```
POST   /api/departments              # 创建部门
GET    /api/departments              # 列表部门（分页）
GET    /api/departments/{dept_id}    # 获取部门详情
PUT    /api/departments/{dept_id}    # 更新部门
DELETE /api/departments/{dept_id}    # 删除部门
```

#### 用户管理
```
POST   /api/users                    # 创建用户
GET    /api/users                    # 列表用户（分页）
GET    /api/users/{user_id}          # 获取用户详情
PUT    /api/users/{user_id}          # 更新用户
DELETE /api/users/{user_id}          # 删除用户
```

### 配置变更

#### 环境变量
**旧配置（弃用）：**
```
DATABASE_URL=sqlite:///./db_rca.db
```

**新配置（推荐）：**
```
DB_HOST=192.168.2.133
DB_PORT=15432
DB_USERNAME=postgres
DB_PASSWORD=111111
DB_NAME=db_rca
```

所有参数都可通过`.env`文件或环境变量覆盖。

### 安装步骤

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境变量
# 复制 .env.example 为 .env 并填入实际配置
cp .env.example .env

# 3. 启动应用
uvicorn main:app --reload
```

### 创建分析会话

**现在需要提供 user_id**：
```json
POST /api/sessions
{
  "user_id": "01234567-89ab-cdef-0123-456789abcdef",
  "db_type": "mysql",
  "db_connection_string": "mysql://user:pass@localhost:3306/db"
}
```

### 数据库表结构

```
departments
├── id (UUID7)
├── name
├── description
├── created_at
└── updated_at

users
├── id (UUID7)
├── username
├── email
├── password_hash
├── full_name
├── department_id (FK)
├── is_active
├── created_at
└── updated_at

analysis_sessions
├── id (UUID7)
├── user_id (FK)
├── db_type
├── status
├── log_filename
├── log_filepath
├── db_connection_string
├── created_at
└── updated_at

chat_messages
├── id (UUID7)
├── session_id (FK)
├── role
├── content
└── created_at

analysis_reports
├── id (UUID7)
├── session_id (FK)
├── content
├── summary
├── severity
└── created_at
```

## 迁移说明

详见 `MIGRATION_GUIDE.md` 获取完整的迁移说明。

## 更新日志

详见 `CHANGELOG_SUMMARY.md` 获取完整的改动清单。
