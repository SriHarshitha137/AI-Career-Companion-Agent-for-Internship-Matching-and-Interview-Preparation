"""Authenticated, owner-only profile and account endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from crud import create_profile, delete_user, update_profile
from dependencies import CurrentUser, DBSession
from schemas import MessageResponse, ProfileCreate, ProfileResponse, ProfileUpdate

router = APIRouter(tags=["Profile"])


@router.post("/profile", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_my_profile(payload: ProfileCreate, current_user: CurrentUser, db: DBSession) -> ProfileResponse:
    if current_user.profile:
        raise HTTPException(status_code=409, detail="Profile already exists. Use PUT /profile to update it.")
    try:
        return create_profile(db, current_user.id, payload)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create profile.") from exc


@router.get("/profile", response_model=ProfileResponse)
def get_my_profile(current_user: CurrentUser) -> ProfileResponse:
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return current_user.profile


@router.put("/profile", response_model=ProfileResponse)
def update_my_profile(payload: ProfileUpdate, current_user: CurrentUser, db: DBSession) -> ProfileResponse:
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create it first.")
    try:
        return update_profile(db, current_user.profile, payload)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update profile.") from exc


@router.delete("/delete-user", response_model=MessageResponse, include_in_schema=False)
@router.delete("/user", response_model=MessageResponse)
def delete_my_account(current_user: CurrentUser, db: DBSession) -> MessageResponse:
    try:
        delete_user(db, current_user)
        return MessageResponse(message="User account, profile, and resume records deleted successfully.")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not delete the user account.") from exc
