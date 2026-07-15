"""
app.py
------
FastAPI application exposing:
    GET  /              -> serves the chat UI (static/index.html)
    POST /api/chat       -> text-to-SQL, safety check, execute (results shown first)
    POST /api/analyze    -> optional Ollama analysis on demand (after results)
    GET  /api/health     -> health check (DB + Ollama reachability)

Pipeline executed by /api/chat, in order:
    1. Call Gemma (ollama_client.generate_sql) with a strict JSON system prompt.
    2. Validate the SQL is read-only SELECT only (sql_safety.validate_select_only).
    3. Execute against SQLite (swappable engine via database.py), capped at sql_safety.MAX_ROWS.
    4. Store the turn in memory (memory_manager) and persist to history.json.
    5. Return {sql, explanation, data} to the frontend (no analysis — user triggers /api/analyze).

Why FastAPI instead of Flask:
    The brief asked for Flask but allowed swapping frameworks if something fits
    better. This pipeline makes two sequential, network-bound calls to Ollama per
    request (SQL generation, then analysis). FastAPI's native async support means
    the server doesn't block its single worker thread waiting on those HTTP calls,
    Pydantic gives free request validation, and you get OpenAPI docs at /docs for
    free, which is handy when testing the API directly during development.
"""

import os
import time
import traceback
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import pandas as pd
from sqlalchemy import text

from database import engine, SessionLocal
import ollama_client
import avalai_client
from sql_safety import validate_select_only, UnsafeSQLError, strip_unrequested_limit, normalize_generated_sql
from memory_manager import memory
from auth import (
    SESSION_SECRET,
    is_admin,
    is_authenticated,
    current_user,
    set_session_user,
    verify_credentials,
)
import users as users_mod

VALID_PROVIDERS = frozenset({"ollama", "avalai"})


def get_llm_client(provider: str):
    if provider == "avalai":
        return avalai_client
    return ollama_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

PUBLIC_PATHS = frozenset({"/", "/login", "/api/login", "/favicon.ico"})
PUBLIC_PREFIXES = ("/static/",)


class RequireLoginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)
        if is_authenticated(request.session):
            return await call_next(request)
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"error": "Authentication required."})
        return RedirectResponse(url="/login", status_code=302)


app = FastAPI(title="PSP BI Conversational Report Builder")
# SessionMiddleware must be outermost so request.session is available in RequireLoginMiddleware.
app.add_middleware(RequireLoginMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def _startup_init_users():
    users_mod.init_users_table()


def require_admin(request: Request):
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "Authentication required."})
    if not is_admin(request.session):
        return JSONResponse(status_code=403, content={"error": "Admin privileges required."})
    return None


