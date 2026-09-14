"""User-scoped cover-letter generation and editing."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from auth import decode_token
from crud import get_user_by_id
from dependencies import CurrentUser, DBSession
from models import CoverLetter, Resume, User
from schemas import CoverLetterGenerateRequest, CoverLetterResponse, CoverLetterUpdateRequest
from services.cover_letters import CoverLetterError, generate
from services.internship_index import get_internship
from services.internship_matcher import candidate_data
from services.pdf_generator import generate_cover_letter_pdf

router = APIRouter(prefix="/cover-letters", tags=["Cover Letters"])


def _user_from_header_or_token(db: DBSession, token: str | None, auth_header: str | None) -> User:
    raw_token = None
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header.split(" ", 1)[1]
    elif token:
        raw_token = token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        user_id = decode_token(raw_token, "access")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or no longer exists.")
    return user


@router.post("/generate", response_model=CoverLetterResponse, status_code=status.HTTP_201_CREATED)
def generate_cover_letter(payload: CoverLetterGenerateRequest, current_user: CurrentUser, db: DBSession) -> CoverLetterResponse:
    internship = get_internship(payload.internship_id)
    if not internship:
        raise HTTPException(status_code=404, detail="Internship not found.")
    latest_resume = db.scalar(select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.uploaded_at.desc()))
    candidate = candidate_data(current_user.profile, latest_resume)
    if not any(candidate.values()):
        raise HTTPException(status_code=404, detail="Add a profile or resume before generating a cover letter.")
    user_name = (current_user.profile.full_name if current_user.profile and current_user.profile.full_name else None) or current_user.username
    candidate["name"] = user_name
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
def download_cover_letter(
    letter_id: int,
    db: DBSession,
    token: str | None = Query(None),
    authorization: str | None = Header(None),
) -> PlainTextResponse:
    user = _user_from_header_or_token(db, token, authorization)
    letter = db.scalar(select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.user_id == user.id))
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found.")
    return PlainTextResponse(
        letter.content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="cover-letter-{letter.id}.txt"'},
    )


@router.get("/{letter_id}/download-pdf")
def download_cover_letter_pdf(
    letter_id: int,
    db: DBSession,
    token: str | None = Query(None),
    authorization: str | None = Header(None),
) -> Response:
    user = _user_from_header_or_token(db, token, authorization)
    letter = db.scalar(select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.user_id == user.id))
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found.")
    pdf_bytes = generate_cover_letter_pdf(letter.content, title=f"Cover Letter #{letter.id}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cover-letter-{letter.id}.pdf"'},
    )
