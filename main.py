from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.router import chat, reports, sessions, upload, users, departments

import app.models  # noqa: F401 — registers all ORM models before create_all
Base.metadata.create_all(bind=engine)

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="DB-RCA: Database Root Cause Analysis",
    version="1.0.0",
    description="Multi-agent database fault analysis system",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(departments.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
