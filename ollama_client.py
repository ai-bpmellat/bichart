"""
ollama_client.py
-----------------
Thin HTTP client around a local Ollama server. Handles two distinct prompts:

1. generate_sql()  -> strict JSON {"sql": ..., "explanation": ...}
2. generate_analysis() -> free-text analysis/forecast paragraph

Gemma (like most small local models) sometimes wraps JSON in markdown fences,
adds a stray sentence before/after the JSON, or uses single quotes. The
`_extract_json` fallback chain handles those cases before giving up.
"""

import json
import os
import re
import requests

OLLAMA_HOST = "http://127.0.0.1:11434"   # use 127.0.0.1, not "localhost" (Windows httpx/requests
                                          # can hit IPv6/proxy resolution issues with "localhost")
#MODEL_NAME = "gemma4:e4b-it-qat"
#MODEL_NAME = " qwen3.5:0.8b"
#MODEL_NAME = "gemma4:e4b"
MODEL_NAME = "gemma4:latest"

REQUEST_TIMEOUT = 60

# Set DEBUG_SQL=1 as an environment variable to print the raw model output
# and the parsed SQL to the console for every chat request. Off by default
# to keep the server log quiet during normal use.
#   Windows (cmd):        set DEBUG_SQL=1
#   Windows (PowerShell):  $env:DEBUG_SQL="1"
#   macOS/Linux:           export DEBUG_SQL=1
DEBUG_SQL = os.environ.get("DEBUG_SQL", "0") == "1"

SQL_SYSTEM_PROMPT = (
    "You are a BI SQL expert. Return ONLY a valid JSON object with keys: "
    "'sql' (the SQL query), and 'explanation' (brief description). "
    "Do not use markdown, do not add extra text.",
    
)

# Default response language for 'explanation' and 'analysis' text shown to the
# user. The SQL itself is always written in SQL syntax regardless of this
# setting. Set to "fa" for Persian or "en" for English.
RESPONSE_LANGUAGE = "fa"

_LANGUAGE_INSTRUCTIONS = {
    "fa": "Write your 'explanation' value in Persian (Farsi), using Persian script.",
    "en": "Write your 'explanation' value in English.",
}
_ANALYSIS_LANGUAGE_INSTRUCTIONS = {
    "fa": "Respond entirely in Persian (Farsi), using Persian script. Do not use English.",
    "en": "Respond entirely in English.",
}


class OllamaError(Exception):
    pass


