"""
users.py
--------
App user accounts (separate from BI dim_customer).
Stores username, hashed password, mobile, email, display_name, role, tier, total_queries.
Also manages query quotas per user tier:
- Tier 3: 5 messages total lifetime (default for new registrations)
- Tier 2: 10 messages per day
- Tier 1: Unlimited messages
- Admin: Tier 1 (unlimited) + user management access
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, inspect, text
from sqlalchemy.orm import Session

from modules.bi_data.database import Base, SessionLocal, engine

# Bootstrap admin (same defaults as before; override via env)
BOOTSTRAP_ADMIN_USERNAME = os.environ.get("AUTH_USERNAME", "saeed")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("AUTH_PASSWORD", "Saeed@123")
BOOTSTRAP_ADMIN_MOBILE = os.environ.get("AUTH_ADMIN_MOBILE", "09120000000")
BOOTSTRAP_ADMIN_EMAIL = os.environ.get("AUTH_ADMIN_EMAIL", "admin@rayamate.ir")
BOOTSTRAP_ADMIN_DISPLAY = os.environ.get("AUTH_ADMIN_DISPLAY", "مدیر سیستم")

TIER_TIER1 = "tier1"        # کاربر سطح ۱: نامحدود
TIER_TIER2 = "tier2"        # کاربر سطح ۲: ۱۰ پیام روزانه
TIER_TIER3 = "tier3"        # کاربر سطح ۳: ۵ پیام در کل (پیش‌فرض ثبت‌نام)
TIER_PREMIUM = "tier1"      # backward-compatibility alias
ROLE_USER = "user"
ROLE_ADMIN = "admin"

TIER3_TOTAL_LIMIT = 5
TIER2_DAILY_LIMIT = 10

TIER3_EXCEEDED_MESSAGE = "سقف مجاز ۵ پیام آزمایشی شما به پایان رسیده است. جهت ادامه استفاده و ارتقا به سطح ۲، لطفاً با ارسال پیام به ما اقدام فرمایید."
TIER2_EXCEEDED_MESSAGE = "مهلت استفاده روزانه شما به پایان رسیده است و فردا مراجعه کنید یا سطح کاربری خود را با پیغام به ما ارتقا دهید."
# Backward compatibility
EXCEEDED_MESSAGE = TIER2_EXCEEDED_MESSAGE


class AppUser(Base):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    mobile = Column(String(20), nullable=False, default="")
    email = Column(String(120), nullable=True, index=True)
    display_name = Column(String(120), nullable=False, default="")
    role = Column(String(20), nullable=False, default=ROLE_USER)       # admin | user
    tier = Column(String(20), nullable=False, default=TIER_TIER3)      # tier1 | tier2 | tier3
    total_queries = Column(Integer, nullable=False, default=0)         # کل پیام‌های ارسالی کاربر
    google_id = Column(String(120), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserDailyUsage(Base):
    __tablename__ = "app_user_daily_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    usage_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    query_count = Column(Integer, nullable=False, default=0)
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


def get_today_date_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _migrate_app_users_columns() -> None:
    """Safely adds missing columns to existing app_users table without data loss."""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("app_users"):
            return
        existing_cols = {col["name"] for col in inspector.get_columns("app_users")}

        with engine.begin() as conn:
            if "email" not in existing_cols:
                conn.execute(text("ALTER TABLE app_users ADD COLUMN email VARCHAR(120)"))
            if "tier" not in existing_cols:
                conn.execute(text("ALTER TABLE app_users ADD COLUMN tier VARCHAR(20) DEFAULT 'tier3'"))
            if "total_queries" not in existing_cols:
                conn.execute(text("ALTER TABLE app_users ADD COLUMN total_queries INTEGER DEFAULT 0"))
            if "google_id" not in existing_cols:
                conn.execute(text("ALTER TABLE app_users ADD COLUMN google_id VARCHAR(120)"))
    except Exception as exc:
        print(f"[users migration] Notice: {exc}")


try:
    _migrate_app_users_columns()
except Exception:
    pass


def init_users_table() -> None:
    """Create tables if missing and run safe column migrations."""
    AppUser.__table__.create(bind=engine, checkfirst=True)
    UserDailyUsage.__table__.create(bind=engine, checkfirst=True)
    _migrate_app_users_columns()
    seed_bootstrap_admin()


def seed_bootstrap_admin() -> None:
    db = SessionLocal()
    try:
        existing = db.query(AppUser).filter(AppUser.username == BOOTSTRAP_ADMIN_USERNAME).first()
        if existing:
            changed = False
            if existing.role != ROLE_ADMIN:
                existing.role = ROLE_ADMIN
                changed = True
            if getattr(existing, "tier", None) != TIER_TIER1:
                existing.tier = TIER_TIER1
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if not getattr(existing, "email", None):
                existing.email = BOOTSTRAP_ADMIN_EMAIL
                changed = True
            if changed:
                db.commit()
            return

        admin = AppUser(
            username=BOOTSTRAP_ADMIN_USERNAME,
            password_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
            mobile=BOOTSTRAP_ADMIN_MOBILE,
            email=BOOTSTRAP_ADMIN_EMAIL,
            display_name=BOOTSTRAP_ADMIN_DISPLAY,
            role=ROLE_ADMIN,
            tier=TIER_TIER1,
            total_queries=0,
            is_active=True,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()


def get_user_by_username(db: Optional[Session], username: str) -> Optional[AppUser]:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        return db.query(AppUser).filter(AppUser.username == username.strip()).first()
    finally:
        if close_db:
            db.close()


def get_user_by_id(user_id: int) -> Optional[AppUser]:
    db = SessionLocal()
    try:
        return db.query(AppUser).filter(AppUser.id == user_id).first()
    finally:
        db.close()


def get_user_today_queries(user_id: int) -> int:
    db = SessionLocal()
    try:
        today_str = get_today_date_str()
        row = db.query(UserDailyUsage).filter(
            UserDailyUsage.user_id == user_id,
            UserDailyUsage.usage_date == today_str,
        ).first()
        return row.query_count if row else 0
    finally:
        db.close()


def check_and_consume_query_quota(user_id: int) -> tuple[bool, str, int, Optional[int]]:
    """
    Checks whether user can make a chat query.
    Returns: (allowed, message, used_count, limit_count)
    - Admin or Tier 1: Unlimited queries
    - Tier 2: 10 queries per day
    - Tier 3: 5 queries lifetime
    """
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if not user or not user.is_active:
            return False, "حساب کاربری نامعتبر یا غیرفعال است.", 0, 0

        user_tier = getattr(user, "tier", TIER_TIER3)
        if user_tier == "premium":
            user_tier = TIER_TIER1

        # Admin or Tier 1: Unlimited queries
        if user.role == ROLE_ADMIN or user_tier == TIER_TIER1:
            today_str = get_today_date_str()
            row = db.query(UserDailyUsage).filter(
                UserDailyUsage.user_id == user_id,
                UserDailyUsage.usage_date == today_str,
            ).first()
            if not row:
                row = UserDailyUsage(user_id=user_id, usage_date=today_str, query_count=1)
                db.add(row)
            else:
                row.query_count += 1
            user.total_queries = (getattr(user, "total_queries", 0) or 0) + 1
            db.commit()
            return True, "", row.query_count, None

        # Tier 2: 10 queries per day
        if user_tier == TIER_TIER2:
            today_str = get_today_date_str()
            row = db.query(UserDailyUsage).filter(
                UserDailyUsage.user_id == user_id,
                UserDailyUsage.usage_date == today_str,
            ).first()
            current_count = row.query_count if row else 0

            if current_count >= TIER2_DAILY_LIMIT:
                return False, TIER2_EXCEEDED_MESSAGE, current_count, TIER2_DAILY_LIMIT

            if not row:
                row = UserDailyUsage(user_id=user_id, usage_date=today_str, query_count=1)
                db.add(row)
            else:
                row.query_count += 1
            user.total_queries = (getattr(user, "total_queries", 0) or 0) + 1
            db.commit()
            return True, "", row.query_count, TIER2_DAILY_LIMIT

        # Tier 3: 5 queries total lifetime
        total_used = getattr(user, "total_queries", 0) or 0
        if total_used >= TIER3_TOTAL_LIMIT:
            return False, TIER3_EXCEEDED_MESSAGE, total_used, TIER3_TOTAL_LIMIT

        today_str = get_today_date_str()
        row = db.query(UserDailyUsage).filter(
            UserDailyUsage.user_id == user_id,
            UserDailyUsage.usage_date == today_str,
        ).first()
        if not row:
            row = UserDailyUsage(user_id=user_id, usage_date=today_str, query_count=1)
            db.add(row)
        else:
            row.query_count += 1
        user.total_queries = total_used + 1
        db.commit()
        return True, "", user.total_queries, TIER3_TOTAL_LIMIT
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        user = (
            db.query(AppUser)
            .filter((AppUser.username == username.strip()) | (AppUser.email == username.strip().lower()))
            .first()
        )
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user_to_dict(user)
    finally:
        db.close()


def user_to_dict(user: AppUser, include_sensitive: bool = False, include_usage: bool = True) -> dict:
    raw_tier = getattr(user, "tier", TIER_TIER3) or TIER_TIER3
    tier = TIER_TIER1 if raw_tier == "premium" else raw_tier
    total_q = getattr(user, "total_queries", 0) or 0

    data = {
        "id": user.id,
        "username": user.username,
        "email": getattr(user, "email", "") or "",
        "mobile": user.mobile or "",
        "display_name": user.display_name or "",
        "role": user.role,
        "tier": tier,
        "total_queries": total_q,
        "google_id": getattr(user, "google_id", "") or "",
        "is_active": bool(user.is_active),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }
    if include_usage:
        today_count = get_user_today_queries(user.id)
        data["queries_today"] = today_count

        if user.role == ROLE_ADMIN or tier == TIER_TIER1:
            data["limit_type"] = "unlimited"
            data["daily_limit"] = None
            data["lifetime_limit"] = None
            data["queries_remaining"] = None
        elif tier == TIER_TIER2:
            data["limit_type"] = "daily"
            data["daily_limit"] = TIER2_DAILY_LIMIT
            data["lifetime_limit"] = None
            data["queries_remaining"] = max(0, TIER2_DAILY_LIMIT - today_count)
        else:  # tier3
            data["limit_type"] = "lifetime"
            data["daily_limit"] = None
            data["lifetime_limit"] = TIER3_TOTAL_LIMIT
            data["queries_remaining"] = max(0, TIER3_TOTAL_LIMIT - total_q)

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
    mobile: str = "",
    email: str = "",
    display_name: str = "",
    role: str = ROLE_USER,
    tier: str = TIER_TIER3,
) -> tuple[Optional[dict], Optional[str]]:
    username = username.strip()
    if not username or not password:
        return None, "نام کاربری و رمز عبور الزامی است."
    if role not in (ROLE_ADMIN, ROLE_USER):
        return None, "نقش کاربری نامعتبر است."

    if tier == "premium":
        tier = TIER_TIER1
    if tier not in (TIER_TIER1, TIER_TIER2, TIER_TIER3):
        return None, "سطح کاربری نامعتبر است."

    db = SessionLocal()
    try:
        if get_user_by_username(db, username):
            return None, "این نام کاربری قبلاً ثبت شده است."
        if email and db.query(AppUser).filter(AppUser.email == email.strip().lower()).first():
            return None, "این ایمیل قبلاً ثبت شده است."

        user = AppUser(
            username=username,
            password_hash=hash_password(password),
            mobile=(mobile or "").strip(),
            email=(email or "").strip().lower(),
            display_name=(display_name or username).strip(),
            role=role,
            tier=tier,
            total_queries=0,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user_to_dict(user), None
    finally:
        db.close()


def register_user(
    name: str,
    mobile: str,
    email: str,
    username: str,
    password: str,
) -> tuple[Optional[dict], Optional[str]]:
    username = username.strip()
    name = (name or "").strip()
    mobile = (mobile or "").strip()
    email = (email or "").strip().lower()

    if not username:
        return None, "نام کاربری الزامی است."
    if not password or len(password) < 6:
        return None, "رمز عبور باید حداقل ۶ کاراکتر باشد."
    if not name:
        return None, "نام و نام خانوادگی الزامی است."
    if not mobile:
        return None, "شماره موبایل الزامی است."
    if not email or "@" not in email:
        return None, "ایمیل معتبر الزامی است."

    db = SessionLocal()
    try:
        if db.query(AppUser).filter(AppUser.username == username).first():
            return None, "این نام کاربری قبلاً ثبت شده است."
        if db.query(AppUser).filter(AppUser.email == email).first():
            return None, "این ایمیل قبلاً ثبت شده است."
        if mobile and db.query(AppUser).filter(AppUser.mobile == mobile).first():
            return None, "این شماره موبایل قبلاً ثبت شده است."

        # Newly registered users start as Tier 3 (5 total messages)
        user = AppUser(
            username=username,
            password_hash=hash_password(password),
            mobile=mobile,
            email=email,
            display_name=name,
            role=ROLE_USER,
            tier=TIER_TIER3,
            total_queries=0,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user_to_dict(user), None
    finally:
        db.close()


def get_or_create_google_user(
    google_id: str,
    email: str,
    display_name: str,
) -> tuple[Optional[dict], Optional[str]]:
    email = (email or "").strip().lower()
    if not email and not google_id:
        return None, "اطلاعات حساب گوگل نامعتبر است."

    db = SessionLocal()
    try:
        user = None
        if google_id:
            user = db.query(AppUser).filter(AppUser.google_id == google_id).first()
        if not user and email:
            user = db.query(AppUser).filter(AppUser.email == email).first()
            if user and not user.google_id:
                user.google_id = google_id
                db.commit()
                db.refresh(user)

        if user:
            if not user.is_active:
                return None, "حساب کاربری شما غیرفعال شده است."
            return user_to_dict(user), None

        # Auto-create new user with Tier 3 (5 total messages)
        base_username = email.split("@")[0].replace(".", "_").replace("-", "_") if "@" in email else f"google_{google_id[:8]}"
        username = base_username
        suffix = 1
        while db.query(AppUser).filter(AppUser.username == username).first():
            username = f"{base_username}_{suffix}"
            suffix += 1

        random_password = secrets.token_urlsafe(24)
        new_user = AppUser(
            username=username,
            password_hash=hash_password(random_password),
            mobile="",
            email=email,
            display_name=display_name or username,
            role=ROLE_USER,
            tier=TIER_TIER3,
            total_queries=0,
            google_id=google_id,
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return user_to_dict(new_user), None
    finally:
        db.close()


def update_user(
    user_id: int,
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,
    mobile: Optional[str] = None,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    role: Optional[str] = None,
    tier: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> tuple[Optional[dict], Optional[str]]:
    db = SessionLocal()
    try:
        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if not user:
            return None, "کاربر یافت نشد."

        if username is not None:
            username = username.strip()
            if not username:
                return None, "نام کاربری نمی‌تواند خالی باشد."
            conflict = (
                db.query(AppUser)
                .filter(AppUser.username == username, AppUser.id != user_id)
                .first()
            )
            if conflict:
                return None, "نام کاربری تکراری است."
            user.username = username

        if email is not None:
            email_clean = email.strip().lower()
            if email_clean:
                conflict_email = (
                    db.query(AppUser)
                    .filter(AppUser.email == email_clean, AppUser.id != user_id)
                    .first()
                )
                if conflict_email:
                    return None, "ایمیل تکراری است."
            user.email = email_clean

        if password is not None and password.strip():
            user.password_hash = hash_password(password.strip())

        if mobile is not None:
            user.mobile = mobile.strip()
        if display_name is not None:
            user.display_name = display_name.strip()

        if role is not None:
            if role not in (ROLE_ADMIN, ROLE_USER):
                return None, "نقش کاربری نامعتبر است."
            if user.role == ROLE_ADMIN and role != ROLE_ADMIN:
                admin_count = db.query(AppUser).filter(AppUser.role == ROLE_ADMIN, AppUser.is_active.is_(True)).count()
                if admin_count <= 1:
                    return None, "نمی‌توان تنها مدیر فعال سیستم را تنزل داد."
            user.role = role

        if tier is not None:
            if tier == "premium":
                tier = TIER_TIER1
            if tier not in (TIER_TIER1, TIER_TIER2, TIER_TIER3):
                return None, "سطح کاربری نامعتبر است."
            user.tier = tier

        if is_active is not None:
            if user.role == ROLE_ADMIN and not is_active:
                admin_count = db.query(AppUser).filter(AppUser.role == ROLE_ADMIN, AppUser.is_active.is_(True)).count()
                if admin_count <= 1:
                    return None, "نمی‌توان تنها مدیر فعال سیستم را غیرفعال کرد."
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
            return False, "کاربر یافت نشد."
        if user.role == ROLE_ADMIN:
            admin_count = db.query(AppUser).filter(AppUser.role == ROLE_ADMIN).count()
            if admin_count <= 1:
                return False, "نمی‌توان تنها مدیر سیستم را حذف کرد."
        db.query(UserDailyUsage).filter(UserDailyUsage.user_id == user_id).delete()
        db.delete(user)
        db.commit()
        return True, None
    finally:
        db.close()
