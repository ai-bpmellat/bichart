"""
users.py
--------
App user accounts (separate from BI dim_customer).
Stores username, hashed password, mobile, display_name, role.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine

# Bootstrap admin (same defaults as before; override via env)
BOOTSTRAP_ADMIN_USERNAME = os.environ.get("AUTH_USERNAME", "saeed")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("AUTH_PASSWORD", "Saeed@123")
BOOTSTRAP_ADMIN_MOBILE = os.environ.get("AUTH_ADMIN_MOBILE", "09120000000")
BOOTSTRAP_ADMIN_DISPLAY = os.environ.get("AUTH_ADMIN_DISPLAY", "مدیر سیستم")


class AppUser(Base):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    mobile = Column(String(20), nullable=False, default="")
    display_name = Column(String(120), nullable=False, default="")
    role = Column(String(20), nullable=False, default="user")  # admin | user
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds_s, salt, digest_hex = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def init_users_table() -> None:
    """Create app_users table if missing (does not wipe BI mock tables)."""
    AppUser.__table__.create(bind=engine, checkfirst=True)
    seed_bootstrap_admin()


def seed_bootstrap_admin() -> None:
    db = SessionLocal()
    try:
        existing = db.query(AppUser).filter(AppUser.username == BOOTSTRAP_ADMIN_USERNAME).first()
        if existing:
            # Ensure bootstrap account stays admin/active
            changed = False
            if existing.role != "admin":
                existing.role = "admin"
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if changed:
                db.commit()
            return
        admin = AppUser(
            username=BOOTSTRAP_ADMIN_USERNAME,
            password_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
            mobile=BOOTSTRAP_ADMIN_MOBILE,
            display_name=BOOTSTRAP_ADMIN_DISPLAY,
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()


def get_user_by_username(db: Session, username: str) -> Optional[AppUser]:
    return db.query(AppUser).filter(AppUser.username == username.strip()).first()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        user = get_user_by_username(db, username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user_to_dict(user)
    finally:
        db.close()


def user_to_dict(user: AppUser, include_sensitive: bool = False) -> dict:
    data = {
        "id": user.id,
        "username": user.username,
        "mobile": user.mobile or "",
        "display_name": user.display_name or "",
        "role": user.role,
        "is_active": bool(user.is_active),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }
    if include_sensitive:
        data["password_hash"] = user.password_hash
    return data


def list_users() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(AppUser).order_by(AppUser.id.asc()).all()
        return [user_to_dict(u) for u in rows]
    finally:
        db.close()


def create_user(
    username: str,
    password: str,
    mobile: str,
    display_name: str,
    role: str = "user",
) -> tuple[Optional[dict], Optional[str]]:
    username = username.strip()
    if not username or not password:
        return None, "Username and password are required."
    if role not in ("admin", "user"):
        return None, "Invalid role."
    db = SessionLocal()
    try:
        if get_user_by_username(db, username):
            return None, "Username already exists."
        user = AppUser(
            username=username,
            password_hash=hash_password(password),
            mobile=(mobile or "").strip(),
            display_name=(display_name or username).strip(),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user_to_dict(user), None
    finally:
        db.close()


def update_user(
    user_id: int,
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,
    mobile: Optional[str] = None,
    display_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> tuple[Optional[dict], Optional[str]]:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if not user:
            return None, "User not found."

        if username is not None:
            username = username.strip()
            if not username:
                return None, "Username cannot be empty."
            conflict = (
                db.query(AppUser)
                .filter(AppUser.username == username, AppUser.id != user_id)
                .first()
            )
            if conflict:
                return None, "Username already exists."
            user.username = username

        if password is not None and password.strip():
            user.password_hash = hash_password(password.strip())

        if mobile is not None:
            user.mobile = mobile.strip()
        if display_name is not None:
            user.display_name = display_name.strip()
        if role is not None:
            if role not in ("admin", "user"):
                return None, "Invalid role."
            # Prevent removing the last admin
            if user.role == "admin" and role != "admin":
                admin_count = db.query(AppUser).filter(AppUser.role == "admin", AppUser.is_active.is_(True)).count()
                if admin_count <= 1:
                    return None, "Cannot demote the last active admin."
            user.role = role
        if is_active is not None:
            if user.role == "admin" and not is_active:
                admin_count = db.query(AppUser).filter(AppUser.role == "admin", AppUser.is_active.is_(True)).count()
                if admin_count <= 1:
                    return None, "Cannot deactivate the last active admin."
            user.is_active = bool(is_active)

        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user_to_dict(user), None
    finally:
        db.close()


def delete_user(user_id: int) -> tuple[bool, Optional[str]]:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if not user:
            return False, "User not found."
        if user.role == "admin":
            admin_count = db.query(AppUser).filter(AppUser.role == "admin").count()
            if admin_count <= 1:
                return False, "Cannot delete the last admin."
        db.delete(user)
        db.commit()
        return True, None
    finally:
        db.close()
