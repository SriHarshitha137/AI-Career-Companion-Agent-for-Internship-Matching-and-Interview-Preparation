"""User-scoped cover-letter generation and editing."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from dependencies import CurrentUser, DBSession
from models import CoverLetter, Resume
from schemas import CoverLetterGenerateRequest, CoverLetterResponse, CoverLetterUpdateRequest
from services.cover_letters import CoverLetterError, generate
from services.internship_index import get_internship
from services.internship_matcher import candidate_data

router = APIRouter(prefix="/cover-letters", tags=["Cover Letters"])


@router.post("/generate", response_model=CoverLetterResponse, status_code=status.HTTP_201_CREATED)
def generate_cover_letter(payload: CoverLetterGenerateRequest, current_user: CurrentUser, db: DBSession) -> CoverLetterResponse:
    internship = get_internship(payload.internship_id)
    if not internship:
        raise HTTPException(status_code=404, detail="Internship not found.")
    latest_resume = db.scalar(select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.uploaded_at.desc()))
    candidate = candidate_data(current_user.profile, latest_resume)
    if not any(candidate.values()):
        raise HTTPException(status_code=404, detail="Add a profile or resume before generating a cover letter.")
    try:
        letter = CoverLetter(user_id=current_user.id, internship_id=payload.internship_id, content=generate(candidate, internship))
        db.add(letter); db.commit(); db.refresh(letter)
        return letter
    except CoverLetterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("", response_model=list[CoverLetterResponse])
def list_cover_letters(current_user: CurrentUser, db: DBSession) -> list[CoverLetterResponse]:
    return list(db.scalars(select(CoverLetter).where(CoverLetter.user_id == current_user.id).order_by(CoverLetter.updated_at.desc())))


@router.put("/{letter_id}", response_model=CoverLetterResponse)
def update_cover_letter(letter_id: int, payload: CoverLetterUpdateRequest, current_user: CurrentUser, db: DBSession) -> CoverLetterResponse:
    letter = db.scalar(select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.user_id == current_user.id))
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found.")
    letter.content = payload.content
    db.commit(); db.refresh(letter)
    return letter


@router.get("/{letter_id}", response_model=CoverLetterResponse)
def get_cover_letter(letter_id: int, current_user: CurrentUser, db: DBSession) -> CoverLetterResponse:
    letter = db.scalar(select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.user_id == current_user.id))
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found.")
    return letter


@router.get("/{letter_id}/download", response_class=PlainTextResponse)
def download_cover_letter(letter_id: int, current_user: CurrentUser, db: DBSession) -> PlainTextResponse:
    letter = db.scalar(select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.user_id == current_user.id))
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found.")
    return PlainTextResponse(letter.content, headers={"Content-Disposition": f'attachment; filename="cover-letter-{letter.id}.txt"'})
