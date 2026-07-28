"""
app.py
------
FastAPI application exposing:
    GET  /              -> product landing (static/first.html)
    GET  /login         -> login form
    GET  /app           -> chat UI (static/index.html)
    POST /api/chat       -> text-to-SQL only (user can edit before running)
    POST /api/run_sql    -> safety check + execute edited/generated SQL
    POST /api/analyze    -> optional analysis on demand (after results)
    POST /api/discuss    -> debate / correct flawed data or analysis (multi-turn)
    GET  /api/health     -> health check (DB + Ollama reachability)
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
import pandas as pd
from sqlalchemy import text

from database import engine, SessionLocal
from pdf_generator import generate_llm_pdf
from excel_generator import generate_llm_excel
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
HISTORY_DATA_CAP = 500  # max rows persisted per history entry, so replaying a past chart/table works


def get_llm_client(provider: str):
    if provider == "avalai":
        return avalai_client
    return ollama_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

PUBLIC_PATHS = frozenset({"/", "/login", "/api/login", "/favicon.ico"})
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


# Added after @app.middleware so SessionMiddleware is outermost and request.session works.
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
  * Mock data spans approximately the last 6 months through today (rolling window from db_mock.py).
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


class RunSqlRequest(BaseModel):
    sql: str
    message: Optional[str] = None  # original user question (for history)
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
    focus: Optional[str] = None  # selected snippet the user wants to debate
    history: Optional[list] = None  # [{role: user|assistant, content: str}, ...]
    original_question: Optional[str] = None
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


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # "up" or "down"


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


@app.get("/favicon.ico")
def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "favicon-32.png"), media_type="image/png")


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
    """Step 1: generate SQL from the user question (no execution)."""
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})

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

    def _mark(step: str, started: float) -> None:
        timings[step] = round((time.perf_counter() - started) * 1000, 1)

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

    timings["total"] = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "sql": raw_sql,
        "explanation": explanation,
        "language": language,
        "provider": provider,
        "timings": timings,
        "awaiting_run": True,
    }


@app.post("/api/run_sql")
def run_sql(req: RunSqlRequest, request: Request):
    """Step 2: validate and execute user-edited (or generated) SQL."""
    sql_text = (req.sql or "").strip()
    if not sql_text:
        return JSONResponse(status_code=400, content={"error": "Empty SQL."})

    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    prefs = memory.get_preferences(username)
    language = req.language or prefs.get("language") or ollama_client.RESPONSE_LANGUAGE
    provider = req.provider if req.provider in VALID_PROVIDERS else prefs.get("provider", "avalai")
    if provider not in VALID_PROVIDERS:
        provider = "avalai"

    user_question = (req.message or "").strip() or "SQL run"
    explanation = req.explanation or ""

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    def _mark(step: str, started: float) -> None:
        timings[step] = round((time.perf_counter() - started) * 1000, 1)

    t = time.perf_counter()
    # Light normalize helps date_key / status issues even after manual edits.
    normalized = normalize_generated_sql(
        strip_unrequested_limit(sql_text, user_question) if user_question != "SQL run" else sql_text
    )
    _mark("sql_normalize", t)

    t = time.perf_counter()
    try:
        safe_sql = validate_select_only(normalized)
    except UnsafeSQLError as e:
        _mark("sql_safety", t)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=400,
            content={
                "error": f"SQL was rejected for safety reasons: {e}",
                "sql": normalized,
                "explanation": explanation,
                "timings": timings,
            },
        )
    _mark("sql_safety", t)

    def _execute(sql_to_run: str) -> list:
        db = SessionLocal()
        try:
            df = pd.read_sql_query(text(sql_to_run), db.bind)
        finally:
            db.close()
        return df.to_dict(orient="records")

    t = time.perf_counter()
    llm = get_llm_client(provider)
    auto_fixed = False
    records = None
    exec_error: Optional[Exception] = None
    try:
        records = _execute(safe_sql)
    except Exception as e:
        exec_error = e
        # One automatic self-correction attempt: feed the DB error back to the LLM
        # instead of immediately forcing the user to edit the SQL by hand.
        try:
            fix_t = time.perf_counter()
            fixed = llm.fix_sql(
                user_question=user_question,
                schema_description=SCHEMA_DESCRIPTION,
                failed_sql=safe_sql,
                error_message=str(e),
                language=language,
            )
            candidate_sql = validate_select_only(
                normalize_generated_sql(strip_unrequested_limit(fixed.get("sql", ""), user_question))
            )
            records = _execute(candidate_sql)
            safe_sql = candidate_sql
            explanation = fixed.get("explanation") or explanation
            auto_fixed = True
            exec_error = None
            _mark("sql_autofix", fix_t)
        except Exception:
            pass  # auto-fix unavailable or still failing — report the original error below

    if exec_error is not None:
        _mark("sql_execution", t)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=400,
            content={
                "error": f"SQL execution failed: {exec_error}",
                "sql": safe_sql,
                "explanation": explanation,
                "timings": timings,
            },
        )
    _mark("sql_execution", t)

    t = time.perf_counter()
    entry = memory.add_message(
        username=username,
        user_question=user_question,
        sql=safe_sql,
        explanation=explanation,
        row_count=len(records),
        data=records[:HISTORY_DATA_CAP],
        analysis=None,
        provider=provider,
        language=language,
    )
    _mark("memory_save", t)

    timings["total"] = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "message_id": entry.get("id"),
        "sql": safe_sql,
        "explanation": explanation,
        "data": records,
        "row_count": len(records),
        "language": language,
        "provider": provider,
        "timings": timings,
        "auto_fixed": auto_fixed,
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
        sample = req.data[:80]
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


@app.post("/api/discuss")
def discuss(req: DiscussRequest, request: Request):
    """Discuss / challenge data rows or analysis wording (multi-turn)."""
    user_message = (req.message or "").strip()
    if not user_message:
        return JSONResponse(status_code=400, content={"error": "Empty discussion message."})

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
        sample = (req.data or [])[:80]
        history = req.history or []
        # Keep history bounded
        if len(history) > 20:
            history = history[-20:]
        reply = llm.generate_discussion(
            data_sample=sample,
            user_question=req.original_question or "",
            analysis=req.analysis or "",
            user_message=user_message,
            history=history,
            focus=req.focus or "",
            language=language,
        )
    except Exception as e:
        timings["discussion"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=502,
            content={"error": f"Discussion failed: {e}", "timings": timings},
        )
    timings["discussion"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = timings["discussion"]

    return {
        "reply": reply,
        "language": language,
        "provider": provider,
        "timings": timings,
    }


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest, request: Request):
    """Store thumbs up/down on a completed answer for evaluation and prompt tuning."""
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


@app.get("/api/history")
def get_history(request: Request):
    """Returns the persisted conversation history for the logged-in user."""
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    return {"history": memory.get_context(username=username, n=50)}


@app.get("/api/frequent-questions")
def frequent_questions():
    """Top asked questions across all users, for the sidebar suggestions panel."""
    return {"questions": memory.get_frequent_questions(n=10)}


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


class PDFExportRequest(BaseModel):
    title: str
    explanation: str
    data: Optional[list] = None
    analysis: Optional[str] = None
    chart_image: Optional[str] = None  # data-URL or base64 PNG/JPEG from Chart.js


class ExcelExportRequest(BaseModel):
    title: str
    explanation: str
    data: Optional[list] = None
    analysis: Optional[str] = None


@app.post("/api/export_pdf")
def export_pdf(req: PDFExportRequest, request: Request):
    """Generates a PDF report from the provided LLM data."""
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "Authentication required."})

    try:
        stamp = time.strftime("%Y%m%d%H%M%S")
        filename = f"report{stamp}.pdf"
        filepath = os.path.join(EXPORTS_DIR, filename)

        generate_llm_pdf(
            output_path=filepath,
            title=req.title,
            explanation=req.explanation,
            data=req.data,
            analysis=req.analysis,
            chart_image=req.chart_image,
        )

        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/pdf",
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"PDF generation failed: {e}"})


@app.post("/api/export_excel")
def export_excel(req: ExcelExportRequest, request: Request):
    """Generates an Excel workbook: sheet0=Data, sheet1=Explanation, sheet2=Analysis."""
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "Authentication required."})

    try:
        stamp = time.strftime("%Y%m%d%H%M%S")
        filename = f"report{stamp}.xlsx"
        filepath = os.path.join(EXPORTS_DIR, filename)

        generate_llm_excel(
            output_path=filepath,
            title=req.title,
            explanation=req.explanation,
            data=req.data,
            analysis=req.analysis,
        )

        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Excel generation failed: {e}"})


# ---------------------------------------------------------------------------
# Feature poll: users vote for the next features they want built.
# Votes are stored per-username in feature_poll.json.
# ---------------------------------------------------------------------------
import json as _json
import threading as _threading

FEATURE_POLL_FILE = os.path.join(DATA_DIR, "feature_poll.json")
_feature_poll_lock = _threading.Lock()

FEATURE_POLL_OPTIONS = [
    {"id": "anomaly_alerts", "label": "هشدار هوشمند ناهنجاری تراکنش‌ها"},
    {"id": "jalali_calendar", "label": "تقویم شمسی در نمودارها و فیلترها"},
    {"id": "geo_map", "label": "نقشه جغرافیایی تراکنش‌ها"},
    {"id": "scheduled_reports", "label": "گزارش زمان‌بندی‌شده و ارسال خودکار"},
    {"id": "excel_export", "label": "خروجی اکسل و PDF از نتایج"},
    {"id": "telegram_bot", "label": "ربات تلگرام / پیامک هشدار"},
    {"id": "forecast", "label": "پیش‌بینی روند تراکنش‌ها"},
]
_FEATURE_POLL_IDS = frozenset(o["id"] for o in FEATURE_POLL_OPTIONS)
FEATURE_POLL_MAX_CHOICES = 3

# Custom feature suggestions (max 100 chars, stored as special options)
FEATURE_CUSTOM_MAX_LEN = 100
FEATURE_CUSTOM_PREFIX = "_custom_"


class FeaturePollRequest(BaseModel):
    features: list[str]


def _load_feature_poll() -> dict:
    try:
        with open(FEATURE_POLL_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
        if isinstance(data, dict) and isinstance(data.get("votes"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"votes": {}}


def _save_feature_poll(data: dict) -> None:
    with open(FEATURE_POLL_FILE, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)


def _feature_poll_state(username: str) -> dict:
    data = _load_feature_poll()
    votes = data["votes"]

    # Built-in options
    counts: dict[str, int] = {o["id"]: 0 for o in FEATURE_POLL_OPTIONS}
    # Collect custom options from all voters
    custom_pool: dict[str, str] = {}
    for selection in votes.values():
        for oid in selection:
            if oid in counts:
                counts[oid] += 1
            elif oid.startswith(FEATURE_CUSTOM_PREFIX):
                label = oid[len(FEATURE_CUSTOM_PREFIX):]
                custom_pool[oid] = label
                counts.setdefault(oid, 0)
                counts[oid] += 1

    return {
        "options": FEATURE_POLL_OPTIONS,
        "custom_options": [{"id": k, "label": v} for k, v in custom_pool.items()],
        "counts": counts,
        "total_voters": len(votes),
        "my_votes": votes.get(username, []),
    }


@app.get("/api/feature-poll")
def get_feature_poll(request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"
    with _feature_poll_lock:
        return _feature_poll_state(username)


@app.post("/api/feature-poll")
def post_feature_poll(req: FeaturePollRequest, request: Request):
    session_user = current_user(request.session)
    username = session_user.get("username") if session_user else "anonymous"

    selection = []
    for f in dict.fromkeys(req.features):
        if f in _FEATURE_POLL_IDS:
            selection.append(f)
        elif f.startswith(FEATURE_CUSTOM_PREFIX):
            label = f[len(FEATURE_CUSTOM_PREFIX):]
            if label and len(label) <= FEATURE_CUSTOM_MAX_LEN:
                selection.append(f)
            elif label:
                return JSONResponse(
                    status_code=400,
                    content={"error": "متن گزینه سفارشی حداکثر ۱۰۰ کاراکتر می‌تواند باشد."},
                )

    if not selection:
        return JSONResponse(status_code=400, content={"error": "حداقل یک قابلیت را انتخاب یا پیشنهاد کنید."})
    if len(selection) > FEATURE_POLL_MAX_CHOICES:
        return JSONResponse(
            status_code=400,
            content={"error": f"حداکثر {FEATURE_POLL_MAX_CHOICES} گزینه قابل انتخاب است."},
        )

    with _feature_poll_lock:
        data = _load_feature_poll()
        data["votes"][username] = selection
        _save_feature_poll(data)
        return {"ok": True, **_feature_poll_state(username)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)