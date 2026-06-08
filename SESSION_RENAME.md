# Session 重命名 - AnalysisSession → ChatSession

## 目标
将 `AnalysisSession` 改为 `ChatSession`，以更准确地反映其在系统中的用途（用于聊天交互）。

## 改动内容

### 1. 模型重命名
**旧结构**：
```
app/models/analysis_session.py
├── class AnalysisSession
└── __tablename__ = "analysis_sessions"
```

**新结构**：
```
app/models/chat_session.py
├── class ChatSession
└── __tablename__ = "chat_sessions"
```

**改动**：
- ✅ 文件: `analysis_session.py` → `chat_session.py`
- ✅ 类名: `AnalysisSession` → `ChatSession`
- ✅ 表名: `analysis_sessions` → `chat_sessions`
- ✅ 用户关系: `analysis_sessions` → `chat_sessions`

### 2. 关系更新

#### 2.1 User 模型
```python
# 旧
analysis_sessions = relationship("AnalysisSession", back_populates="user")

# 新
chat_sessions = relationship("ChatSession", back_populates="user")
```

#### 2.2 ChatMessage 模型
```python
# 旧
session_id = Column(String(36), ForeignKey("analysis_sessions.id"), nullable=False)
session = relationship("AnalysisSession", back_populates="messages")

# 新
session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
session = relationship("ChatSession", back_populates="messages")
```

#### 2.3 AnalysisReport 模型
```python
# 旧
session_id = Column(String(36), ForeignKey("analysis_sessions.id"), nullable=False, unique=True)
session = relationship("AnalysisSession", back_populates="report")

# 新
session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, unique=True)
session = relationship("ChatSession", back_populates="report")
```

### 3. 导入和注册更新

**文件**: `app/models/__init__.py`
```python
# 旧
from app.models.analysis_session import AnalysisSession
__all__ = ["Department", "User", "AnalysisSession", "ChatMessage", "AnalysisReport"]

# 新
from app.models.chat_session import ChatSession
__all__ = ["Department", "User", "ChatSession", "ChatMessage", "AnalysisReport"]
```

### 4. CRUD 操作更新

**文件**: `app/crud/session.py`
```python
# 旧
from app.models.analysis_session import AnalysisSession

def create_session(db: Session, data: SessionCreate) -> AnalysisSession:
    session = AnalysisSession(...)

def get_session(db: Session, session_id: str) -> Optional[AnalysisSession]:
    return db.query(AnalysisSession).filter(...)

# 新
from app.models.chat_session import ChatSession

def create_session(db: Session, data: SessionCreate) -> ChatSession:
    session = ChatSession(...)

def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(...)
```

## User ID 关系

ChatSession 保持与 User 的关系，确保每个会话都关联到一个用户：

```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid7)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)  # ✓ 用户关联
    
    user = relationship("User", back_populates="chat_sessions")
```

## 数据库迁移

如果存在现有数据，需要执行以下步骤：

1. 备份现有 `analysis_sessions` 表
2. 创建新的 `chat_sessions` 表（SQLAlchemy 会自动创建）
3. 迁移数据（如有必要）

```sql
-- 可选：手动迁移现有数据
ALTER TABLE analysis_sessions RENAME TO chat_sessions;
ALTER TABLE chat_messages DROP CONSTRAINT chat_messages_session_id_fkey;
ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_session_id_fkey 
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id);
-- ... 其他外键更新
```

## API 端点

所有 API 端点保持不变：

```
POST   /api/sessions              # 创建会话
GET    /api/sessions              # 列表会话
GET    /api/sessions/{session_id} # 获取会话
DELETE /api/sessions/{session_id} # 删除会话
POST   /api/sessions/{session_id}/chat  # 发送消息
GET    /api/sessions/{session_id}/messages  # 获取消息
```

## 数据库表结构

```
chat_sessions
├── id (UUID7 PK)
├── user_id (FK → users.id)  ✓ 关联用户
├── db_type (VARCHAR)
├── status (VARCHAR)
├── log_filename (VARCHAR)
├── log_filepath (VARCHAR)
├── db_connection_string (VARCHAR)
├── created_at (DATETIME)
└── updated_at (DATETIME)

关系:
- chat_sessions (1) ←→ (many) chat_messages
- chat_sessions (1) ←→ (1) analysis_reports
- chat_sessions (many) ←→ (1) users
```

## 优势

1. **名称准确**：`ChatSession` 更准确地反映其用于聊天交互的用途
2. **语义清晰**：与 `ChatMessage` 配对，形成清晰的语义
3. **关系明确**：每个会话都明确关联到一个用户
4. **表名一致**：`chat_sessions` 表名与类名对应

## 受影响的文件

- ✅ `app/models/chat_session.py` (新建)
- ✅ `app/models/user.py` (更新关系)
- ✅ `app/models/chat_message.py` (更新外键)
- ✅ `app/models/analysis_report.py` (更新外键)
- ✅ `app/models/__init__.py` (更新导入)
- ✅ `app/crud/session.py` (更新导入和类型)
- ✅ `app/models/analysis_session.py` (已删除)
