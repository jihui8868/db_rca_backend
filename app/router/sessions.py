from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import session as crud_session
from app.schemas.session import SessionCreate, SessionListResponse, SessionResponse

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionResponse)
def create_session(data: SessionCreate, db: Session = Depends(get_db)):
    return crud_session.create_session(db, data)


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(db: Session = Depends(get_db)):
    sessions = crud_session.list_sessions(db)
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = crud_session.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    success = crud_session.delete_session(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}
