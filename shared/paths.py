"""Project filesystem roots used by all modules."""

from __future__ import annotations

import os

_SHARED_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SHARED_DIR)
BASE_DIR = PROJECT_ROOT

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
EXPORTS_DIR = os.path.join(PROJECT_ROOT, "exports")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)


def _load_dotenv() -> None:
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and v:
                    os.environ[k] = v
    except Exception:
        pass


_load_dotenv()


