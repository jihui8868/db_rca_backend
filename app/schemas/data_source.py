from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DataSourceCreate(BaseModel):
    name: str
    db_type: str
    host: str
    port: int
    username: str
    password: str
    database_name: str
    description: Optional[str] = None


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[str] = None


class DataSourceResponse(BaseModel):
    id: str
    name: str
    db_type: str
    host: str
    port: int
    username: str
    password: str
    database_name: str
    description: Optional[str] = None
    is_active: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataSourceListResponse(BaseModel):
    data_sources: list[DataSourceResponse]
    total: int
