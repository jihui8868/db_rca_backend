from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SessionCreate(BaseModel):
    db_type: str = "unknown"
    db_connection_string: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    db_type: str
    status: str
    log_filename: Optional[str] = None
    db_connection_string: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
