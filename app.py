"""
app.py — Demo (indexPage branch)
--------------------------------
Open chat UI only (no login / first page / user management).

    GET  /               -> static/index.html
    POST /api/chat       -> text-to-SQL + execute
    POST /api/analyze    -> optional analysis
    GET  /api/history    -> demo history
    GET/PUT /api/preferences
    GET  /api/health
"""

import os
import time
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
from sqlalchemy import text

from database import SessionLocal
import ollama_client
import avalai_client
from sql_safety import validate_select_only, UnsafeSQLError, strip_unrequested_limit, normalize_generated_sql
from memory_manager import memory

VALID_PROVIDERS = frozenset({"ollama", "avalai"})
DEMO_USERNAME = "demo"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def get_llm_client(provider: str):
    if provider == "avalai":
        return avalai_client
    return ollama_client


app = FastAPI(title="PSP BI Conversational Report Builder (Demo)")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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


class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = None
    provider: Optional[str] = "avalai"


class AnalyzeRequest(BaseModel):
    message: str
    data: list
    language: Optional[str] = None
    provider: Optional[str] = "avalai"


class PreferencesRequest(BaseModel):
    provider: Optional[str] = None
    language: Optional[str] = None


@app.get("/")
def index():
    """Demo entry: chat UI only."""
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
    try:
        return avalai_client.check_credit()
    except avalai_client.AvalAIError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


@app.get("/api/preferences")
def get_preferences():
    return memory.get_preferences(DEMO_USERNAME)


@app.put("/api/preferences")
def put_preferences(req: PreferencesRequest):
    provider = req.provider if req.provider in VALID_PROVIDERS else None
    language = req.language if req.language in ("fa", "en") else None
    prefs = memory.set_preferences(DEMO_USERNAME, provider=provider, language=language)
    return {"ok": True, "preferences": prefs}


@app.get("/api/history")
def get_history():
    return {"history": memory.get_context(username=DEMO_USERNAME, n=50)}


@app.post("/api/chat")
def chat(req: ChatRequest):
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})

    username = DEMO_USERNAME
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
def analyze(req: AnalyzeRequest):
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})
    if not req.data:
        return JSONResponse(status_code=400, content={"error": "No data to analyze."})

    username = DEMO_USERNAME
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
