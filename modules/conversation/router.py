"""Conversation HTTP routes: history, preferences, feedback."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules.conversation.memory import memory
from modules.identity.session import current_user
from modules.llm.provider import VALID_PROVIDERS

router = APIRouter(tags=["conversation"])


class PreferencesRequest(BaseModel):
    provider: Optional[str] = None
    language: Optional[str] = None


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str


@router.post("/api/feedback")
def submit_feedback(req: FeedbackRequest, request: Request):
    session_user = current_user(request.session)
    if not session_user:
        return JSONResponse(status_code=401, content={"error": "Authentication required."})

    rating = (req.rating or "").strip().lower()
    if rating in ("correct", "up", "👍"):
        rating = "up"
    elif rating in ("wrong", "down", "👎"):
        rating = "down"
    else:
        return JSONResponse(status_code=400, content={"error": "Rating must be up or down."})

    ok, err = memory.set_feedback(
        session_user.get("username"),
        req.message_id.strip(),
        rating,
    )
    if not ok:
        return JSONResponse(status_code=404, content={"error": err or "Could not save feedback."})
    return {"ok": True, "rating": rating}


@router.get("/api/history")
def get_history(request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    return {"history": memory.get_context(username=username, n=50)}


@router.get("/api/frequent-questions")
def frequent_questions():
    return {"questions": memory.get_frequent_questions(n=10)}


@router.get("/api/preferences")
def get_preferences(request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    return memory.get_preferences(username)


@router.put("/api/preferences")
def put_preferences(req: PreferencesRequest, request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    provider = req.provider if req.provider in VALID_PROVIDERS else None
    language = req.language if req.language in ("fa", "en") else None
    prefs = memory.set_preferences(username, provider=provider, language=language)
    return {"ok": True, "preferences": prefs}
