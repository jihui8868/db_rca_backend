from datetime import datetime

from pydantic import BaseModel


class ChatMessageCreate(BaseModel):
    role: str
    content: str


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]
