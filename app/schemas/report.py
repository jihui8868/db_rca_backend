from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: int
    session_id: str
    content: str
    summary: Optional[str] = None
    severity: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
