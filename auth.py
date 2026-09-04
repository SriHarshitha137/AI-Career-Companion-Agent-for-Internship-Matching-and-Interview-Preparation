"""Password hashing and JWT helpers. Secrets are intentionally read from environment variables."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

import config  # noqa: F401  # Load .env before secrets are read.

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-development-secret-before-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "15"))
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "type": "access", "exp": expires_at}, SECRET_KEY, algorithm=ALGORITHM)


def create_reset_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "type": "reset", "exp": expires_at}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> int:
    """Validate signature, expiry, intended use, and the numeric user subject."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise ValueError("incorrect token type")
        return int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid or expired token.") from exc
