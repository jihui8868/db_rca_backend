from typing import Optional

from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.schemas.session import SessionCreate


def create_session(db: Session, data: SessionCreate) -> ChatSession:
    session = ChatSession(
        user_id=data.user_id,
        data_source_id=data.data_source_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def list_sessions(db: Session) -> list[ChatSession]:
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()


def update_session_status(db: Session, session_id: str, status: str) -> Optional[ChatSession]:
    session = get_session(db, session_id)
    if session:
        session.status = status
        db.commit()
        db.refresh(session)
    return session


def update_session_log(db: Session, session_id: str, filename: str, filepath: str) -> Optional[ChatSession]:
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
