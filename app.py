"""
app.py
------
Composition root for the BiChart modular monolith.

HTTP surface is assembled from domain module routers:
  identity · chat · conversation · reporting · polls
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from modules.chat.router import router as chat_router
from modules.conversation.router import router as conversation_router
from modules.identity import users as users_mod
from modules.identity.router import router as identity_router
from modules.identity.session import SESSION_SECRET, is_authenticated
from modules.polls.router import router as polls_router
from modules.reporting.router import router as reporting_router
from shared.paths import STATIC_DIR

PUBLIC_PATHS = frozenset({"/", "/login", "/help", "/api/login", "/favicon.ico"})
PUBLIC_PREFIXES = ("/static/",)

app = FastAPI(title="PSP BI Conversational Report Builder")


@app.middleware("http")
async def require_login_middleware(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    if is_authenticated(request.session):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"error": "Authentication required."})
    return RedirectResponse(url="/login", status_code=302)


# SessionMiddleware must be outermost so request.session works in the auth middleware.
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(identity_router)
app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(reporting_router)
app.include_router(polls_router)


@app.on_event("startup")
def _startup_init_users():
    users_mod.init_users_table()


@app.get("/favicon.ico")
def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "favicon-32.png"), media_type="image/png")


@app.get("/")
def landing():
    """Marketing first page (no login required)."""
    return FileResponse(os.path.join(STATIC_DIR, "first.html"))


@app.get("/help")
def help_page():
    """Bilingual system help & documentation page."""
    return FileResponse(os.path.join(STATIC_DIR, "help.html"))


@app.get("/app")
def chat_app(request: Request):
    """Authenticated BI chat UI."""
    if not is_authenticated(request.session):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
