"""
cPanel / Phusion Passenger entry point for FastAPI.

Phusion Passenger on cPanel speaks WSGI, but FastAPI is an ASGI app.
We use 'a2wsgi' to bridge ASGI -> WSGI.
"""

from __future__ import annotations

import os
import sys
import traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PROJECT_ROOT, "passenger_debug.log")
STDERR_FILE = os.path.join(PROJECT_ROOT, "stderr.log")

# Force all low-level Python errors to write to stderr.log
sys.stderr = open(STDERR_FILE, "a", encoding="utf-8")
sys.stdout = sys.stderr


def log_debug(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


# ── 1. Ensure project root is on sys.path ──────────────────────────────
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── 2. Add ONLY the matching virtualenv site-packages for this Python version ──
USER_HOME = os.path.expanduser("~")
py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"  # e.g. "3.11"

# Add lib64 (C-extensions / wheels) and lib (pure python) for the CURRENT version only!
venv_lib64 = os.path.join(USER_HOME, "virtualenv", "bichart", py_ver, "lib64", f"python{py_ver}", "site-packages")
venv_lib = os.path.join(USER_HOME, "virtualenv", "bichart", py_ver, "lib", f"python{py_ver}", "site-packages")

for p in [venv_lib64, venv_lib]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
        log_debug(f"Added matching site-packages: {p}")

# ── 3. Load environment variables (.env file + defaults) ───────────────
_env_file = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(_env_file):
    try:
        with open(_env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and v:
                        os.environ[k] = v
    except Exception as exc:
        log_debug(f"Notice loading .env: {exc}")

os.environ.setdefault("AVALAI_API_KEY", "aa-PqX6XTobrcQv8r4zFGaIIhl4lur7e1kNswrKsIh2sAKjcczu")
os.environ.setdefault("SESSION_SECRET", "bichart-super-secret-key-change-in-production")
os.environ.setdefault("GOOGLE_CLIENT_ID", "287844662924-oq9gpis6urq8g7g35pmpnejq1vvk1ofv.apps.googleusercontent.com")
os.environ.setdefault("TURNSTILE_SITE_KEY", os.environ.get("TURNSTILE_SITE_KEY", ""))
os.environ.setdefault("TURNSTILE_SECRET_KEY", os.environ.get("TURNSTILE_SECRET_KEY", ""))

# ── 4. Import and wrap the FastAPI application ─────────────────────────
_startup_error = None
try:
    from app import app
    from a2wsgi import WSGIMiddleware

    application = WSGIMiddleware(app)
    log_debug("Successfully initialized WSGIMiddleware(app)")

except Exception as exc:
    _startup_error = traceback.format_exc()
    log_debug(f"STARTUP ERROR:\n{_startup_error}")

    def error_application(environ, start_response):
        status = "500 Internal Server Error"
        body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>BiChart - Passenger Startup Error</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace; background: #0f172a; color: #f8fafc; padding: 30px; line-height: 1.5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 25px; border: 1px solid #334155; }}
        h1 {{ color: #ef4444; font-size: 22px; margin-top: 0; }}
        h2 {{ color: #38bdf8; font-size: 16px; margin-top: 20px; border-bottom: 1px solid #334155; padding-bottom: 5px; }}
        pre {{ background: #0b0f19; padding: 15px; border-radius: 8px; overflow-x: auto; color: #fca5a5; font-size: 13px; border: 1px solid #450a0a; }}
        .info {{ background: #0b0f19; padding: 12px; border-radius: 8px; font-size: 13px; color: #94a3b8; }}
        ul {{ margin: 5px 0; padding-left: 20px; }}
        li {{ margin-bottom: 3px; word-break: break-all; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ BiChart Startup Exception</h1>
        <p>Phusion Passenger encountered an error while starting the Python application:</p>
        <pre>{_startup_error}</pre>

        <h2>Python Environment</h2>
        <div class="info">
            <p><strong>Python Executable:</strong> {sys.executable}</p>
            <p><strong>Python Version:</strong> {sys.version}</p>
            <p><strong>Working Directory:</strong> {os.getcwd()}</p>
        </div>

        <h2>sys.path ({len(sys.path)} entries)</h2>
        <div class="info">
            <ul>
                {"".join(f"<li>{p}</li>" for p in sys.path)}
            </ul>
        </div>
    </div>
</body>
</html>"""
        response_headers = [
            ("Content-type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body.encode("utf-8")))),
        ]
        start_response(status, response_headers)
        return [body.encode("utf-8")]

    application = error_application
