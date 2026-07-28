"""Identity HTTP routes: login, session, user admin CRUD."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from modules.conversation.memory import memory
from modules.identity import users as users_mod
from modules.identity.session import (
    current_user,
    is_admin,
    is_authenticated,
    set_session_user,
    verify_credentials,
)
from shared.paths import STATIC_DIR

router = APIRouter(tags=["identity"])


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha: Optional[bool] = False


class UserCreateRequest(BaseModel):
    username: str
    password: str
    mobile: str = ""
    display_name: str = ""
    role: str = "user"


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    mobile: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


def require_admin(request: Request):
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "Authentication required."})
    if not is_admin(request.session):
        return JSONResponse(status_code=403, content={"error": "Admin privileges required."})
    return None


@router.get("/login")
def login_page(request: Request):
    if is_authenticated(request.session):
        return RedirectResponse(url="/app", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@router.post("/api/login")
def login(req: LoginRequest, request: Request):
    if not req.captcha:
        return JSONResponse(status_code=400, content={"error": "Please confirm you are not a robot."})
    user = verify_credentials(req.username, req.password)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Invalid username or password."})
    set_session_user(request.session, user)
    return {"ok": True, "user": user}


@router.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/api/me")
def me(request: Request):
    user = current_user(request.session)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Not authenticated."})
    prefs = memory.get_preferences(user.get("username"))
    return {**user, "preferences": prefs}


@router.get("/users")
def users_page(request: Request):
    if not is_authenticated(request.session):
        return RedirectResponse(url="/login", status_code=302)
    if not is_admin(request.session):
        return RedirectResponse(url="/app", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "users.html"))


@router.get("/api/users")
def api_list_users(request: Request):
    denied = require_admin(request)
    if denied:
        return denied
    return {"users": users_mod.list_users()}


@router.post("/api/users")
def api_create_user(req: UserCreateRequest, request: Request):
    denied = require_admin(request)
    if denied:
        return denied
    user, err = users_mod.create_user(
        username=req.username,
        password=req.password,
        mobile=req.mobile,
        display_name=req.display_name,
        role=req.role,
    )
    if err:
        return JSONResponse(status_code=400, content={"error": err})
    return {"ok": True, "user": user}


@router.put("/api/users/{user_id}")
def api_update_user(user_id: int, req: UserUpdateRequest, request: Request):
    denied = require_admin(request)
    if denied:
        return denied
    user, err = users_mod.update_user(
        user_id,
        username=req.username,
        password=req.password,
        mobile=req.mobile,
        display_name=req.display_name,
        role=req.role,
        is_active=req.is_active,
    )
    if err:
        status = 404 if err == "User not found." else 400
        return JSONResponse(status_code=status, content={"error": err})
    return {"ok": True, "user": user}


@router.delete("/api/users/{user_id}")
def api_delete_user(user_id: int, request: Request):
    denied = require_admin(request)
    if denied:
        return denied
    me_user = current_user(request.session)
    if me_user and me_user.get("id") == user_id:
        return JSONResponse(status_code=400, content={"error": "You cannot delete your own account."})
    ok, err = users_mod.delete_user(user_id)
    if not ok:
        status = 404 if err == "User not found." else 400
        return JSONResponse(status_code=status, content={"error": err})
    return {"ok": True}
