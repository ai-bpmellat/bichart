"""Feature poll HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules.identity.session import current_user
from modules.polls import service as poll_service

router = APIRouter(tags=["polls"])


class FeaturePollRequest(BaseModel):
    features: list[str]


@router.get("/api/feature-poll")
def get_feature_poll(request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    return poll_service.get_state(username)


@router.post("/api/feature-poll")
def post_feature_poll(req: FeaturePollRequest, request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    result, err = poll_service.cast_votes(username, req.features)
    if err:
        return JSONResponse(status_code=400, content={"error": err})
    return result
