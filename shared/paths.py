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

