"""
app.py
------
FastAPI application exposing:
    GET  /              -> serves the chat UI (static/index.html)
    POST /api/chat       -> the full pipeline (text-to-SQL -> execute -> analyze)
    GET  /api/health     -> health check (DB + Ollama reachability)

Pipeline executed by /api/chat, in order:
    1. Call Gemma (ollama_client.generate_sql) with a strict JSON system prompt.
    2. Validate the SQL is read-only SELECT only (sql_safety.validate_select_only).
    3. Execute against SQLite (swappable engine via database.py), capped at sql_safety.MAX_ROWS.
    4. Call Gemma again (ollama_client.generate_analysis) with the first 20 rows + question.
    5. Store the full turn in memory (memory_manager) and persist to history.json.
    6. Return {sql, explanation, data, analysis} to the frontend.

Why FastAPI instead of Flask:
    The brief asked for Flask but allowed swapping frameworks if something fits
    better. This pipeline makes two sequential, network-bound calls to Ollama per
    request (SQL generation, then analysis). FastAPI's native async support means
    the server doesn't block its single worker thread waiting on those HTTP calls,
    Pydantic gives free request validation, and you get OpenAPI docs at /docs for
    free, which is handy when testing the API directly during development.
"""

import os
import traceback
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
from sqlalchemy import text

from database import engine, SessionLocal
import ollama_client
from sql_safety import validate_select_only, UnsafeSQLError, strip_unrequested_limit
from memory_manager import memory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="PSP BI Conversational Report Builder")
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

fact_transactions(transaction_id INTEGER PK, date_key INTEGER FK -> dim_date,
                   terminal_id INTEGER FK -> dim_terminal, merchant_id INTEGER FK -> dim_merchant,
                   transaction_time DATETIME, amount REAL, currency TEXT, status TEXT
                   (approved/declined/reversed), card_pan_masked TEXT, response_code TEXT,
                   settlement_date DATE, channel TEXT (POS/ONLINE/MOBILE))

Notes:
- "yesterday" / "دیروز" means full_date = date('now','-1 day') joined via date_key, or you
  can filter transaction_time directly using date() function.
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health():
    status = {"db": "unknown", "ollama": "unknown"}

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

    overall_ok = status["db"] == "ok" and status["ollama"] == "ok"
    return JSONResponse(status_code=200 if overall_ok else 503, content=status)


@app.post("/api/chat")
def chat(req: ChatRequest):
    user_question = req.message.strip()
    if not user_question:
        return JSONResponse(status_code=400, content={"error": "Empty message."})

    language = req.language or ollama_client.RESPONSE_LANGUAGE

    # ---- Step 1: Text-to-SQL via Gemma ----
    try:
        sql_result = ollama_client.generate_sql(user_question, SCHEMA_DESCRIPTION, language=language)
        raw_sql = strip_unrequested_limit(sql_result["sql"], user_question)
        explanation = sql_result.get("explanation", "")
    except ollama_client.OllamaError as e:
        return JSONResponse(status_code=502, content={"error": f"SQL generation failed: {e}"})

    # ---- Step 2: Safety check (read-only SELECT, no destructive statements) ----
    try:
        safe_sql = validate_select_only(raw_sql)
    except UnsafeSQLError as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Generated SQL was rejected for safety reasons: {e}",
                "sql": raw_sql,
                "explanation": explanation,
            },
        )

    # ---- Step 3: Execute against the DB ----
    try:
        db = SessionLocal()
        try:
            df = pd.read_sql_query(text(safe_sql), db.bind)
        finally:
            db.close()
        records = df.to_dict(orient="records")
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"SQL execution failed: {e}",
                "sql": safe_sql,
                "explanation": explanation,
            },
        )

    # ---- Step 4: Analysis / prediction via Gemma (second call) ----
    sample_for_analysis = records[:20]
    analysis = ollama_client.generate_analysis(sample_for_analysis, user_question, language=language)

    # ---- Step 5: Persist to memory (in-process + history.json) ----
    memory.add_message(
        user_question=user_question,
        sql=safe_sql,
        explanation=explanation,
        row_count=len(records),
        analysis=analysis,
    )

    return {
        "sql": safe_sql,
        "explanation": explanation,
        "data": records,
        "row_count": len(records),
        "analysis": analysis,
        "language": language,
    }


@app.get("/api/history")
def get_history():
    """Returns the persisted conversation history (for reloading on page refresh)."""
    return {"history": memory.get_context(n=50)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
