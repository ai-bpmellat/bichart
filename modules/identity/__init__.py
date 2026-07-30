"""Identity module: app users + session auth."""

from modules.identity import users
from modules.identity.session import (
    AUTH_USERNAME,
    SESSION_SECRET,
    current_user,
    is_admin,
    is_authenticated,
    set_session_user,
    verify_credentials,
)

__all__ = [
    "users",
    "AUTH_USERNAME",
    "SESSION_SECRET",
    "current_user",
    "is_admin",
    "is_authenticated",
    "set_session_user",
    "verify_credentials",
]
