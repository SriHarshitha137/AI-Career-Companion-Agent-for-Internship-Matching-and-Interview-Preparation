"""Protected API routes for AI-Powered Interview Preparation Agent."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select

from dependencies import CurrentUser, DBSession
from models import InterviewDocument, InterviewMessage, InterviewSession
from schemas import (
    InterviewChatRequest,
    InterviewChatResponse,
    InterviewDocumentResponse,
    InterviewMessageResponse,
    InterviewQuestionsRequest,
    InterviewQuestionsResponse,
    InterviewRoadmapRequest,
    InterviewRoadmapResponse,
    InterviewRoleRecommendationResponse,
    InterviewSessionCreateRequest,
    InterviewSessionResponse,
    InterviewSessionUpdateRequest,
    InterviewSkillGapRequest,
    InterviewSkillGapResponse,
    InterviewStatusResponse,
    InterviewStrongestSkillsResponse,
)
from services.interview_prep_service import (
    InterviewPrepError,
    chat_with_agent,
    extract_resume_profile,
    generate_interview_questions,
    generate_roadmap,
    generate_skill_gap_and_path,
    get_latest_user_resume,
    get_strongest_skills,
    process_interview_document,
    recommend_roles,
)

router = APIRouter(prefix="/interview-prep", tags=["Interview Preparation"])

UPLOADS_DIRECTORY = Path("uploads/interview_docs")
MAX_DOCUMENT_BYTES = int(os.getenv("MAX_DOC_BYTES", str(10 * 1024 * 1024)))
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx"}


@router.get("/status", response_model=InterviewStatusResponse)
def get_interview_status(current_user: CurrentUser, db: DBSession) -> InterviewStatusResponse:
    """Check whether the authenticated user has a parsed resume and return candidate overview."""
    resume = get_latest_user_resume(db, current_user.id)
    if not resume or not resume.parsed_json:
        return InterviewStatusResponse(
            has_resume=False,
            message="Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
        )

    profile = extract_resume_profile(resume)
    # Generate default role recommendations if skills present
    default_roles: list[str] = []
    if profile.get("technical_skills"):
        try:
            rec_result = recommend_roles(profile)
            default_roles = rec_result.get("roles", [])
        except Exception:
            pass

    return InterviewStatusResponse(
        has_resume=True,
        resume_id=resume.id,
        candidate_name=profile.get("full_name"),
        technical_skills=profile.get("technical_skills", []),
        recommended_roles=default_roles,
        projects_count=len(profile.get("projects", [])),
    )


@router.post("/recommend-roles", response_model=InterviewRoleRecommendationResponse)
def get_role_recommendations(current_user: CurrentUser, db: DBSession) -> InterviewRoleRecommendationResponse:
    """Analyze the candidate's parsed resume and recommend suitable internship roles."""
    resume = get_latest_user_resume(db, current_user.id)
    if not resume or not resume.parsed_json:
        raise HTTPException(
            status_code=400,
            detail="Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
        )
    profile = extract_resume_profile(resume)
    try:
        result = recommend_roles(profile)
        return InterviewRoleRecommendationResponse(**result)
    except InterviewPrepError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/strongest-skills", response_model=InterviewStrongestSkillsResponse)
def get_candidate_strongest_skills(current_user: CurrentUser, db: DBSession) -> InterviewStrongestSkillsResponse:
    """Identify candidate's strongest skills with resume-grounded evidence."""
    resume = get_latest_user_resume(db, current_user.id)
    if not resume or not resume.parsed_json:
        raise HTTPException(
            status_code=400,
            detail="Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
        )
    profile = extract_resume_profile(resume)
    try:
        result = get_strongest_skills(profile)
        return InterviewStrongestSkillsResponse(**result)
    except InterviewPrepError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/questions", response_model=InterviewQuestionsResponse)
def get_questions(
    payload: InterviewQuestionsRequest, current_user: CurrentUser, db: DBSession
) -> InterviewQuestionsResponse:
    """Generate technical, HR, or project-based questions tailored to resume & role."""
    resume = get_latest_user_resume(db, current_user.id)
    if not resume or not resume.parsed_json:
        raise HTTPException(
            status_code=400,
            detail="Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
        )
    profile = extract_resume_profile(resume)
    try:
        result = generate_interview_questions(
            profile=profile,
            category=payload.category,
            role=payload.role,
            project_name=payload.project_name,
        )
        return InterviewQuestionsResponse(**result)
    except InterviewPrepError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/roadmap", response_model=InterviewRoadmapResponse)
