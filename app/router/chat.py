from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents import agent_service
from app.core.database import get_db
from app.crud import message as crud_message
from app.crud import session as crud_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.message import MessageListResponse, MessageResponse
from db_adapters import get_adapter

router = APIRouter(tags=["chat"])


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def send_message(session_id: str, body: ChatRequest, db: Session = Depends(get_db)):
    session = crud_session.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    crud_message.create_message(db, session_id, "user", body.message)

    existing_messages = crud_message.get_messages_by_session(db, session_id)
    is_first = len(existing_messages) <= 1

    db_diagnostics = None
    if is_first and session.db_connection_string:
        adapter = get_adapter(session.db_type, session.db_connection_string)
        if adapter and adapter.test_connection():
            db_diagnostics = adapter.get_diagnostics_summary()

    response_text = agent_service.chat(
        session_id=session_id,
        user_message=body.message,
        log_filepath=session.log_filepath,
        log_filename=session.log_filename,
        db_diagnostics=db_diagnostics,
        is_first_message=is_first,
    )

    crud_message.create_message(db, session_id, "assistant", response_text)

    if session.status == "analyzing":
        crud_session.update_session_status(db, session_id, "complete")

    return ChatResponse(role="assistant", content=response_text, session_id=session_id)


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
def get_messages(session_id: str, db: Session = Depends(get_db)):
    session = crud_session.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = crud_message.get_messages_by_session(db, session_id)
    return MessageListResponse(messages=messages)
