"""SQLAlchemy database configuration. SQLite is the default for local development."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./resume_parser.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _: object) -> None:
    """Make SQLite enforce the cascade relationships declared in the models."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class used by every database model."""


def apply_safe_schema_updates() -> None:
    """Add new nullable profile columns for existing local SQLite databases.

    SQLAlchemy's create_all creates missing tables but does not alter an existing
    table. This small additive migration preserves existing user and resume data.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return
    additions = {
        "portfolio": "VARCHAR(300)", "college": "VARCHAR(200)", "degree": "VARCHAR(150)",
        "branch": "VARCHAR(150)", "graduation_year": "INTEGER", "profile_picture_path": "VARCHAR(500)",
        "technical_skills": "JSON NOT NULL DEFAULT '[]'", "soft_skills": "JSON NOT NULL DEFAULT '[]'",
        "cgpa": "VARCHAR(50)", "location": "VARCHAR(200)",
        "projects": "JSON NOT NULL DEFAULT '[]'", "certifications": "JSON NOT NULL DEFAULT '[]'",
        "achievements": "JSON NOT NULL DEFAULT '[]'",
    }
    existing = {column["name"] for column in inspect(engine).get_columns("user_profiles")} if inspect(engine).has_table("user_profiles") else set()
    with engine.begin() as connection:
        for column, definition in additions.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE user_profiles ADD COLUMN {column} {definition}"))
