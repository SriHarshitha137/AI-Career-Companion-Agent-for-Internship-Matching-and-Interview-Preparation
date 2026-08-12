"""Small, reusable database operations used by the API routers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import hash_password
from models import Resume, User, UserProfile
from schemas import ProfileCreate, ProfileUpdate, RegisterRequest


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, payload: RegisterRequest) -> User:
    user = User(username=payload.username, email=str(payload.email).lower(), hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_profile(db: Session, user_id: int, payload: ProfileCreate) -> UserProfile:
    profile = UserProfile(user_id=user_id, **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, profile: UserProfile, payload: ProfileUpdate) -> UserProfile:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


def create_resume(db: Session, **fields: object) -> Resume:
    resume = Resume(**fields)  # type: ignore[arg-type]
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def update_password(db: Session, user: User, password: str) -> None:
    user.hashed_password = hash_password(password)
    db.commit()


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()
