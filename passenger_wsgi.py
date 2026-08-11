"""
cPanel / Phusion Passenger entry point for FastAPI.

Phusion Passenger on cPanel speaks WSGI, but FastAPI is an ASGI app.
We use 'a2wsgi' to bridge ASGI → WSGI so Passenger can manage the process.

cPanel -> Setup Python App configuration:
  - Python Version: 3.10+ recommended
  - Application root: /home/<username>/bichart   (where this file lives)
  - Application URL: /  (or your subdomain/subdirectory)
  - Application startup file: passenger_wsgi.py
  - Application entry point: application
  - Environment Variables (set in cPanel UI):
      AVALAI_API_KEY = your_avalai_api_key
      SESSION_SECRET = your_session_secret
"""

import os
import sys

# ── 1. Ensure project root is on sys.path ──────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── 2. Default environment variables (override via cPanel UI) ──────────
os.environ.setdefault("AVALAI_API_KEY", "aa-PqX6XTobrcQv8r4zFGaIIhl4lur7e1kNswrKsIh2sAKjcczu")
os.environ.setdefault("SESSION_SECRET", "bichart-super-secret-key-change-in-production")

# ── 3. Import the FastAPI ASGI application ─────────────────────────────
from app import app  # noqa: E402

# ── 4. Wrap ASGI → WSGI for Phusion Passenger ─────────────────────────
from a2wsgi import WSGIMiddleware  # must be in requirements.txt

application = WSGIMiddleware(app)
