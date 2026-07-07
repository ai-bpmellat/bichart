"""
avalai_client.py
------------------
HTTP client for AvalAI's OpenAI-compatible chat API.
Mirrors ollama_client's public API: generate_sql() and generate_analysis().
"""

import json
import os

import requests

from ollama_client import (
    RESPONSE_LANGUAGE,
    SQL_SYSTEM_PROMPT,
    _ANALYSIS_LANGUAGE_INSTRUCTIONS,
    _LANGUAGE_INSTRUCTIONS,
    _extract_json,
)

AVALAI_BASE = "https://api.avalai.ir/v1"
AVALAI_API_KEY = os.environ.get("AVALAI_API_KEY", "")
AVALAI_MODEL = os.environ.get("AVALAI_MODEL", "gpt-4o-mini")

REQUEST_TIMEOUT = 60


class AvalAIError(Exception):
    pass


def _chat(user: str, system: str = "", temperature: float = 0.1) -> str:
    if not AVALAI_API_KEY:
        raise AvalAIError(
            "AVALAI_API_KEY is not set on the server. "
            "Set it with: $env:AVALAI_API_KEY=\"your-key\" (PowerShell)"
        )
    payload = {
        "model": AVALAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    try:
        resp = requests.post(
            f"{AVALAI_BASE}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AVALAI_API_KEY}",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.ConnectionError as e:
        raise AvalAIError(f"Could not reach AvalAI API: {e}")
    except requests.exceptions.Timeout:
        raise AvalAIError("AvalAI request timed out.")
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        raise AvalAIError(f"AvalAI returned an HTTP error: {e}" + (f" — {detail}" if detail else ""))
    except (KeyError, IndexError, TypeError) as e:
        raise AvalAIError(f"Unexpected AvalAI response format: {e}")


def check_credit() -> dict:
    """Returns credit balance from AvalAI (server-side only)."""
    if not AVALAI_API_KEY:
        raise AvalAIError("AVALAI_API_KEY is not set on the server.")
    try:
        resp = requests.get(
            "https://api.avalai.ir/user/v1/credit",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AVALAI_API_KEY}",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise AvalAIError(f"Could not fetch AvalAI credit: {e}")


def generate_sql(user_question: str, schema_description: str, language: str = RESPONSE_LANGUAGE) -> dict:
    lang_instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["en"])
    prompt = (
        f"Database schema:\n{schema_description}\n\n"
        f"User question (may be in Persian or English): {user_question}\n\n"
        f"Write a single SELECT query (SQLite syntax) that answers this question. "
        f"Only add a LIMIT clause if the user explicitly asked for a specific number of "
        f"results (e.g. 'top 10'); otherwise return all matching rows, up to 10000. "
        f"Date handling: fact_transactions.date_key is INTEGER YYYYMMDD (e.g. 20260319), "
        f"not a SQL date. Always JOIN dim_date ON fact_transactions.date_key = dim_date.date_key "
        f"and use dim_date.full_date for date filters, strftime month/year, and relative dates "
        f"like date('now','-6 months'). Never compare date_key to date() or call strftime on date_key. "
        f"For calendar months use SQLite modifier 'start of month' (not 'first day of month'). "
        f"Last month / ماه گذشته: full_date >= date('now','start of month','-1 month') "
        f"AND full_date < date('now','start of month'). "
        f"Join dim_merchant directly on fact_transactions.merchant_id (do not route via dim_terminal unless needed). "
        f"Do NOT add status filters unless the user explicitly asked (e.g. 'فعال فقط', 'موفق', 'ناموفق'). "
        f"If filtering terminal status, use lowercase: dim_terminal.status IN ('active','inactive'). "
        f"If filtering transaction status, use fact_transactions.status IN ('approved','declined','reversed'). "
        f"{lang_instruction} The 'sql' value must remain valid SQL syntax regardless of language. "
        f"Respond with ONLY the JSON object, no other text."
    )
    raw = _chat(prompt, system=SQL_SYSTEM_PROMPT, temperature=0.1)
    parsed = _extract_json(raw)
    if "sql" not in parsed:
        raise AvalAIError(f"Model JSON missing 'sql' key: {parsed}")
    parsed.setdefault("explanation", "")
    return parsed


def generate_analysis(data_sample: list, user_question: str, language: str = RESPONSE_LANGUAGE) -> str:
    data_json = json.dumps(data_sample, ensure_ascii=False, default=str)
    prompt = (
        f"Here is the data (first 20 rows): {data_json}. "
        f"Based on this, user asked: {user_question}. "
        f"Provide a clear, concise analysis, forecast, or prediction."
    )
    lang_instruction = _ANALYSIS_LANGUAGE_INSTRUCTIONS.get(language, _ANALYSIS_LANGUAGE_INSTRUCTIONS["en"])
    system = (
        "You are a BI data analyst for a Payment Service Provider. "
        "Be concise, specific, and use numbers from the data when possible. "
        f"{lang_instruction} "
        "Respond in plain text (no JSON, no markdown headers)."
    )
    try:
        raw = _chat(prompt, system=system, temperature=0.4)
    except AvalAIError as e:
        return f"(Analysis unavailable: {e})"
    return raw.strip() or "No analysis could be generated for this result set."
