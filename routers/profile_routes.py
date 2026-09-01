"""Authenticated, owner-only profile and account endpoints."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError

from crud import create_profile, delete_user, update_profile
from dependencies import CurrentUser, DBSession
from schemas import MessageResponse, ProfileCreate, ProfileResponse, ProfileUpdate

router = APIRouter(tags=["Profile"])
PROFILE_IMAGE_DIRECTORY = Path("uploads/profile_images")
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}


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


@router.post("/profile/picture", response_model=ProfileResponse)
async def upload_profile_picture(current_user: CurrentUser, db: DBSession, file: UploadFile = File(...)) -> ProfileResponse:
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create it first.")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Profile picture must be PNG, JPG, JPEG, or WEBP.")
    content = await file.read()
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Profile picture must be between 1 byte and 2 MB.")
    PROFILE_IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stored = PROFILE_IMAGE_DIRECTORY / f"{uuid4().hex}{suffix}"
    try:
        stored.write_bytes(content)
        current_user.profile.profile_picture_path = str(stored)
        db.commit(); db.refresh(current_user.profile)
        return current_user.profile
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not save profile picture.") from exc


@router.get("/profile/picture")
def get_profile_picture(current_user: CurrentUser) -> FileResponse:
    path = Path(current_user.profile.profile_picture_path) if current_user.profile and current_user.profile.profile_picture_path else None
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Profile picture not found.")
    return FileResponse(path)


@router.delete("/delete-user", response_model=MessageResponse, include_in_schema=False)
@router.delete("/user", response_model=MessageResponse)
def delete_my_account(current_user: CurrentUser, db: DBSession) -> MessageResponse:
    try:
        delete_user(db, current_user)
        return MessageResponse(message="User account, profile, and resume records deleted successfully.")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not delete the user account.") from exc
