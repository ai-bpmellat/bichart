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

# fact_transactions.date_key is INTEGER YYYYMMDD — not a SQL date.
_FACT_TXN_ALIAS_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+fact_transactions(?:\s+AS)?\s+(\w+)",
    re.IGNORECASE,
)
_DIM_DATE_JOIN_RE = re.compile(
    r"JOIN\s+dim_date(?:\s+AS)?\s+(\w+)\s+ON\s+"
    r"(?:(\w+)\.date_key\s*=\s*(\w+)\.date_key)",
    re.IGNORECASE,
)
_DATE_KEY_DATE_OP_RE = re.compile(
    r"(\w+)\.date_key\s*(>=|<=|>|<|=)\s*(date\s*\([^)]+\))",
    re.IGNORECASE,
)
_DATE_OP_DATE_KEY_RE = re.compile(
    r"(date\s*\([^)]+\))\s*(>=|<=|>|<|=)\s*(\w+)\.date_key",
    re.IGNORECASE,
)
_STRFTIME_ON_DATE_KEY_RE = re.compile(
    r"(strftime\s*\(\s*'[^']*'\s*,\s*)(\w+)\.date_key(\s*\))",
    re.IGNORECASE,
)
_DATE_ON_DATE_KEY_RE = re.compile(
    r"date\s*\(\s*(\w+)\.date_key\s*\)",
    re.IGNORECASE,
)


class UnsafeSQLError(Exception):
    pass


def _dim_date_alias_for_fact_alias(sql: str, fact_alias: str) -> str | None:
    """Return dim_date alias already joined to this fact_transactions alias, if any."""
    for m in _DIM_DATE_JOIN_RE.finditer(sql):
        left_tbl, right_tbl = m.group(2), m.group(3)
        if {left_tbl, right_tbl} == {fact_alias, m.group(1)}:
            return m.group(1)
    return None


def _needs_date_key_fixup(sql: str, fact_aliases: set[str]) -> bool:
    for alias in fact_aliases:
        a = re.escape(alias)
        if re.search(rf"strftime\s*\(\s*'[^']*'\s*,\s*{a}\.date_key\s*\)", sql, re.IGNORECASE):
            return True
        if re.search(rf"date\s*\(\s*{a}\.date_key\s*\)", sql, re.IGNORECASE):
            return True
        if re.search(rf"{a}\.date_key\s*(?:>=|<=|>|<|=)\s*date\s*\(", sql, re.IGNORECASE):
            return True
        if re.search(rf"date\s*\([^)]+\)\s*(?:>=|<=|>|<|=)\s*{a}\.date_key\b", sql, re.IGNORECASE):
            return True
    return False


def fix_date_key_sql(sql: str) -> str:
    """
    Repair LLM SQL that treats fact_transactions.date_key (INTEGER YYYYMMDD)
    as a SQL date. Joins dim_date when needed and rewrites filters/expressions
    to use dim_date.full_date.
    """
    cleaned = sql.strip().rstrip(";")
    fact_aliases = set(_FACT_TXN_ALIAS_RE.findall(cleaned))
    if not fact_aliases or not _needs_date_key_fixup(cleaned, fact_aliases):
        return cleaned

    dim_aliases: dict[str, str] = {}
    for alias in fact_aliases:
        existing = _dim_date_alias_for_fact_alias(cleaned, alias)
        if existing:
            dim_aliases[alias] = existing
            continue
        dim_alias = f"_d_{alias}"
        dim_aliases[alias] = dim_alias
        pattern = rf"((?:FROM|JOIN)\s+fact_transactions(?:\s+AS)?\s+{re.escape(alias)})\b"
        cleaned = re.sub(
            pattern,
            rf"\1 JOIN dim_date AS {dim_alias} ON {alias}.date_key = {dim_alias}.date_key",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )

    def _dim(alias: str) -> str:
        return dim_aliases.get(alias, alias)

    cleaned = _STRFTIME_ON_DATE_KEY_RE.sub(
        lambda m: f"{m.group(1)}{_dim(m.group(2))}.full_date{m.group(3)}",
        cleaned,
    )
    cleaned = _DATE_ON_DATE_KEY_RE.sub(
        lambda m: f"{_dim(m.group(1))}.full_date",
        cleaned,
    )
    cleaned = _DATE_KEY_DATE_OP_RE.sub(
        lambda m: f"{_dim(m.group(1))}.full_date {m.group(2)} {m.group(3)}",
        cleaned,
    )
    cleaned = _DATE_OP_DATE_KEY_RE.sub(
        lambda m: f"{m.group(1)} {m.group(2)} {_dim(m.group(3))}.full_date",
        cleaned,
    )
    return cleaned


# SQLite accepts 'start of month', not 'first day of month' (which returns NULL).
_INVALID_MONTH_MODIFIERS = [
    (re.compile(r"first\s+day\s+of\s+month", re.IGNORECASE), "start of month"),
    (re.compile(r"last\s+day\s+of\s+month", re.IGNORECASE), "start of month', '+1 month', '-1 day"),
]


def fix_sqlite_date_modifiers(sql: str) -> str:
    """Replace invalid SQLite date() modifiers that Gemma often invents."""
    cleaned = sql.strip().rstrip(";")
    for pattern, replacement in _INVALID_MONTH_MODIFIERS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def fix_status_literals(sql: str) -> str:
    """
    Normalize common LLM hallucinations around status literals.

    In this mock DB:
      - dim_terminal.status is 'active' or 'inactive' (lowercase)
      - fact_transactions.status is 'approved'/'declined'/'reversed'

    Some models generate 'Active'/'Inactive' which can produce empty results.
    This rewrite is intentionally narrow: it only normalizes those literals.
    """
    cleaned = sql.strip().rstrip(";")
    cleaned = re.sub(r"=\s*'Active'\b", "= 'active'", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"=\s*\"Active\"\b", "= 'active'", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"=\s*'Inactive'\b", "= 'inactive'", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"=\s*\"Inactive\"\b", "= 'inactive'", cleaned, flags=re.IGNORECASE)
    return cleaned


def normalize_generated_sql(sql: str) -> str:
    """Apply all safe rewrites to LLM-generated SQL before validation."""
    return fix_status_literals(fix_sqlite_date_modifiers(fix_date_key_sql(sql)))


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
