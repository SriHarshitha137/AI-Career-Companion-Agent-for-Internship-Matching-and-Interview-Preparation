"""Authenticated, owner-only profile and account endpoints."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError

from auth import decode_token
from crud import create_profile, delete_user, get_user_by_id, update_profile
from dependencies import CurrentUser, DBSession
from models import User, UserProfile
from schemas import MessageResponse, ProfileCreate, ProfileResponse, ProfileUpdate

router = APIRouter(tags=["Profile"])
PROFILE_IMAGE_DIRECTORY = Path("uploads/profile_images")
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}


def _ensure_profile(user: User, db: DBSession) -> UserProfile:
    if not user.profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(user)
    return user.profile


@router.post("/profile", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_my_profile(payload: ProfileCreate, current_user: CurrentUser, db: DBSession) -> ProfileResponse:
    if current_user.profile:
        return update_profile(db, current_user.profile, ProfileUpdate(**payload.model_dump()))
    try:
        return create_profile(db, current_user.id, payload)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create profile.") from exc


@router.get("/profile", response_model=ProfileResponse)
def get_my_profile(current_user: CurrentUser, db: DBSession) -> ProfileResponse:
    return _ensure_profile(current_user, db)


@router.put("/profile", response_model=ProfileResponse)
def update_my_profile(payload: ProfileUpdate, current_user: CurrentUser, db: DBSession) -> ProfileResponse:
    profile = _ensure_profile(current_user, db)
    try:
        return update_profile(db, profile, payload)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update profile.") from exc


@router.post("/profile/picture", response_model=ProfileResponse)
async def upload_profile_picture(current_user: CurrentUser, db: DBSession, file: UploadFile = File(...)) -> ProfileResponse:
    profile = _ensure_profile(current_user, db)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Profile picture must be PNG, JPG, JPEG, or WEBP.")
    content = await file.read()
    if not content or len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Profile picture must be between 1 byte and 5 MB.")
    PROFILE_IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    # Remove old image if present
    if profile.profile_picture_path:
        Path(profile.profile_picture_path).unlink(missing_ok=True)
    stored = PROFILE_IMAGE_DIRECTORY / f"{uuid4().hex}{suffix}"
    try:
        stored.write_bytes(content)
        profile.profile_picture_path = str(stored).replace("\\", "/")
        db.commit()
        db.refresh(profile)
        return profile
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not save profile picture.") from exc


@router.get("/profile/picture")
def get_profile_picture(
    db: DBSession,
    token: str | None = None,
    authorization: str | None = Header(None),
) -> FileResponse:
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ", 1)[1]
    elif token:
        raw_token = token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        user_id = decode_token(raw_token, "access")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc
    user = get_user_by_id(db, user_id)
    if not user or not user.profile or not user.profile.profile_picture_path:
        raise HTTPException(status_code=404, detail="Profile picture not found.")
    path = Path(user.profile.profile_picture_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Profile picture file missing.")
    return FileResponse(path)


@router.delete("/profile/picture", response_model=ProfileResponse)
def delete_profile_picture(current_user: CurrentUser, db: DBSession) -> ProfileResponse:
    profile = _ensure_profile(current_user, db)
    if profile.profile_picture_path:
        Path(profile.profile_picture_path).unlink(missing_ok=True)
        profile.profile_picture_path = None
        db.commit()
        db.refresh(profile)
    return profile


@router.delete("/delete-user", response_model=MessageResponse, include_in_schema=False)
@router.delete("/user", response_model=MessageResponse)
def delete_my_account(current_user: CurrentUser, db: DBSession) -> MessageResponse:
    try:
        delete_user(db, current_user)
        return MessageResponse(message="User account, profile, and resume records deleted successfully.")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not delete the user account.") from exc