# ---------------------------------------------------------------------------
# Schema description given to the LLM so it knows what it can query.
# ---------------------------------------------------------------------------
SCHEMA_DESCRIPTION = """
Tables:

dim_date(date_key INTEGER PK, full_date DATE, day_name TEXT, month_name TEXT,
          year INTEGER, month INTEGER, day INTEGER, is_weekend BOOLEAN, is_holiday BOOLEAN)

dim_customer(customer_id INTEGER PK, customer_name TEXT, access_key TEXT, role TEXT)
  -- the PSP's contracted client company that owns merchants

dim_category(category_id INTEGER PK, category_name TEXT)
  -- standardized Persian merchant verticals; valid category_name values ONLY:
  1 فروشگاه‌های مواد غذایی و سوپرمارکت‌ها
  2 رستوران‌ها، فست‌فودها و کافه‌ها
  3 پوشاک و کیف و کفش
  4 داروخانه‌ها و مراکز درمانی
  5 خدمات پزشکی و آزمایشگاهی
  6 جایگاه‌های سوخت
  7 هتل‌ها و مراکز اقامتی
  8 حمل‌ونقل و تاکسی
  9 آموزشگاه‌ها و مراکز آموزشی
  10 خدمات فنی و تعمیراتی
  11 فروش لوازم خانگی و الکترونیک
  12 طلافروشی و جواهرات
  13 خدمات دولتی و عمومی
  14 خیریه‌ها و سازمان‌های غیرانتفاعی
  15 کسب‌وکارهای اینترنتی و تجارت الکترونیک

dim_merchant(merchant_id INTEGER PK, merchant_name TEXT, merchant_code TEXT,
             mcc TEXT, category_id INTEGER FK -> dim_category, category TEXT,
             city TEXT, owner_customer_id INTEGER FK -> dim_customer, is_active BOOLEAN)
  -- category is denormalized copy of dim_category.category_name (Persian)

dim_terminal(terminal_id INTEGER PK, terminal_serial TEXT, merchant_id INTEGER FK -> dim_merchant,
             terminal_type TEXT, install_date DATE, status TEXT)
  -- status values: 'active' or 'inactive' (lowercase)

fact_transactions(transaction_id INTEGER PK, date_key INTEGER FK -> dim_date,
                   terminal_id INTEGER FK -> dim_terminal, merchant_id INTEGER FK -> dim_merchant,
                   transaction_time DATETIME, amount REAL, currency TEXT, status TEXT
                   (approved/declined/reversed), card_pan_masked TEXT, response_code TEXT,
                   settlement_date DATE, channel TEXT (POS/ONLINE/MOBILE))
  -- date_key is INTEGER YYYYMMDD (e.g. 20260319), NOT a SQL date.
  -- NEVER use date(), strftime(), or compare date_key to date('now', ...).
  -- ALWAYS join dim_date and use dim_date.full_date for any date filter or month/year logic.

Notes:
- CRITICAL date rules:
  * Join: JOIN dim_date d ON f.date_key = d.date_key
  * Filter: WHERE d.full_date >= date('now','-6 months')  — NOT f.date_key >= date(...)
  * Month/year: strftime('%Y-%m', d.full_date)  — NOT strftime(..., f.date_key)
  * "yesterday" / "دیروز": WHERE d.full_date = date('now','-1 day')
  * "last month" / "ماه گذشته": WHERE d.full_date >= date('now','start of month','-1 month')
    AND d.full_date < date('now','start of month')
  * Use SQLite modifier 'start of month' — NEVER 'first day of month' (returns NULL in SQLite).
  * Mock data spans full_date 2026-01-01 through 2026-06-22 (about six months).
- Status rules:
  * dim_terminal.status: 'active' / 'inactive' (lowercase) — do not use 'Active'
  * fact_transactions.status: approved / declined / reversed
- merchant_name, customer_name, category, and category_name are in Persian (Farsi).
- For category breakdowns, join dim_merchant to dim_category on category_id,
  or use dim_merchant.category directly (same Persian labels).
- Always join through merchant_id when filtering by merchant.
- Do not add LIMIT unless the user asks for a specific number of rows (e.g. top 10).
"""


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = None  # "fa" or "en"; defaults to ollama_client.RESPONSE_LANGUAGE
    provider: Optional[str] = "avalai"  # "ollama" or "avalai"


class AnalyzeRequest(BaseModel):
    message: str
    data: list
    language: Optional[str] = None
    provider: Optional[str] = "avalai"


class PreferencesRequest(BaseModel):
    provider: Optional[str] = None
    language: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/login")
def login_page(request: Request):
    if is_authenticated(request.session):
        return RedirectResponse(url="/app", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    if not req.captcha:
        return JSONResponse(status_code=400, content={"error": "Please confirm you are not a robot."})
    user = verify_credentials(req.username, req.password)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Invalid username or password."})
    set_session_user(request.session, user)
    return {"ok": True, "user": user}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    user = current_user(request.session)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Not authenticated."})
    prefs = memory.get_preferences(user.get("username"))
    return {**user, "preferences": prefs}


@app.get("/users")
def users_page(request: Request):
    if not is_authenticated(request.session):
        return RedirectResponse(url="/login", status_code=302)
    if not is_admin(request.session):
        return RedirectResponse(url="/app", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "users.html"))


@app.get("/api/users")
def api_list_users(request: Request):
    denied = require_admin(request)
    if denied:
        return denied
    return {"users": users_mod.list_users()}


@app.post("/api/users")
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


@app.put("/api/users/{user_id}")
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


@app.delete("/api/users/{user_id}")
def api_delete_user(user_id: int, request: Request):
    denied = require_admin(request)
    if denied:
        return denied
    # Prevent self-delete
    me_user = current_user(request.session)
    if me_user and me_user.get("id") == user_id:
        return JSONResponse(status_code=400, content={"error": "You cannot delete your own account."})
    ok, err = users_mod.delete_user(user_id)
    if not ok:
        status = 404 if err == "User not found." else 400
        return JSONResponse(status_code=status, content={"error": err})
    return {"ok": True}


@app.get("/")
def landing():
    """Marketing first page (no login required)."""
    return FileResponse(os.path.join(STATIC_DIR, "first.html"))


@app.get("/app")
def chat_app(request: Request):
    """Authenticated BI chat UI."""
    if not is_authenticated(request.session):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
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