def get_roadmap(
    payload: InterviewRoadmapRequest, current_user: CurrentUser, db: DBSession
) -> InterviewRoadmapResponse:
    """Generate structured interview preparation roadmap for the selected role."""
    resume = get_latest_user_resume(db, current_user.id)
    profile = extract_resume_profile(resume) if resume else {}
    result = generate_roadmap(profile, payload.role)
    return InterviewRoadmapResponse(**result)


@router.post("/skill-gap", response_model=InterviewSkillGapResponse)
def get_skill_gap(
    payload: InterviewSkillGapRequest, current_user: CurrentUser, db: DBSession
) -> InterviewSkillGapResponse:
    """Identify current skills, skills to improve, and missing skills for role."""
    resume = get_latest_user_resume(db, current_user.id)
    if not resume or not resume.parsed_json:
        raise HTTPException(
            status_code=400,
            detail="Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
        )
    profile = extract_resume_profile(resume)
    try:
        result = generate_skill_gap_and_path(profile, payload.role)
        return InterviewSkillGapResponse(**result)
    except InterviewPrepError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# ----------------------------------------------------------------------
# Session Management
# ----------------------------------------------------------------------

@router.get("/sessions", response_model=list[InterviewSessionResponse])
def list_sessions(current_user: CurrentUser, db: DBSession) -> list[InterviewSessionResponse]:
    """List authenticated user's interview preparation sessions."""
    return list(
        db.scalars(
            select(InterviewSession)
            .where(InterviewSession.user_id == current_user.id)
            .order_by(InterviewSession.updated_at.desc())
        )
    )


@router.post("/sessions", response_model=InterviewSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: InterviewSessionCreateRequest, current_user: CurrentUser, db: DBSession
) -> InterviewSessionResponse:
    """Explicitly create a fresh interview chat session (+ New Chat)."""
    title = payload.title or "Interview Prep Session"
    session = InterviewSession(
        user_id=current_user.id,
        title=title,
        selected_role=payload.selected_role,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=list[InterviewMessageResponse])
def get_session_messages(
    session_id: int, current_user: CurrentUser, db: DBSession
) -> list[InterviewMessageResponse]:
    """Retrieve all messages for a specific session owned by user."""
    session = db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return list(
        db.scalars(
            select(InterviewMessage)
            .where(InterviewMessage.session_id == session.id)
            .order_by(InterviewMessage.created_at)
        )
    )


@router.put("/sessions/{session_id}/role", response_model=InterviewSessionResponse)
def update_session_role(
    session_id: int, payload: InterviewSessionUpdateRequest, current_user: CurrentUser, db: DBSession
) -> InterviewSessionResponse:
    """Update active role or title on an interview session."""
    session = db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    if payload.selected_role is not None:
        session.selected_role = payload.selected_role
    if payload.title is not None:
        session.title = payload.title
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", response_model=dict)
def delete_session(session_id: int, current_user: CurrentUser, db: DBSession) -> dict:
    """Delete an interview preparation session and its messages."""
    session = db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    db.delete(session)
    db.commit()
    return {"message": "Interview session deleted successfully."}


# ----------------------------------------------------------------------
# Document Upload & Management
# ----------------------------------------------------------------------

