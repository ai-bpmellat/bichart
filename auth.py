"""
auth.py
-------
Session helpers for the BI chat UI.
Login credentials are validated against app_users in the database.
"""

from __future__ import annotations

import os
from typing import Optional

import users as users_mod

SESSION_SECRET = os.environ.get("SESSION_SECRET", "bichart-change-this-secret-in-production")

SESSION_USER_KEY = "user"
SESSION_USER_ID_KEY = "user_id"
SESSION_ROLE_KEY = "role"
SESSION_DISPLAY_KEY = "display_name"

# Kept for backward-compatible env bootstrap naming
AUTH_USERNAME = users_mod.BOOTSTRAP_ADMIN_USERNAME


def verify_credentials(username: str, password: str) -> Optional[dict]:
    """
    Returns a public user dict on success, or None on failure.
    """
    return users_mod.authenticate_user(username, password)


def set_session_user(session: dict, user: dict) -> None:
    session[SESSION_USER_KEY] = user["username"]
    session[SESSION_USER_ID_KEY] = user["id"]
    session[SESSION_ROLE_KEY] = user.get("role", "user")
    session[SESSION_DISPLAY_KEY] = user.get("display_name") or user["username"]


def is_authenticated(session: dict) -> bool:
    return bool(session.get(SESSION_USER_KEY))


def is_admin(session: dict) -> bool:
    return session.get(SESSION_ROLE_KEY) == "admin"


def current_user(session: dict) -> Optional[dict]:
    if not is_authenticated(session):
        return None
    return {
        "id": session.get(SESSION_USER_ID_KEY),
        "username": session.get(SESSION_USER_KEY),
        "role": session.get(SESSION_ROLE_KEY, "user"),
        "display_name": session.get(SESSION_DISPLAY_KEY) or session.get(SESSION_USER_KEY),
    }
