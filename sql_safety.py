"""
sql_safety.py
--------------
Validates that LLM-generated SQL is a single, read-only SELECT statement
before it ever touches the database. This runs BEFORE the authorization
scoping in auth.py (order: parse JSON -> safety check -> auth scoping -> execute).
"""

import re

FORBIDDEN_KEYWORDS = [
    "drop", "delete", "update", "insert", "alter", "create", "truncate",
    "replace", "grant", "revoke", "attach", "detach", "pragma", "vacuum",
    "reindex", "exec", "execute",
]

MAX_ROWS = 100000


class UnsafeSQLError(Exception):
    pass


_LIMIT_REQUEST_PATTERNS = [
    r"\btop\s+\d+",
    r"\bfirst\s+\d+",
    r"\blimit\s+\d+",
    r"\d+\s*(row|rows|result|results)\b",
    r"اول\s*\d+",
    r"\d+\s*تا",
    r"\d+\s*مورد",
    r"برترین\s*\d+",
    r"بیشترین\s*\d+\s",
]


def user_requested_row_limit(user_question: str) -> bool:
    """True when the user explicitly asked for a capped number of rows (e.g. top 10)."""
    if not user_question:
        return False
    q = user_question.lower()
    return any(re.search(p, q) for p in _LIMIT_REQUEST_PATTERNS)


def strip_unrequested_limit(sql: str, user_question: str) -> str:
    """
    Remove a trailing LIMIT clause when the user did not ask for one.
    Gemma often adds LIMIT 100 by habit even for 'show all' questions.
    """
    if user_requested_row_limit(user_question):
        return sql.strip()
    cleaned = sql.strip().rstrip(";")
    return re.sub(
        r"\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )


def validate_select_only(sql: str) -> str:
    """
    Raises UnsafeSQLError if the SQL is not a safe, single, read-only SELECT.
    Returns the SQL unchanged unless a LIMIT exceeds MAX_ROWS (then it is capped).
    Does not add LIMIT automatically — full result sets are allowed up to MAX_ROWS.
    """
    if not sql or not sql.strip():
        raise UnsafeSQLError("Empty SQL was generated.")

    cleaned = sql.strip().rstrip(";")

    # Reject multiple statements (stacked queries via semicolon)
    if ";" in cleaned:
        raise UnsafeSQLError("Multiple SQL statements are not allowed.")

    lowered = cleaned.lower()

    if not lowered.startswith("select") and not lowered.startswith("with"):
        raise UnsafeSQLError("Only SELECT statements are allowed.")

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            raise UnsafeSQLError(f"Forbidden keyword detected: '{kw.upper()}'.")

    # Only cap an explicit LIMIT that exceeds MAX_ROWS; never inject LIMIT.
    limit_match = re.search(r"\blimit\s+(\d+)", lowered)
    if limit_match:
        existing_limit = int(limit_match.group(1))
        if existing_limit > MAX_ROWS:
            cleaned = re.sub(
                r"(?i)\blimit\s+\d+", f"LIMIT {MAX_ROWS}", cleaned
            )

    return cleaned