@app.get("/api/avalai/credit")
def avalai_credit():
    """Server-side proxy for AvalAI credit balance (API key never sent to browser)."""
    try:
        return avalai_client.check_credit()
    except avalai_client.AvalAIError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})

    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"

    # Prefer request values; fall back to saved per-user preferences; then defaults
    prefs = memory.get_preferences(username)
    language = req.language or prefs.get("language") or ollama_client.RESPONSE_LANGUAGE
    provider = req.provider if req.provider in VALID_PROVIDERS else prefs.get("provider", "avalai")
    if provider not in VALID_PROVIDERS:
        provider = "avalai"
    # Remember model choice for this user's next questions
    memory.set_preferences(username, provider=provider, language=language)

    llm = get_llm_client(provider)
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    def _mark(step: str, started: float) -> None:
        timings[step] = round((time.perf_counter() - started) * 1000, 1)

    # ---- Step 1: Text-to-SQL via selected LLM provider ----
    t = time.perf_counter()
    try:
        sql_result = llm.generate_sql(user_question, SCHEMA_DESCRIPTION, language=language)
        explanation = sql_result.get("explanation", "")
    except Exception as e:
        _mark("sql_generation", t)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=502,
            content={"error": f"SQL generation failed: {e}", "timings": timings},
        )
    _mark("sql_generation", t)

    t = time.perf_counter()
    raw_sql = normalize_generated_sql(strip_unrequested_limit(sql_result["sql"], user_question))
    _mark("sql_normalize", t)

    # ---- Step 2: Safety check (read-only SELECT, no destructive statements) ----
    t = time.perf_counter()
    try:
        safe_sql = validate_select_only(raw_sql)
    except UnsafeSQLError as e:
        _mark("sql_safety", t)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Generated SQL was rejected for safety reasons: {e}",
                "sql": raw_sql,
                "explanation": explanation,
                "timings": timings,
            },
        )
    _mark("sql_safety", t)

    # ---- Step 3: Execute against the DB ----
    t = time.perf_counter()
    try:
        db = SessionLocal()
        try:
            df = pd.read_sql_query(text(safe_sql), db.bind)
        finally:
            db.close()
        records = df.to_dict(orient="records")
    except Exception as e:
        _mark("sql_execution", t)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=400,
            content={
                "error": f"SQL execution failed: {e}",
                "sql": safe_sql,
                "explanation": explanation,
                "timings": timings,
            },
        )
    _mark("sql_execution", t)

    # ---- Step 4: Persist to per-user memory ----
    t = time.perf_counter()
    memory.add_message(
        username=username,
        user_question=user_question,
        sql=safe_sql,
        explanation=explanation,
        row_count=len(records),
        analysis=None,
        provider=provider,
        language=language,
    )
    _mark("memory_save", t)

    timings["total"] = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "sql": safe_sql,
        "explanation": explanation,
        "data": records,
        "row_count": len(records),
        "language": language,
        "provider": provider,
        "timings": timings,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, request: Request):
    """On-demand analysis after results are already shown."""
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})
    if not req.data:
        return JSONResponse(status_code=400, content={"error": "No data to analyze."})

    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    prefs = memory.get_preferences(username)

    language = req.language or prefs.get("language") or ollama_client.RESPONSE_LANGUAGE
    provider = req.provider if req.provider in VALID_PROVIDERS else prefs.get("provider", "avalai")
    if provider not in VALID_PROVIDERS:
        provider = "avalai"
    memory.set_preferences(username, provider=provider, language=language)

    llm = get_llm_client(provider)
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    t = time.perf_counter()
    try:
        sample = req.data[:20]
        analysis = llm.generate_analysis(sample, user_question, language=language)
    except Exception as e:
        timings["analysis"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=502,
            content={"error": f"Analysis failed: {e}", "timings": timings},
        )
    timings["analysis"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = timings["analysis"]

    memory.update_last_analysis(analysis, user_question=user_question, username=username)

    return {
        "analysis": analysis,
        "language": language,
        "provider": provider,
        "timings": timings,
    }


@app.get("/api/history")
def get_history(request: Request):
    """Returns the persisted conversation history for the logged-in user."""
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    return {"history": memory.get_context(username=username, n=50)}


@app.get("/api/preferences")
def get_preferences(request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    return memory.get_preferences(username)


@app.put("/api/preferences")
def put_preferences(req: PreferencesRequest, request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    provider = req.provider if req.provider in VALID_PROVIDERS else None
    language = req.language if req.language in ("fa", "en") else None
    prefs = memory.set_preferences(username, provider=provider, language=language)
    return {"ok": True, "preferences": prefs}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
