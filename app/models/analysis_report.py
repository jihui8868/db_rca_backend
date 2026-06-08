from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import generate_uuid7


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid7)
    session_id = Column(String(36), ForeignKey("analysis_sessions.id"), nullable=False, unique=True)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AnalysisSession", back_populates="report")
