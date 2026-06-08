from typing import Optional

from sqlalchemy.orm import Session

from app.models.analysis_report import AnalysisReport


def get_report_by_session(db: Session, session_id: str) -> Optional[AnalysisReport]:
    return db.query(AnalysisReport).filter(AnalysisReport.session_id == session_id).first()


def create_or_update_report(
    db: Session,
    session_id: str,
    content: str,
    summary: Optional[str] = None,
    severity: Optional[str] = None,
) -> AnalysisReport:
    report = get_report_by_session(db, session_id)
    if report:
        report.content = content
        report.summary = summary
        report.severity = severity
    else:
        report = AnalysisReport(
            session_id=session_id,
            content=content,
            summary=summary,
            severity=severity,
        )
        db.add(report)
    db.commit()
    db.refresh(report)
    return report
