"""
auth.py
-------
Authorization layer for the chat-to-SQL pipeline (runs AFTER the SQL safety
check, BEFORE execution).

Design
------
Each "customer" (a contracted company in dim_customer) owns a subset of
dim_merchant rows via dim_merchant.owner_customer_id. A non-admin customer
must only ever see fact_transactions / dim_terminal / dim_merchant rows that
belong to merchants they own — regardless of what SQL the LLM generated.

Authentication here is a simple demo API key (sent as "access_key" in the
request body, see app.py) mapped to a dim_customer row. Swap this for real
OAuth/JWT/session auth in production — but keep the *authorization* (row-
level scoping) logic below, since that's the part that actually protects
the data no matter how the user authenticated.

Row-level scoping strategy
---------------------------
Rather than trusting the model to include `merchant_id` in its SELECT list
(it often won't, e.g. "SELECT amount, status FROM fact_transactions"), we
rewrite the FROM/JOIN clauses themselves: every reference to a scoped table
is replaced with an inline subquery that pre-filters on merchant_id, e.g.

    FROM fact_transactions f
    -->
    FROM (SELECT * FROM fact_transactions WHERE merchant_id IN (2,7,9)) AS f

This is robust to:
  - existing table aliases ("FROM fact_transactions f")
  - no alias ("FROM fact_transactions")
  - JOINs ("JOIN dim_merchant m ON ...")
  - the model never selecting merchant_id at all

It deliberately avoids matching SQL keywords (LIMIT, WHERE, ORDER, GROUP,
etc.) as if they were a table alias.
"""

import os
import re
from sqlalchemy import text
from database import SessionLocal

# Set AUTH_ENABLED=1 in the environment to require login again.
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "0") == "1"


class AuthorizationError(Exception):
    pass


# Tables in our schema that carry merchant-scoped data and therefore need
# row-level filtering for non-admin customers.
SCOPED_TABLES = {
    "fact_transactions": "merchant_id",
    "dim_merchant": "merchant_id",
    "dim_terminal": "merchant_id",
}

_SQL_KEYWORDS = {
    "where", "group", "order", "limit", "join", "on", "having", "union",
    "left", "right", "inner", "outer", "full", "as", "set", "offset",
}
_KEYWORD_ALT = "|".join(_SQL_KEYWORDS)


def get_default_admin_customer() -> dict | None:
    """First admin customer — used when AUTH_ENABLED is False (full data access)."""
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT customer_id, customer_name, role FROM dim_customer "
                "WHERE role = 'admin' ORDER BY customer_id LIMIT 1"
            )
        ).fetchone()
        if not row:
            return None
        return {"customer_id": row[0], "customer_name": row[1], "role": row[2]}
    finally:
        db.close()


def resolve_customer(access_key: str | None) -> dict | None:
    """Return the session customer. Skips access_key when auth is disabled."""
    if not AUTH_ENABLED:
        return get_default_admin_customer()
    return get_customer_by_key(access_key)


def get_customer_by_key(access_key: str) -> dict | None:
    """Look up a customer row by their demo access key. Returns None if invalid."""
    if not access_key:
        return None
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT customer_id, customer_name, role FROM dim_customer WHERE access_key = :k"),
            {"k": access_key},
        ).fetchone()
        if not row:
            return None
        return {"customer_id": row[0], "customer_name": row[1], "role": row[2]}
    finally:
        db.close()


def list_customers() -> list:
    """For the login dropdown in the demo UI."""
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT customer_id, customer_name, access_key, role FROM dim_customer ORDER BY customer_id")
        ).fetchall()
        return [
            {"customer_id": r[0], "customer_name": r[1], "access_key": r[2], "role": r[3]}
            for r in rows
        ]
    finally:
        db.close()


def get_authorized_merchant_ids(customer_id: int) -> list:
    """Returns the list of merchant_ids this customer is allowed to see."""
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT merchant_id FROM dim_merchant WHERE owner_customer_id = :cid"),
            {"cid": customer_id},
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        db.close()


def authorize_and_scope_sql(sql: str, customer: dict) -> str:
    """
    Given a validated, read-only SELECT statement and the authenticated
    customer, returns SQL rewritten so every scoped table is pre-filtered
    to that customer's owned merchants. Admin customers pass through
    unchanged (PSP-internal BI users see all data).

    Raises AuthorizationError if the customer has zero authorized merchants
    on file (nothing safe to return) and the query touches a scoped table.
    """
    if customer["role"] == "admin":
        return sql

    sql_lower = sql.lower()
    touches_scoped_table = any(
        re.search(rf"\b{tbl}\b", sql_lower) for tbl in SCOPED_TABLES
    )
    if not touches_scoped_table:
        # e.g. a pure dim_date query — nothing merchant-specific to restrict.
        return sql

    merchant_ids = get_authorized_merchant_ids(customer["customer_id"])
    if not merchant_ids:
        raise AuthorizationError(
            f"Customer '{customer['customer_name']}' has no authorized merchants on file."
        )
    ids_csv = ",".join(str(i) for i in merchant_ids)

    rewritten = sql
    for tbl, col in SCOPED_TABLES.items():
        pattern = re.compile(
            rf"(?i)\b(from|join)\s+{tbl}\b"
            rf"(?:\s+(?:as\s+)?(?!(?:{_KEYWORD_ALT})\b)([a-zA-Z_][a-zA-Z0-9_]*))?"
        )

        def repl(m, _tbl=tbl, _col=col):
            kw = m.group(1)
            alias = m.group(2) if m.group(2) else _tbl
            return f"{kw} (SELECT * FROM {_tbl} WHERE {_col} IN ({ids_csv})) AS {alias}"

        rewritten = pattern.sub(repl, rewritten)

    return rewritten


def merchant_ids_for_customer(customer: dict) -> list:
    """Empty list means 'unrestricted' (admin), by convention — display purposes only."""
    if customer["role"] == "admin":
        return []
    return get_authorized_merchant_ids(customer["customer_id"])
