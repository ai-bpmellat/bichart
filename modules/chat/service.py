"""Chat orchestration: text-to-SQL → safety → execute → analyze/discuss."""

from __future__ import annotations

import time
from typing import Any, Optional

import pandas as pd
from sqlalchemy import text

from modules.bi_data.database import SessionLocal
from modules.chat.schema import SCHEMA_DESCRIPTION
from modules.conversation.memory import memory
from modules.llm import ollama as ollama_client
from modules.llm.provider import VALID_PROVIDERS, get_llm_client
from modules.sql_guard.safety import (
    UnsafeSQLError,
    normalize_generated_sql,
    strip_unrequested_limit,
    validate_select_only,
)

HISTORY_DATA_CAP = 500


def resolve_language_provider(
    username: str,
    language: Optional[str] = None,
    provider: Optional[str] = None,
) -> tuple[str, str]:
    prefs = memory.get_preferences(username)
    lang = language or prefs.get("language") or ollama_client.RESPONSE_LANGUAGE
    prov = provider if provider in VALID_PROVIDERS else prefs.get("provider", "avalai")
    if prov not in VALID_PROVIDERS:
        prov = "avalai"
    memory.set_preferences(username, provider=prov, language=lang)
    return lang, prov


def generate_sql(user_question: str, language: str, provider: str) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    llm = get_llm_client(provider)

    t = time.perf_counter()
    try:
        sql_result = llm.generate_sql(user_question, SCHEMA_DESCRIPTION, language=language)
        explanation = sql_result.get("explanation", "")
    except Exception as e:
        timings["sql_generation"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return {"error": f"SQL generation failed: {e}", "timings": timings, "status": 502}
    timings["sql_generation"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    raw_sql = normalize_generated_sql(strip_unrequested_limit(sql_result["sql"], user_question))
    timings["sql_normalize"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "sql": raw_sql,
        "explanation": explanation,
        "language": language,
        "provider": provider,
        "timings": timings,
        "awaiting_run": True,
    }


def _execute(sql_to_run: str) -> list:
    db = SessionLocal()
    try:
        df = pd.read_sql_query(text(sql_to_run), db.bind)
    finally:
        db.close()
    return df.to_dict(orient="records")


def run_sql(
    sql_text: str,
    *,
    username: str,
    user_question: str,
    explanation: str,
    language: str,
    provider: str,
) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    t = time.perf_counter()
    normalized = normalize_generated_sql(
        strip_unrequested_limit(sql_text, user_question) if user_question != "SQL run" else sql_text
    )
    timings["sql_normalize"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    try:
        safe_sql = validate_select_only(normalized)
    except UnsafeSQLError as e:
        timings["sql_safety"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "error": f"SQL was rejected for safety reasons: {e}",
            "sql": normalized,
            "explanation": explanation,
            "timings": timings,
            "status": 400,
        }
    timings["sql_safety"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    llm = get_llm_client(provider)
    auto_fixed = False
    records = None
    exec_error: Optional[Exception] = None
    try:
        records = _execute(safe_sql)
    except Exception as e:
        exec_error = e
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
            timings["sql_autofix"] = round((time.perf_counter() - fix_t) * 1000, 1)
        except Exception:
            pass

    if exec_error is not None:
        timings["sql_execution"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "error": f"SQL execution failed: {exec_error}",
            "sql": safe_sql,
            "explanation": explanation,
            "timings": timings,
            "status": 400,
        }
    timings["sql_execution"] = round((time.perf_counter() - t) * 1000, 1)

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
    timings["memory_save"] = round((time.perf_counter() - t) * 1000, 1)
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


def analyze(user_question: str, data: list, language: str, provider: str, username: str) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    llm = get_llm_client(provider)
    t = time.perf_counter()
    try:
        analysis = llm.generate_analysis(data[:80], user_question, language=language)
    except Exception as e:
        timings["analysis"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return {"error": f"Analysis failed: {e}", "timings": timings, "status": 502}
    timings["analysis"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = timings["analysis"]
    memory.update_last_analysis(analysis, user_question=user_question, username=username)
    return {
        "analysis": analysis,
        "language": language,
        "provider": provider,
        "timings": timings,
    }


def discuss(
    *,
    user_message: str,
    data: Optional[list],
    analysis: str,
    focus: str,
    history: Optional[list],
    original_question: str,
    language: str,
    provider: str,
) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    llm = get_llm_client(provider)
    t = time.perf_counter()
    try:
        hist = history or []
        if len(hist) > 20:
            hist = hist[-20:]
        reply = llm.generate_discussion(
            data_sample=(data or [])[:80],
            user_question=original_question or "",
            analysis=analysis or "",
            user_message=user_message,
            history=hist,
            focus=focus or "",
            language=language,
        )
    except Exception as e:
        timings["discussion"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return {"error": f"Discussion failed: {e}", "timings": timings, "status": 502}
    timings["discussion"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = timings["discussion"]
    return {"reply": reply, "language": language, "provider": provider, "timings": timings}
