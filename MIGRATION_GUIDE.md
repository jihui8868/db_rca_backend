# 数据库迁移指南

## 改动概述

本次更新包含以下主要改动：

1. **数据库引擎变更**：从SQLite改为PostgreSQL
2. **ID生成方式**：从UUID4改为UUID7（所有模型）
3. **用户管理**：新增User和Department模型
4. **session增强**：AnalysisSession现在包含user_id关联

## 环境变量配置

### 旧配置（SQLite）
```
DATABASE_URL=sqlite:///./db_rca.db
```

### 新配置（PostgreSQL）
将以下变量添加到`.env`文件：
```
DB_HOST=192.168.2.133
DB_PORT=15432
DB_USERNAME=postgres
DB_PASSWORD=111111
DB_NAME=db_rca
```

参考`.env.example`文件了解所有配置选项。

## 安装依赖

```bash
uv sync
```

这将自动安装新增的依赖：
- `uuid6>=1.5.0` - UUID6/UUID7生成
- `email-validator>=2.0.0` - 邮箱验证
- `psycopg2-binary>=2.9` - PostgreSQL驱动

## 数据库初始化

首次运行应用时，SQLAlchemy会自动创建所有表：

```bash
uvicorn main:app --reload
```

数据库表包括：
- `departments` - 部门表
- `users` - 用户表
- `analysis_sessions` - 分析会话表
- `chat_messages` - 聊天消息表
- `analysis_reports` - 分析报告表

## 新增API端点

### 部门管理
- `POST /api/departments` - 创建部门
- `GET /api/departments` - 列表部门
- `GET /api/departments/{dept_id}` - 获取部门详情
- `PUT /api/departments/{dept_id}` - 更新部门
- `DELETE /api/departments/{dept_id}` - 删除部门

### 用户管理
- `POST /api/users` - 创建用户
- `GET /api/users` - 列表用户
- `GET /api/users/{user_id}` - 获取用户详情
- `PUT /api/users/{user_id}` - 更新用户
- `DELETE /api/users/{user_id}` - 删除用户

## 会话创建变更

创建分析会话现在需要提供`user_id`：

### 请求格式
```json
{
  "user_id": "generated-uuid7",
  "db_type": "mysql",
  "db_connection_string": "..."
}
```

## 数据库迁移步骤

如果从旧数据库迁移现有数据，需要按以下步骤进行：

1. 备份现有SQLite数据库
2. 创建新的PostgreSQL数据库
3. 编写迁移脚本转换数据（包括生成UUID7 ID）
4. 更新环境变量指向新数据库
5. 启动应用并验证数据完整性

## UUID7 说明

UUID7是一个基于时间戳的UUID版本，具有以下优势：
- 时间有序，便于索引和排序
- 更好的数据库性能
- 保持UUID的随机性特性

所有新创建的记录都将自动使用UUID7作为主键。
