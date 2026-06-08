# 命名统一 - ChatMessage

## 目标
统一 ChatMessage 相关的命名，避免歧义和混淆。

## 改动内容

### 1. Schemas 统一
**旧结构**：
```
app/schemas/message.py
├── MessageResponse (id: int)  ❌ ID类型过时
└── MessageListResponse
```

**新结构**：
```
app/schemas/chat_message.py
├── ChatMessageCreate        # 创建消息请求
├── ChatMessageResponse      # 消息响应 (id: str - UUID7)
└── ChatMessageListResponse  # 消息列表响应
```

**改动**：
- ✅ `message.py` → `chat_message.py` (重命名)
- ✅ `MessageResponse` → `ChatMessageResponse`
- ✅ `MessageListResponse` → `ChatMessageListResponse`
- ✅ `id: int` → `id: str` (UUID7)
- ✅ 添加 `ChatMessageCreate` 用于请求体

### 2. CRUD 统一
**旧结构**：
```
app/crud/message.py
├── create_message()
└── get_messages_by_session()
```

**新结构**：
```
app/crud/chat_message.py  # 重命名以保持一致
├── create_message()
└── get_messages_by_session()
```

**改动**：
- ✅ `message.py` → `chat_message.py` (重命名)
- ✅ 维持所有函数接口不变

### 3. 导入更新
**修改文件**：
- ✅ `app/router/chat.py`
  - `from app.crud import message` → `from app.crud import chat_message`
  - `from app.schemas.message import` → `from app.schemas.chat_message import`
  - 使用 `ChatMessageListResponse` 替代 `MessageListResponse`

## 命名约定说明

现在所有 ChatMessage 相关的代码遵循统一的命名约定：

| 层级 | 命名 | 文件路径 |
|------|------|---------|
| **Model** | `ChatMessage` | `app/models/chat_message.py` |
| **Schema** | `ChatMessageCreate/Response` | `app/schemas/chat_message.py` |
| **CRUD** | `create_message/get_messages_by_session` | `app/crud/chat_message.py` |
| **Router** | 导入上述并暴露端点 | `app/router/chat.py` |

## 优势

1. **一致性**：所有相关文件使用 `chat_message` 命名
2. **清晰性**：避免 `message` vs `chat_message` 的混淆
3. **可维护性**：相关功能聚集在一起，易于查找
4. **类型正确**：Schema 中的 ID 类型现在与模型一致 (UUID7)

## 兼容性

- ✅ 所有 API 端点保持不变
- ✅ CRUD 函数签名保持不变
- ✅ 数据库表结构保持不变
- ✅ 只是内部代码组织的改进

## 受影响的文件

- `app/models/chat_message.py` ✓ 无改动
- `app/schemas/chat_message.py` ✓ 重命名 + 更新
- `app/crud/chat_message.py` ✓ 重命名
- `app/router/chat.py` ✓ 更新导入
- `app/schemas/message.py` ✓ 已删除
- `app/crud/message.py` ✓ 已删除
