from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import generate_uuid7


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid7)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    db_type = Column(String(50), nullable=False, default="unknown")
    status = Column(String(20), nullable=False, default="created")
    log_filename = Column(String(255), nullable=True)
    log_filepath = Column(String(512), nullable=True)
    db_connection_string = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    report = relationship("AnalysisReport", back_populates="session", uselist=False, cascade="all, delete-orphan")