def _post(prompt: str, system: str = "", temperature: float = 0.1) -> str:
    """Low-level call to Ollama's /api/generate endpoint. Returns raw text response."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        # trust_env=False avoids requests picking up stray HTTP_PROXY / NO_PROXY
        # env vars on Windows that can cause connection resets to localhost.
        session = requests.Session()
        session.trust_env = False
        resp = session.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(
            f"Could not reach Ollama at {OLLAMA_HOST}. Is `ollama serve` running "
            f"and is the model pulled? ({e})"
        )
    except requests.exceptions.Timeout:
        raise OllamaError("Ollama request timed out. The model may be loading for the first time.")
    except requests.exceptions.HTTPError as e:
        raise OllamaError(f"Ollama returned an HTTP error: {e}")


def _escape_literal_control_chars_in_strings(text: str) -> str:
    """
    Gemma sometimes writes multi-line SQL (e.g. a CTE) using REAL newline
    characters inside the JSON string value, instead of the escaped \\n
    sequence JSON requires. That produces "Invalid control character" errors
    from json.loads. This walks the text tracking whether we're currently
    inside a string (toggled by unescaped double quotes) and escapes any
    literal \n, \r, or \t found ONLY while inside a string — structural
    whitespace between JSON tokens (e.g. pretty-printed indentation) is left
    untouched since it's outside any string and already valid JSON syntax.
    """
    out = []
    in_string = False
    for i, ch in enumerate(text):
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            in_string = not in_string
            out.append(ch)
        elif in_string and ch == "\n":
            out.append("\\n")
        elif in_string and ch == "\r":
            out.append("\\r")
        elif in_string and ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    return "".join(out)


def _try_parse(candidate: str):
    """Attempts json.loads, then retries once with literal newlines/tabs
    inside string values escaped. Returns the parsed dict or None."""
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_escape_literal_control_chars_in_strings(candidate))
    except json.JSONDecodeError:
        return None


def _extract_json(raw: str) -> dict:
    """
    Best-effort extraction of a JSON object from model output that may be
    wrapped in markdown fences, prefixed with chatter, contain literal
    newlines inside string values (common with multi-line SQL), or use
    minor formatting quirks.
    """
    text = raw.strip()

    # 1) Direct parse (with literal-newline repair retry)
    result = _try_parse(text)
    if result is not None:
        return result

    # 2) Strip ```json ... ``` or ``` ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        result = _try_parse(fence_match.group(1))
        if result is not None:
            return result

    # 3) Grab the first {...} block greedily (handles leading/trailing chatter)
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
        result = _try_parse(candidate)
        if result is not None:
            return result

        # 4) Common fixups: single quotes -> double quotes, trailing commas.
        #    Quote replacement must happen BEFORE the newline-escape walk,
        #    since that walk only recognizes " as a string delimiter — on
        #    single-quoted input it would never detect it's inside a string.
        fixed = candidate.replace("'", '"')
        fixed = re.sub(r",\s*}", "}", fixed)
        fixed = re.sub(r",\s*]", "]", fixed)
        for variant in (fixed, _escape_literal_control_chars_in_strings(fixed)):
            try:
                return json.loads(variant)
            except json.JSONDecodeError:
                continue

    raise OllamaError(f"Could not parse JSON from model output: {raw[:300]}")


def generate_sql(user_question: str, schema_description: str, language: str = RESPONSE_LANGUAGE) -> dict:
    """
    Calls Gemma with a strict system prompt to produce {"sql": ..., "explanation": ...}.
    The SQL itself is always SQLite syntax (English keywords); only the
    'explanation' field is written in the requested `language` ("fa" or "en").
    Returns a dict with those two keys. Raises OllamaError on failure.
    """
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
        f"Forecast / prediction questions (پیش‌بینی، انتظار می‌رود، روند، forecast, expected): "
        f"the database has NO future transactions — never filter full_date with '+1 month' or future dates. "
        f"Return historical aggregates instead (e.g. monthly totals via "
        f"GROUP BY strftime('%Y-%m', dim_date.full_date) for the last 6 months) so a trend can be inferred. "
        f"Join dim_merchant directly on fact_transactions.merchant_id (do not route via dim_terminal unless needed). "
        f"Do NOT add status filters unless the user explicitly asked (e.g. 'فعال فقط', 'موفق', 'ناموفق'). "
        f"If filtering terminal status, use lowercase: dim_terminal.status IN ('active','inactive'). "
        f"If filtering transaction status, use fact_transactions.status IN ('approved','declined','reversed'). "
        f"{lang_instruction} The 'sql' value must remain valid SQL syntax regardless of language. "
        f"Respond with ONLY the JSON object, no other text."
    )
    raw = _post(prompt, system=SQL_SYSTEM_PROMPT, temperature=0.1)

    if DEBUG_SQL:
        print(f"\n--- [ollama_client] RAW model output for SQL generation ---\n{raw}\n")

    parsed = _extract_json(raw)

    if DEBUG_SQL:
        print(f"--- [ollama_client] Parsed SQL ---\n{parsed.get('sql')}\n")

    if "sql" not in parsed:
        raise OllamaError(f"Model JSON missing 'sql' key: {parsed}")
    parsed.setdefault("explanation", "")
    return parsed


def generate_analysis(data_sample: list, user_question: str, language: str = RESPONSE_LANGUAGE) -> str:
    """
    Second-stage call: given the first ~20 rows of query results and the
    original question, ask Gemma for analysis / forecast / anomaly detection
    in plain text (no JSON constraint needed here), written in `language`.
    """
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
        raw = _post(prompt, system=system, temperature=0.4)
    except OllamaError as e:
        return f"(Analysis unavailable: {e})"
    return raw.strip() or "No analysis could be generated for this result set."