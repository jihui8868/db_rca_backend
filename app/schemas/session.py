from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SessionCreate(BaseModel):
    user_id: str
    data_source_id: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    data_source_id: str
    status: str
    log_filename: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
