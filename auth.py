"""
auth.py
-------
Simple session-based login for the BI chat UI.
Credentials are read from environment variables (with dev defaults).
"""

import os
import secrets

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "saeed")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "Saeed@123")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "bichart-change-this-secret-in-production")

SESSION_USER_KEY = "user"


def verify_credentials(username: str, password: str) -> bool:
    user_ok = secrets.compare_digest(username.strip(), AUTH_USERNAME)
    pass_ok = secrets.compare_digest(password, AUTH_PASSWORD)
    return user_ok and pass_ok


def is_authenticated(session: dict) -> bool:
    return session.get(SESSION_USER_KEY) == AUTH_USERNAME
