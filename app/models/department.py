from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import generate_uuid7


class Department(Base):
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=generate_uuid7)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="department")
