"""Chat HTTP routes: generate SQL, run, analyze, discuss, health."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from modules.bi_data.database import SessionLocal
from modules.chat import service as chat_service
from modules.identity.session import current_user
from modules.llm import avalai as avalai_client
from modules.llm import ollama as ollama_client

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = None
    provider: Optional[str] = "avalai"


class RunSqlRequest(BaseModel):
    sql: str
    message: Optional[str] = None
    explanation: Optional[str] = None
    language: Optional[str] = None
    provider: Optional[str] = None


class AnalyzeRequest(BaseModel):
    message: str
    data: list
    language: Optional[str] = None
    provider: Optional[str] = "avalai"


class DiscussRequest(BaseModel):
    message: str
    data: Optional[list] = None
    analysis: Optional[str] = None
    focus: Optional[str] = None
    history: Optional[list] = None
    original_question: Optional[str] = None
    language: Optional[str] = None
    provider: Optional[str] = "avalai"


@router.get("/api/health")
def health():
    status = {"db": "unknown", "ollama": "unknown", "avalai": "unknown"}

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status["db"] = "ok"
    except Exception as e:
        status["db"] = f"error: {e}"

    try:
        ollama_client._post("ping", system="reply with the word pong", temperature=0.0)
        status["ollama"] = "ok"
    except ollama_client.OllamaError as e:
        status["ollama"] = f"error: {e}"

    try:
        avalai_client.check_credit()
        status["avalai"] = "ok"
    except avalai_client.AvalAIError as e:
        status["avalai"] = f"error: {e}"

    overall_ok = status["db"] == "ok"
    return JSONResponse(status_code=200 if overall_ok else 503, content=status)


@router.get("/api/avalai/credit")
def avalai_credit():
    try:
        return avalai_client.check_credit()
    except avalai_client.AvalAIError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


@router.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})

    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    language, provider = chat_service.resolve_language_provider(
        username, language=req.language, provider=req.provider
    )
    result = chat_service.generate_sql(user_question, language, provider)
    if "error" in result:
        return JSONResponse(status_code=result.get("status", 502), content=result)
    return result


@router.post("/api/run_sql")
def run_sql(req: RunSqlRequest, request: Request):
    sql_text = (req.sql or "").strip()
    if not sql_text:
        return JSONResponse(status_code=400, content={"error": "Empty SQL."})

    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    language, provider = chat_service.resolve_language_provider(
        username, language=req.language, provider=req.provider
    )
    user_question = (req.message or "").strip() or "SQL run"
    result = chat_service.run_sql(
        sql_text,
        username=username,
        user_question=user_question,
        explanation=req.explanation or "",
        language=language,
        provider=provider,
    )
    if "error" in result:
        return JSONResponse(status_code=result.get("status", 400), content=result)
    return result


@router.post("/api/analyze")
def analyze(req: AnalyzeRequest, request: Request):
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})
    if not req.data:
        return JSONResponse(status_code=400, content={"error": "No data to analyze."})

    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    language, provider = chat_service.resolve_language_provider(
        username, language=req.language, provider=req.provider
    )
    result = chat_service.analyze(user_question, req.data, language, provider, username)
    if "error" in result:
        return JSONResponse(status_code=result.get("status", 502), content=result)
    return result


@router.post("/api/discuss")
def discuss(req: DiscussRequest, request: Request):
    user_message = (req.message or "").strip()
    if not user_message:
        return JSONResponse(status_code=400, content={"error": "Empty discussion message."})

    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    language, provider = chat_service.resolve_language_provider(
        username, language=req.language, provider=req.provider
    )
    result = chat_service.discuss(
        user_message=user_message,
        data=req.data,
        analysis=req.analysis or "",
        focus=req.focus or "",
        history=req.history,
        original_question=req.original_question or "",
        language=language,
        provider=provider,
    )
    if "error" in result:
        return JSONResponse(status_code=result.get("status", 502), content=result)
    return result
