from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents import agent_service
from app.core.database import get_db
from app.crud import report as crud_report
from app.crud import session as crud_session
from app.schemas.report import ReportResponse

router = APIRouter(tags=["reports"])


@router.get("/sessions/{session_id}/report", response_model=ReportResponse)
def get_report(session_id: str, db: Session = Depends(get_db)):
    session = crud_session.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    report = crud_report.get_report_by_session(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated")
    return report


@router.post("/sessions/{session_id}/report/generate", response_model=ReportResponse)
def generate_report(session_id: str, db: Session = Depends(get_db)):
    session = crud_session.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    content = agent_service.generate_report(session_id)

    severity = "unknown"
    lower = content.lower()
    for level in ("critical", "high", "medium", "low"):
        if level in lower:
            severity = level
            break

    lines = content.split("\n")
    summary_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            summary_lines.append(stripped)
        if len(summary_lines) >= 2:
            break
    summary = " ".join(summary_lines) if summary_lines else None

    report = crud_report.create_or_update_report(
        db=db,
        session_id=session_id,
        content=content,
        summary=summary,
        severity=severity,
    )
    return report
