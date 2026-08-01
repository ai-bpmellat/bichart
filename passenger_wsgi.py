"""
cPanel / Phusion Passenger entry point for FastAPI.

cPanel -> Setup Python App configuration:
  - Python Version: 3.8+ (3.10 / 3.11 recommended)
  - Application root: /home/username/public_html (or project directory)
  - Application URL: https://yourdomain.com
  - Application startup file: passenger_wsgi.py
  - Application entry point: application
  - Environment Variables (optional in cPanel UI):
      AVALAI_API_KEY = your_avalai_api_key
      SESSION_SECRET = your_session_secret
"""

import os
import sys

# 1. Ensure project root directory is at the top of sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 2. Set default environment variables if not set in server environment
os.environ.setdefault("AVALAI_API_KEY", "aa-PqX6XTobrcQv8r4zFGaIIhl4lur7e1kNswrKsIh2sAKjcczu")
os.environ.setdefault("SESSION_SECRET", "bichart-super-secret-key-change-in-production")

# 3. Import FastAPI ASGI application
from app import app

# 4. Wrap ASGI app into WSGI application for Phusion Passenger
try:
    from a2wsgi import WSGIMiddleware
    application = WSGIMiddleware(app)
except ImportError:
    from asgiref.wsgi import WsgiToAsgi
    application = WsgiToAsgi(app)
