import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.crud import session as crud_session

router = APIRouter(tags=["upload"])


@router.post("/sessions/{session_id}/upload")
def upload_log(session_id: str, file: UploadFile, db: Session = Depends(get_db)):
    session = crud_session.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    upload_dir = Path(settings.upload_dir) / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = file.filename or "upload.log"
    filepath = upload_dir / filename

    content = file.file.read()
    filepath.write_bytes(content)

    crud_session.update_session_log(db, session_id, filename, str(filepath))

    return {
        "session_id": session_id,
        "filename": filename,
        "size": len(content),
    }
