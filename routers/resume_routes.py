"""Protected upload endpoint that stores a resume and reuses the existing parsing pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from crud import create_resume
from models import Resume
from dependencies import CurrentUser, DBSession
from main import ResumeProcessingError, parse_resume
from schemas import ResumeResponse

router = APIRouter(prefix="/resume", tags=["Resume"])
UPLOADS_DIRECTORY = Path("uploads")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(..., description="A PDF or DOCX resume, up to 5 MB by default."),
) -> ResumeResponse:
    """Save the original file, parse it with existing modules, then save the JSON result."""
    original_filename = file.filename or "uploaded_resume"
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only .pdf and .docx files are accepted.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")

    UPLOADS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{suffix}"
    stored_path = UPLOADS_DIRECTORY / stored_filename
    try:
        # Persist first so the database can refer to the original received file.
        stored_path.write_bytes(file_bytes)
        parsed_data = parse_resume(file_bytes, original_filename)
        return create_resume(
            db,
            user_id=current_user.id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(stored_path),
            parsed_json=parsed_data,
        )
    except ResumeProcessingError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except OSError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save the uploaded file.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Resume parsed but database storage failed.") from exc


@router.get("", response_model=list[ResumeResponse])
def list_resumes(current_user: CurrentUser, db: DBSession) -> list[ResumeResponse]:
    """List only the authenticated user's uploaded resumes and parsed results."""
    return list(db.scalars(select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.uploaded_at.desc())))


@router.get("/{resume_id}/download")
def download_resume(resume_id: int, current_user: CurrentUser, db: DBSession) -> FileResponse:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id))
    if not resume or not Path(resume.file_path).is_file():
        raise HTTPException(status_code=404, detail="Resume not found.")
    return FileResponse(resume.file_path, filename=resume.original_filename)


@router.post("/{resume_id}/reparse", response_model=ResumeResponse)
def reparse_resume(resume_id: int, current_user: CurrentUser, db: DBSession) -> ResumeResponse:
    """Re-run the original parsing pipeline against a resume the user owns."""
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id))
    if not resume or not Path(resume.file_path).is_file():
        raise HTTPException(status_code=404, detail="Resume not found.")
    try:
        resume.parsed_json = parse_resume(Path(resume.file_path).read_bytes(), resume.original_filename)
        db.commit(); db.refresh(resume)
        return resume
    except ResumeProcessingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not read the stored resume.") from exc
