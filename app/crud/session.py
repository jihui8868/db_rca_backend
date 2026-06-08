from typing import Optional

from sqlalchemy.orm import Session

from app.models.analysis_session import AnalysisSession
from app.schemas.session import SessionCreate


def create_session(db: Session, data: SessionCreate) -> AnalysisSession:
    session = AnalysisSession(
        db_type=data.db_type,
        db_connection_string=data.db_connection_string,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> Optional[AnalysisSession]:
    return db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()


def list_sessions(db: Session) -> list[AnalysisSession]:
    return db.query(AnalysisSession).order_by(AnalysisSession.created_at.desc()).all()


def update_session_status(db: Session, session_id: str, status: str) -> Optional[AnalysisSession]:
    session = get_session(db, session_id)
    if session:
        session.status = status
        db.commit()
        db.refresh(session)
    return session


def update_session_log(db: Session, session_id: str, filename: str, filepath: str) -> Optional[AnalysisSession]:
    session = get_session(db, session_id)
    if session:
        session.log_filename = filename
        session.log_filepath = filepath
        session.status = "analyzing"
        db.commit()
        db.refresh(session)
    return session


def delete_session(db: Session, session_id: str) -> bool:
    session = get_session(db, session_id)
    if session:
        db.delete(session)
        db.commit()
        return True
    return False
