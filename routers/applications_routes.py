"""User-scoped application tracking endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from dependencies import CurrentUser, DBSession
from models import Application, CoverLetter, Resume
from schemas import ApplicationCreateRequest, ApplicationResponse, ApplicationUpdateRequest, MessageResponse
from services.internship_index import get_internship

router = APIRouter(prefix="/applications", tags=["Applications"])


def _owned_application(application_id: int, user_id: int, db: DBSession) -> Application:
    application = db.scalar(select(Application).where(Application.id == application_id, Application.user_id == user_id))
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")
    return application


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def apply(payload: ApplicationCreateRequest, current_user: CurrentUser, db: DBSession) -> ApplicationResponse:
    try:
        if not get_internship(payload.internship_id):
            raise HTTPException(status_code=404, detail="Internship not found in the knowledge base.")
        if payload.resume_id and not db.scalar(select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == current_user.id)):
            raise HTTPException(status_code=404, detail="Resume not found.")
        if payload.cover_letter_id and not db.scalar(select(CoverLetter).where(CoverLetter.id == payload.cover_letter_id, CoverLetter.user_id == current_user.id)):
            raise HTTPException(status_code=404, detail="Cover letter not found.")
        application = Application(user_id=current_user.id, **payload.model_dump())
        db.add(application); db.commit(); db.refresh(application)
        return application
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="You have already applied to this internship.") from exc


@router.get("", response_model=list[ApplicationResponse])
def list_applications(current_user: CurrentUser, db: DBSession) -> list[ApplicationResponse]:
    return list(db.scalars(select(Application).where(Application.user_id == current_user.id).order_by(Application.applied_at.desc())))


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: int, current_user: CurrentUser, db: DBSession) -> ApplicationResponse:
    return _owned_application(application_id, current_user.id, db)


@router.patch("/{application_id}", response_model=ApplicationResponse)
def update_application(application_id: int, payload: ApplicationUpdateRequest, current_user: CurrentUser, db: DBSession) -> ApplicationResponse:
    application = _owned_application(application_id, current_user.id, db)
    application.status = payload.status
    db.commit(); db.refresh(application)
    return application


@router.post("/{application_id}/withdraw", response_model=ApplicationResponse)
def withdraw_application(application_id: int, current_user: CurrentUser, db: DBSession) -> ApplicationResponse:
    application = _owned_application(application_id, current_user.id, db)
    if application.status in {"Accepted", "Rejected", "Withdrawn"}:
        raise HTTPException(status_code=409, detail="This application cannot be withdrawn.")
    application.status, application.withdrawn_at = "Withdrawn", datetime.now(timezone.utc)
    db.commit(); db.refresh(application)
    return application
