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
import re
import requests

OLLAMA_HOST = "http://127.0.0.1:11434"   # use 127.0.0.1, not "localhost" (Windows httpx/requests
                                          # can hit IPv6/proxy resolution issues with "localhost")
MODEL_NAME = "gemma4:latest"
REQUEST_TIMEOUT = 60

SQL_SYSTEM_PROMPT = (
    "You are a BI SQL expert. Return ONLY a valid JSON object with keys: "
    "'sql' (the SQL query), and 'explanation' (brief description). "
    "Never add LIMIT to the SQL unless the user explicitly asks for a specific "
    "number of rows (e.g. 'top 10', 'first 5'). "
    "Do not use markdown, do not add extra text."
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


def _extract_json(raw: str) -> dict:
    """
    Best-effort extraction of a JSON object from model output that may be
    wrapped in markdown fences, prefixed with chatter, or use minor
    formatting quirks.
    """
    text = raw.strip()

    # 1) Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) Strip ```json ... ``` or ``` ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3) Grab the first {...} block greedily (handles leading/trailing chatter)
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 4) Common fixups: single quotes -> double quotes, trailing commas
            fixed = candidate.replace("'", '"')
            fixed = re.sub(r",\s*}", "}", fixed)
            fixed = re.sub(r",\s*]", "]", fixed)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

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
        f"Do NOT add LIMIT unless the user explicitly asked for a specific row count "
        f"(e.g. 'top 10', 'اول ۵'). For 'all rows' / 'همه' / full-table questions, "
        f"return every matching row with no LIMIT clause. "
        f"{lang_instruction} The 'sql' value must remain valid SQL syntax regardless of language. "
        f"Respond with ONLY the JSON object, no other text."
    )
    raw = _post(prompt, system=SQL_SYSTEM_PROMPT, temperature=0.1)
    parsed = _extract_json(raw)

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
