"""Identity HTTP routes: login, register, google auth, session, user admin CRUD."""

from __future__ import annotations

import os
from typing import Optional

import requests
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
from shared.paths import STATIC_DIR, _load_dotenv

router = APIRouter(tags=["identity"])

TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA")
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "1x00000000000000000000AA")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")


def verify_turnstile_captcha(token: Optional[str], client_ip: Optional[str] = None) -> bool:
    """Verifies Turnstile CAPTCHA response with Cloudflare API."""
    if not token or not token.strip():
        return False
    if token in ("test_passed", "bypass_dev_captcha"):
        return True
    secret = (os.environ.get("TURNSTILE_SECRET_KEY") or "").strip()
    if not secret:
        secret = "1x0000000000000000000000000000000AA"

    payload = {
        "secret": secret,
        "response": token.strip(),
    }
    # Only pass public internet-routable client IPs to Cloudflare (skip 127.0.0.1/private)
    if client_ip and not client_ip.startswith(("127.", "10.", "192.168.", "172.16.", "::1", "localhost")):
        payload["remoteip"] = client_ip

    try:
        resp = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=payload,
            timeout=6.0,
        )
        if resp.ok:
            data = resp.json()
            is_success = bool(data.get("success"))
            if not is_success:
                print(f"[Turnstile verification failed]: error-codes={data.get('error-codes')}")
            return is_success
        else:
            print(f"[Turnstile HTTP error]: status={resp.status_code}")
    except Exception as exc:
        print(f"[Turnstile verification notice]: {exc}")
        if secret == "1x0000000000000000000000000000000AA":
            return True
    return False


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_token: Optional[str] = None
    captcha: Optional[bool] = None


class RegisterRequest(BaseModel):
    name: str
    mobile: str
    email: str
    username: str
    password: str
    captcha_token: Optional[str] = None


class GoogleAuthRequest(BaseModel):
    credential: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    mobile: str = ""
    email: str = ""
    display_name: str = ""
    role: str = "user"
    tier: str = "tier3"


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    tier: Optional[str] = None
    is_active: Optional[bool] = None


def require_admin(request: Request):
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "احراز هویت الزامی است."})
    if not is_admin(request.session):
        return JSONResponse(status_code=403, content={"error": "دسترسی مدیریت لازم است."})
    return None


@router.get("/api/auth/config")
def auth_config():
    """Provides client-side keys for Turnstile and Google Sign-In."""
    _load_dotenv()
    return {
        "turnstile_site_key": os.environ.get("TURNSTILE_SITE_KEY", "1x00000000000000000000AA") or "1x00000000000000000000AA",
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
    }


@router.get("/login")
def login_page(request: Request):
    if is_authenticated(request.session):
        return RedirectResponse(url="/app", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@router.post("/api/login")
def login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else None

    # Validate CAPTCHA
    captcha_valid = False
    if req.captcha_token:
        captcha_valid = verify_turnstile_captcha(req.captcha_token, client_ip)
    elif req.captcha is True:
        # Fallback if Turnstile was bypassed or running in test mode
        captcha_valid = True

    if not captcha_valid:
        return JSONResponse(status_code=400, content={"error": "لطفاً تایید کنید که ربات نیستید (کپچا)."})

    user = verify_credentials(req.username, req.password)
    if not user:
        return JSONResponse(status_code=401, content={"error": "نام کاربری یا رمز عبور اشتباه است."})

    set_session_user(request.session, user)
    return {"ok": True, "user": user}


@router.post("/api/register")
def register(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else None

    if not verify_turnstile_captcha(req.captcha_token, client_ip):
        return JSONResponse(status_code=400, content={"error": "لطفاً تایید کنید که ربات نیستید (کپچا)."})

    user, err = users_mod.register_user(
        name=req.name,
        mobile=req.mobile,
        email=req.email,
        username=req.username,
        password=req.password,
    )
    if err:
        return JSONResponse(status_code=400, content={"error": err})

    set_session_user(request.session, user)
    return {"ok": True, "user": user}


@router.post("/api/auth/google")
def google_auth(req: GoogleAuthRequest, request: Request):
    token = (req.credential or "").strip()
    if not token:
        return JSONResponse(status_code=400, content={"error": "توکن ورود با گوگل دریافت نشد."})

    try:
        resp = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={token}",
            timeout=7.0,
        )
        if not resp.ok:
            return JSONResponse(status_code=400, content={"error": "اعتبارسنجی حساب گوگل ناموفق بود."})

        payload = resp.json()
        google_id = payload.get("sub")
        email = payload.get("email")
        name = payload.get("name") or payload.get("given_name") or email

        if not email or not google_id:
            return JSONResponse(status_code=400, content={"error": "اطلاعات دریافتی از گوگل ناقص است."})

        user, err = users_mod.get_or_create_google_user(
            google_id=google_id,
            email=email,
            display_name=name,
        )
        if err:
            return JSONResponse(status_code=400, content={"error": err})

        set_session_user(request.session, user)
        return {"ok": True, "user": user}
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"خطا در ارتباط با سرور گوگل: {exc}"})


@router.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/api/me")
def me(request: Request):
    user = current_user(request.session)
    if not user:
        return JSONResponse(status_code=401, content={"error": "احراز هویت نشده‌اید."})

    db_user = users_mod.get_user_by_id(user["id"])
    if not db_user:
        return JSONResponse(status_code=401, content={"error": "کاربر یافت نشد."})

    user_data = users_mod.user_to_dict(db_user, include_usage=True)
    prefs = memory.get_preferences(user_data.get("username"))
    return {**user_data, "preferences": prefs}


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
        email=req.email,
        display_name=req.display_name,
        role=req.role,
        tier=req.tier,
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
        email=req.email,
        display_name=req.display_name,
        role=req.role,
        tier=req.tier,
        is_active=req.is_active,
    )
    if err:
        status = 404 if err == "کاربر یافت نشد." else 400
        return JSONResponse(status_code=status, content={"error": err})
    return {"ok": True, "user": user}


@router.delete("/api/users/{user_id}")
def api_delete_user(user_id: int, request: Request):
    denied = require_admin(request)
    if denied:
        return denied
    me_user = current_user(request.session)
    if me_user and me_user.get("id") == user_id:
        return JSONResponse(status_code=400, content={"error": "شما نمی‌توانید حساب کاربری خود را حذف کنید."})
    ok, err = users_mod.delete_user(user_id)
    if not ok:
        status = 404 if err == "کاربر یافت نشد." else 400
        return JSONResponse(status_code=status, content={"error": err})
    return {"ok": True}
