"""Pydantic schemas shared by the Gemini extractor and final API response."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    """Reject unexpected LLM keys so malformed answers do not silently pass."""

    model_config = ConfigDict(extra="forbid")


class Education(StrictModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    grade: Optional[str] = None


class Experience(StrictModel):
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)


class Project(StrictModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class Certification(StrictModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None
    credential_url: Optional[str] = None


class Publication(StrictModel):
    title: Optional[str] = None
    publisher: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None


class LLMResumeData(StrictModel):
    """The exact JSON contract requested from Gemini."""

    full_name: Optional[str] = None
    professional_summary: Optional[str] = None
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    work_experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    internships: list[Experience] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)


class ContactData(StrictModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None


class FinalResumeData(LLMResumeData):
    """Stable response schema: all requested fields are always present."""

    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None


# The following schemas are for the authenticated API. They are separate from the
# strict Gemini response schemas above because API clients may omit optional fields.
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordBase(BaseModel):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_needs_letter_and_digit(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one letter and one number.")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_needs_letter_and_digit(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("New password must contain at least one letter and one number.")
        return value


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def reset_password_needs_letter_and_digit(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("New password must contain at least one letter and one number.")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str
    # Exposed only for local development because this starter project has no email provider.
    reset_token: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime


class ProfileBase(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    bio: str | None = None
    linkedin: str | None = Field(default=None, max_length=300)
    github: str | None = Field(default=None, max_length=300)
    portfolio: str | None = Field(default=None, max_length=300)
    college: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=150)
    branch: str | None = Field(default=None, max_length=150)
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    skills: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    bio: str | None = None
    linkedin: str | None = Field(default=None, max_length=300)
    github: str | None = Field(default=None, max_length=300)
    portfolio: str | None = Field(default=None, max_length=300)
    college: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=150)
    branch: str | None = Field(default=None, max_length=150)
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    skills: list[str] | None = None
    technical_skills: list[str] | None = None
    soft_skills: list[str] | None = None
    education: list[dict[str, Any]] | None = None
    experience: list[dict[str, Any]] | None = None


class ProfileResponse(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    profile_picture_path: str | None = None


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    stored_filename: str
    parsed_json: dict[str, Any]
    uploaded_at: datetime


class MatchRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)


class InternshipRecommendation(BaseModel):
    internship_id: str
    title: str
    company: str
    description: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    eligibility: str | None = None
    location: str | None = None
    duration: str | None = None
    work_mode: str | None = None
    stipend: str | None = None
    application_url: str | None = None
    match_score: int
    overall_match_percentage: int
    semantic_similarity: int
    skill_match_percentage: int
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    reason: str


class MatchResponse(BaseModel):
    candidate_skills: list[str] = Field(default_factory=list)
    recommendations: list[InternshipRecommendation] = Field(default_factory=list)


class IngestionResponse(BaseModel):
    indexed: bool
    internships: int
    chunks: int


class CoverLetterGenerateRequest(BaseModel):
    internship_id: str = Field(min_length=1, max_length=100)


class CoverLetterUpdateRequest(BaseModel):
    content: str = Field(min_length=20, max_length=10000)


class CoverLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    internship_id: str
    content: str
    file_path: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationCreateRequest(BaseModel):
    internship_id: str = Field(min_length=1, max_length=100)
    resume_id: int | None = None
    cover_letter_id: int | None = None


class ApplicationUpdateRequest(BaseModel):
    status: str = Field(pattern="^(Applied|Under Review|Shortlisted|Interview|Accepted|Rejected)$")


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    internship_id: str
    resume_id: int | None
    cover_letter_id: int | None
    status: str
    applied_at: datetime
    updated_at: datetime
    withdrawn_at: datetime | None


class AssistantChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    session_id: int | None = None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    created_at: datetime


class AssistantChatResponse(BaseModel):
    session_id: int
    answer: str
    sources: list[str] = Field(default_factory=list)
