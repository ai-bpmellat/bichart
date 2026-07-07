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
    AUTH_USERNAME,
    SESSION_SECRET,
    SESSION_USER_KEY,
    is_authenticated,
    verify_credentials,
)

VALID_PROVIDERS = frozenset({"ollama", "avalai"})


def get_llm_client(provider: str):
    if provider == "avalai":
        return avalai_client
    return ollama_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

PUBLIC_PATHS = frozenset({"/login", "/api/login", "/favicon.ico"})
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
    provider: Optional[str] = "ollama"  # "ollama" or "avalai"


class AnalyzeRequest(BaseModel):
    message: str
    data: list
    language: Optional[str] = None
    provider: Optional[str] = "ollama"


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/login")
def login_page(request: Request):
    if is_authenticated(request.session):
        return RedirectResponse(url="/", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    if not verify_credentials(req.username, req.password):
        return JSONResponse(status_code=401, content={"error": "Invalid username or password."})
    request.session[SESSION_USER_KEY] = AUTH_USERNAME
    return {"ok": True, "username": AUTH_USERNAME}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    if not is_authenticated(request.session):
        return JSONResponse(status_code=401, content={"error": "Not authenticated."})
    return {"username": request.session.get(SESSION_USER_KEY)}
@app.get("/")
def index(request: Request):
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
def chat(req: ChatRequest):
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})

    language = req.language or ollama_client.RESPONSE_LANGUAGE
    provider = req.provider if req.provider in VALID_PROVIDERS else "ollama"
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

    # ---- Step 4: Persist to memory (analysis added later via /api/analyze) ----
    t = time.perf_counter()
    memory.add_message(
        user_question=user_question,
        sql=safe_sql,
        explanation=explanation,
        row_count=len(records),
        analysis=None,
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
def analyze(req: AnalyzeRequest):
    """On-demand Ollama analysis after results are already shown."""
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})
    if not req.data:
        return JSONResponse(status_code=400, content={"error": "No data to analyze."})

    language = req.language or ollama_client.RESPONSE_LANGUAGE
    provider = req.provider if req.provider in VALID_PROVIDERS else "ollama"
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

    memory.update_last_analysis(analysis, user_question=user_question)

    return {
        "analysis": analysis,
        "language": language,
        "provider": provider,
        "timings": timings,
    }


@app.get("/api/history")
def get_history():
    """Returns the persisted conversation history (for reloading on page refresh)."""
    return {"history": memory.get_context(n=50)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
