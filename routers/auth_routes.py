"""Authentication and password-management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth import create_access_token, create_reset_token, decode_token, verify_password
from crud import create_user, get_user_by_email, get_user_by_username, update_password
from dependencies import CurrentUser, DBSession
from models import User
from schemas import (
    ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, MessageResponse,
    RegisterRequest, ResetPasswordRequest, TokenResponse, UserResponse,
)

router = APIRouter(tags=["Authentication"])


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    return current_user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DBSession) -> UserResponse:
    if get_user_by_email(db, str(payload.email)) or get_user_by_username(db, payload.username):
        raise HTTPException(status_code=409, detail="A user with this email or username already exists.")
    try:
        return create_user(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with this email or username already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create user.") from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DBSession) -> TokenResponse:
    user = get_user_by_email(db, str(payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive.")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/logout", response_model=MessageResponse)
def logout(_: CurrentUser) -> MessageResponse:
    # JWTs are stateless: the client must discard its token. A token blacklist is needed for server revocation.
    return MessageResponse(message="Logged out successfully. Discard the access token on the client.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: DBSession) -> MessageResponse:
    user = get_user_by_email(db, str(payload.email))
    # Do not reveal whether an email is registered. In a real system email this token instead.
    response = MessageResponse(message="If the email exists, a reset token has been created.")
    if user:
        response.reset_token = create_reset_token(user.id)  # Development-only replacement for email delivery.
    return response


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: DBSession) -> MessageResponse:
    try:
        user_id = decode_token(payload.reset_token, "reset")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    update_password(db, user, payload.new_password)
    return MessageResponse(message="Password reset successfully.")


@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, current_user: CurrentUser, db: DBSession) -> MessageResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    update_password(db, current_user, payload.new_password)
    return MessageResponse(message="Password changed successfully.")
