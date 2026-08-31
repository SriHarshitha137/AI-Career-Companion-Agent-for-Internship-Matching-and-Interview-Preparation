"""Authenticated internship ingestion and RAG matching endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from dependencies import CurrentUser, DBSession
from models import Resume
from schemas import IngestionResponse, MatchRequest, MatchResponse
from services.internship_index import InternshipIndexError, ingest, search
from services.internship_matcher import candidate_data, candidate_query, match

router = APIRouter(prefix="/internships", tags=["Internships"])


@router.post("/ingest", response_model=IngestionResponse)
def ingest_internships(_: CurrentUser, force: bool = False) -> IngestionResponse:
    try:
        return IngestionResponse(**ingest(force=force))
    except InternshipIndexError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/match", response_model=MatchResponse)
def find_matches(payload: MatchRequest, current_user: CurrentUser, db: DBSession) -> MatchResponse:
    latest_resume = db.scalar(select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.uploaded_at.desc()))
    candidate = candidate_data(current_user.profile, latest_resume)
    query = candidate_query(candidate)
    if not query:
        raise HTTPException(status_code=404, detail="Add a profile or upload a resume before finding matches.")
    try:
        retrieved = search(query, payload.top_k)
        return MatchResponse(candidate_skills=candidate["skills"], recommendations=match(candidate, retrieved))
    except InternshipIndexError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
