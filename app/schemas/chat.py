from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str
    session_id: str