@router.post("/documents/upload", response_model=InterviewDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(..., description="A PDF or DOCX preparation document, syllabus, or guide."),
) -> InterviewDocumentResponse:
    """Upload and index a PDF/DOCX document for RAG-based interview Q&A."""
    original_filename = file.filename or "interview_document"
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only .pdf and .docx files are accepted.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(file_bytes) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Document exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit.",
        )

    UPLOADS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{suffix}"
    stored_path = UPLOADS_DIRECTORY / stored_filename

    try:
        stored_path.write_bytes(file_bytes)
        raw_text, chunks = process_interview_document(file_bytes, original_filename)

        doc = InterviewDocument(
            user_id=current_user.id,
            filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(stored_path),
            file_type=suffix,
            extracted_text=raw_text,
            chunks=chunks,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        return InterviewDocumentResponse(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            chunk_count=len(doc.chunks),
            created_at=doc.created_at,
        )
    except InterviewPrepError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Document processing failed.") from exc


@router.get("/documents", response_model=list[InterviewDocumentResponse])
def list_documents(current_user: CurrentUser, db: DBSession) -> list[InterviewDocumentResponse]:
    """List authenticated user's uploaded interview documents."""
    docs = list(
        db.scalars(
            select(InterviewDocument)
            .where(InterviewDocument.user_id == current_user.id)
            .order_by(InterviewDocument.created_at.desc())
        )
    )
    return [
        InterviewDocumentResponse(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            chunk_count=len(d.chunks),
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.delete("/documents/{document_id}", response_model=dict)
def delete_document(document_id: int, current_user: CurrentUser, db: DBSession) -> dict:
    """Delete an uploaded interview document."""
    doc = db.scalar(
        select(InterviewDocument).where(
            InterviewDocument.id == document_id,
            InterviewDocument.user_id == current_user.id,
        )
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    Path(doc.file_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully."}


# ----------------------------------------------------------------------
# Interactive Chat Endpoint
# ----------------------------------------------------------------------

@router.post("/chat", response_model=InterviewChatResponse)
def interview_chat(
    payload: InterviewChatRequest, current_user: CurrentUser, db: DBSession
) -> InterviewChatResponse:
    """Grounded conversational agent with conversational memory, RAG, and safety guardrails."""
    # 1. Resolve or create session
    session = None
    if payload.session_id:
        session = db.scalar(
            select(InterviewSession).where(
                InterviewSession.id == payload.session_id,
                InterviewSession.user_id == current_user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found.")
    else:
        title = payload.question[:50].strip() or "Interview Prep Session"
        session = InterviewSession(
            user_id=current_user.id,
            title=title,
            selected_role=payload.selected_role,
        )
        db.add(session)
        db.flush()

    if payload.selected_role and not session.selected_role:
        session.selected_role = payload.selected_role

    # 2. Retrieve session history for conversational memory
    prior_messages = list(
        db.scalars(
            select(InterviewMessage)
            .where(InterviewMessage.session_id == session.id)
            .order_by(InterviewMessage.created_at)
        )
    )
    history = [{"role": msg.role, "content": msg.content} for msg in prior_messages]
    # Append current turn to history context
    history.append({"role": "user", "content": payload.question})

    # 3. Retrieve latest resume profile
    resume = get_latest_user_resume(db, current_user.id)
    profile = extract_resume_profile(resume) if resume else {}

    # 4. Retrieve document if attached
    document = None
    if payload.document_id:
        document = db.scalar(
            select(InterviewDocument).where(
                InterviewDocument.id == payload.document_id,
                InterviewDocument.user_id == current_user.id,
            )
        )

    # 5. Execute agent
    answer_text, sources, is_product, is_out_of_scope = chat_with_agent(
        question=payload.question,
        profile=profile,
        history=history,
        selected_role=session.selected_role,
        document=document,
    )

    # 6. Persist message turn in database
    now = datetime.now(timezone.utc)
    session.updated_at = now
    if session.title in {"Interview Prep Session", "New Chat"} and len(payload.question) > 3:
        session.title = payload.question[:50].strip()

    metadata = {
        "sources": sources,
        "selected_role": session.selected_role,
        "document_id": payload.document_id,
    }

    user_msg = InterviewMessage(
        session_id=session.id,
        role="user",
        content=payload.question,
        context_metadata=None,
        created_at=now,
    )
    assistant_msg = InterviewMessage(
        session_id=session.id,
        role="assistant",
        content=answer_text,
        context_metadata=metadata,
        created_at=now,
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()

    return InterviewChatResponse(
        session_id=session.id,
        answer=answer_text,
        selected_role=session.selected_role,
        sources=sources,
        question=payload.question,
        is_product_redirect=is_product,
        is_out_of_scope=is_out_of_scope,
    )
