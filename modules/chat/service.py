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
    except Exception as e:
        timings["sql_generation"] = round((time.perf_counter() - t) * 1000, 1)
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return {"error": f"SQL generation failed: {e}", "timings": timings, "status": 502}
    timings["sql_generation"] = round((time.perf_counter() - t) * 1000, 1)

    if sql_result.get("needs_clarification"):
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "needs_clarification": True,
            "clarification_question": sql_result.get("clarification_question", ""),
            "language": language,
            "provider": provider,
            "timings": timings,
        }

    explanation = sql_result.get("explanation", "")

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

    stats = compute_result_stats(records, user_question=user_question)

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
        "stats": stats,
    }


def compute_result_stats(records: list, user_question: str = "", numeric_col_hint: Optional[str] = None) -> dict[str, Any]:
    """محاسبه هوشمند آمار و شاخص‌های کاربردی بازاریابی و ارزیابی کسب‌وکار متناسب با قصد سوال کاربر."""
    if not records:
        return {"intent_type": "comparison"}

    q_lower = (user_question or "").lower()

    # 1. Intent Detection
    forecast_keywords = ["پیش‌بینی", "احتمال", "رشد", "آینده", "ماه بعد", "ماه آینده", "روند", "forecast", "predict", "probability", "growth", "future", "trend", "momentum", "expect", "انتظار"]
    churn_keywords = ["ریزش", "کاهش", "افت", "ناموفق", "خروج", "غیرفعال", "churn", "decline", "drop", "loss", "inactive", "failed"]
    ranking_keywords = ["۱۰", "برتر", "رتبه", "بیشترین", "کمترین", "سهم", "تمرکز", "top", "rank", "highest", "lowest", "share", "pareto", "پارتو"]

    is_forecast = any(w in q_lower for w in forecast_keywords)
    is_churn = any(w in q_lower for w in churn_keywords) and not is_forecast
    is_ranking = any(w in q_lower for w in ranking_keywords) and not (is_forecast or is_churn)

    intent = "forecast" if is_forecast else ("churn" if is_churn else ("ranking" if is_ranking else "comparison"))

    # Determine numeric column
    numeric_col = numeric_col_hint
    if not numeric_col:
        for k, v in records[0].items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numeric_col = k
                break

    if not numeric_col:
        return {"intent_type": intent}

    values = []
    for r in records:
        val = r.get(numeric_col)
        if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
            values.append(float(val))

    if not values:
        return {"intent_type": intent, "column": numeric_col}

    total = sum(values)
    avg_val = round(total / len(values), 2)
    max_val = max(values)
    min_val = min(values)

    # Time series / Growth calculations
    growth_rates = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev != 0:
            growth_rates.append(((curr - prev) / prev) * 100)

    avg_growth_pct = round(sum(growth_rates) / len(growth_rates), 1) if growth_rates else 0.0
    pos_growths = [g for g in growth_rates if g > 0]
    positive_growth_ratio_pct = round((len(pos_growths) / len(growth_rates) * 100), 1) if growth_rates else 50.0

    # Growth Volatility (Standard Deviation of Growth Rates)
    if len(growth_rates) > 1:
        mean_g = avg_growth_pct
        variance = sum((g - mean_g) ** 2 for g in growth_rates) / len(growth_rates)
        growth_volatility_pct = round(variance ** 0.5, 1)
    else:
        growth_volatility_pct = 0.0

    # Calculate estimated growth probability for next period
    if growth_rates:
        base_prob = positive_growth_ratio_pct
        trend_adj = 10.0 if avg_growth_pct > 5 else (-10.0 if avg_growth_pct < -5 else 0.0)
        recent_adj = 5.0 if growth_rates[-1] > 0 else -5.0
        # Reduce probability slightly if volatility is high
        volatility_adj = -5.0 if growth_volatility_pct > 15.0 else 0.0
        estimated_growth_prob_pct = round(max(5.0, min(95.0, base_prob + trend_adj + recent_adj + volatility_adj)), 1)
    else:
        estimated_growth_prob_pct = 50.0

    # Ranking & Top/Bottom Stats
    top = values[0]
    bottom = values[-1]

    # Comparative Benchmarks
    top_vs_avg_ratio = round(top / avg_val, 1) if avg_val != 0 else 1.0
    latest_vs_avg_pct = round(((values[-1] - avg_val) / avg_val * 100), 1) if avg_val != 0 else 0.0

    # Predictive Forecast Calculations
    projected_next_value = round(values[-1] * (1.0 + (avg_growth_pct / 100.0)), 2)
    projected_range_low = round(projected_next_value * 0.93, 2)
    projected_range_high = round(projected_next_value * 1.07, 2)

    # Momentum trend indicator
    if len(growth_rates) >= 2:
        recent_momentum = growth_rates[-1] - growth_rates[-2]
        if recent_momentum > 3.0:
            momentum_label = "شتاب‌دار صعودی (Accelerating Growth)"
        elif recent_momentum < -3.0:
            momentum_label = "کاهش شتاب رشد (Decelerating)"
        else:
            momentum_label = "رشد پایدار و متعادل (Stable Momentum)"
    else:
        momentum_label = "روند معمولی (Standard Trend)"

    # Ranking & Concentration Stats
    top_share_pct = round((top / total * 100), 1) if total != 0 else 0.0
    top_3_sum = sum(values[:3])
    top_3_share_pct = round((top_3_sum / total * 100), 1) if total != 0 else 0.0
    top_to_bottom_ratio = round((top / bottom), 1) if bottom != 0 else None

    # Churn stats
    drop_from_peak_pct = round(((max_val - values[-1]) / max_val * 100), 1) if max_val != 0 else 0.0

    return {
        "intent_type": intent,
        "column": numeric_col,
        "total_sum": total,
        "avg_val": avg_val,
        "max_val": max_val,
        "min_val": min_val,
        "first_val": values[0],
        "latest_val": values[-1],
        "row_count": len(values),
        # Marketing & Growth metrics
        "avg_growth_pct": avg_growth_pct,
        "positive_growth_ratio_pct": positive_growth_ratio_pct,
        "estimated_growth_prob_pct": estimated_growth_prob_pct,
        "growth_volatility_pct": growth_volatility_pct,
        "growth_rates": [round(g, 1) for g in growth_rates],
        # Comparative metrics
        "top_vs_avg_ratio": top_vs_avg_ratio,
        "latest_vs_avg_pct": latest_vs_avg_pct,
        "momentum_label": momentum_label,
        # Predictive Metrics
        "projected_next_value": projected_next_value,
        "projected_range_low": projected_range_low,
        "projected_range_high": projected_range_high,
        # Ranking & Concentration metrics
        "top_value": top,
        "bottom_value": bottom,
        "top_share_pct": top_share_pct,
        "top_3_share_pct": top_3_share_pct if len(values) >= 3 else None,
        "top_to_bottom_ratio": top_to_bottom_ratio,
        # Churn & Risk metrics
        "drop_from_peak_pct": drop_from_peak_pct,
    }


def analyze(user_question: str, data: list, language: str, provider: str, username: str) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    llm = get_llm_client(provider)
    t = time.perf_counter()
    stats = compute_result_stats(data, user_question=user_question)
    try:
        analysis = llm.generate_analysis(
            data[:80],
            user_question,
            language=language,
            precomputed_stats=stats,
        )
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
