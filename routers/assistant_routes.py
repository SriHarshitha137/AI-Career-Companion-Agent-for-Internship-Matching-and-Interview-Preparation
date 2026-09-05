"""Authenticated, persisted InternSphere product assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from dependencies import CurrentUser, DBSession
from models import ChatMessage, ChatSession
from schemas import (
    AssistantChatRequest, AssistantChatResponse,
    ChatMessageResponse, ChatSessionCreateRequest, ChatSessionResponse,
)
from services.product_assistant import answer

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreateRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> ChatSessionResponse:
    """Explicitly start a fresh, empty chat session."""
    title = payload.title or "New Career Chat"
    session = ChatSession(user_id=current_user.id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/chat", response_model=AssistantChatResponse)
def chat(payload: AssistantChatRequest, current_user: CurrentUser, db: DBSession) -> AssistantChatResponse:
    session = None
    if payload.session_id:
        session = db.scalar(
            select(ChatSession).where(
                ChatSession.id == payload.session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found.")
    else:
        title = payload.question[:50].strip() or "Career Chat"
        session = ChatSession(user_id=current_user.id, title=title)
        db.add(session)
        db.flush()

    # Retrieve prior messages for THIS session only to provide conversation memory
    prior_messages = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
        )
    )
    history = [{"role": msg.role, "content": msg.content} for msg in prior_messages]
    # Append current question to history context
    history.append({"role": "user", "content": payload.question})

    response_text, sources = answer(payload.question, history=history)

    now = datetime.now(timezone.utc)
    session.updated_at = now
    if session.title == "New Career Chat":
        session.title = payload.question[:50].strip() or "Career Chat"

    user_msg = ChatMessage(session_id=session.id, role="user", content=payload.question, created_at=now)
    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=response_text, created_at=now)
    db.add_all([user_msg, assistant_msg])
    db.commit()

    return AssistantChatResponse(
        session_id=session.id,
        answer=response_text,
        sources=sources,
        question=payload.question,
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
def sessions(current_user: CurrentUser, db: DBSession) -> list[ChatSessionResponse]:
    return list(
        db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == current_user.id)
            .order_by(ChatSession.updated_at.desc())
        )
    )


@router.get("/sessions/{session_id}", response_model=list[ChatMessageResponse])
def messages(session_id: int, current_user: CurrentUser, db: DBSession) -> list[ChatMessageResponse]:
    session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
        )
    )


@router.delete("/sessions/{session_id}", response_model=dict)
def delete_session(session_id: int, current_user: CurrentUser, db: DBSession) -> dict:
    session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    db.delete(session)
    db.commit()
    return {"message": "Chat session deleted successfully."}
