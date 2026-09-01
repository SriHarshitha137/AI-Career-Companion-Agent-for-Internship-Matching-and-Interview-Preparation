"""Authenticated, persisted InternSphere product assistant."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from dependencies import CurrentUser, DBSession
from models import ChatMessage, ChatSession
from schemas import AssistantChatRequest, AssistantChatResponse, ChatMessageResponse
from services.product_assistant import answer

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


@router.post("/chat", response_model=AssistantChatResponse)
def chat(payload: AssistantChatRequest, current_user: CurrentUser, db: DBSession) -> AssistantChatResponse:
    session = db.scalar(select(ChatSession).where(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)) if payload.session_id else None
    if payload.session_id and not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    if not session:
        session = ChatSession(user_id=current_user.id, title=payload.question[:80])
        db.add(session); db.flush()
    response, sources = answer(payload.question)
    db.add_all([ChatMessage(session_id=session.id, role="user", content=payload.question), ChatMessage(session_id=session.id, role="assistant", content=response)])
    db.commit()
    return AssistantChatResponse(session_id=session.id, answer=response, sources=sources)


@router.get("/sessions", response_model=list[dict])
def sessions(current_user: CurrentUser, db: DBSession) -> list[dict]:
    return [{"id": item.id, "title": item.title, "updated_at": item.updated_at} for item in db.scalars(select(ChatSession).where(ChatSession.user_id == current_user.id).order_by(ChatSession.updated_at.desc()))]


@router.get("/sessions/{session_id}", response_model=list[ChatMessageResponse])
def messages(session_id: int, current_user: CurrentUser, db: DBSession) -> list[ChatMessageResponse]:
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at)))


@router.delete("/sessions/{session_id}", response_model=dict)
def delete_session(session_id: int, current_user: CurrentUser, db: DBSession) -> dict:
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    db.delete(session); db.commit()
    return {"message": "Chat session deleted."}
