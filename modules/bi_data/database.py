"""
database.py
------------
Central SQLAlchemy configuration.

This is the ONLY file you need to touch to move from SQLite (local dev/mock)
to IBM DB2 or Microsoft SQL Server in production. Everything else in the app
(db_mock.py, app.py) talks to the database through the `engine` / `SessionLocal`
objects defined here, never through a raw sqlite3 connection string.

How to swap later:
------------------
DB2 (using ibm_db_sa driver, `pip install ibm_db ibm_db_sa`):
    DATABASE_URL = "db2+ibm_db://user:password@host:50000/DBNAME"

SQL Server (using pyodbc, `pip install pyodbc`):
    DATABASE_URL = "mssql+pyodbc://user:password@host/DBNAME?driver=ODBC+Driver+17+for+SQL+Server"

PostgreSQL (using psycopg2, `pip install psycopg2-binary`):
    DATABASE_URL = "postgresql+psycopg2://user:password@host:5432/DBNAME"

In all cases the rest of the codebase is unaffected because it only ever
imports `engine`, `SessionLocal`, and `Base` from this module.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from shared.paths import DATA_DIR, PROJECT_ROOT

os.makedirs(DATA_DIR, exist_ok=True)

_legacy_db = os.path.join(PROJECT_ROOT, "psp_bi_mock.db")
_data_db = os.path.join(DATA_DIR, "psp_bi_mock.db")
# Prefer data/; keep root path while a running process still holds the legacy file.
SQLITE_PATH = _data_db if os.path.exists(_data_db) else (
    _legacy_db if os.path.exists(_legacy_db) else _data_db
)

# ---------------------------------------------------------------------------
# DATABASE_URL is the single switch. Read from env var so you can override
# without touching code (e.g. DATABASE_URL=mssql+pyodbc://... on prod).
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{SQLITE_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
