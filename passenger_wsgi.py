"""
cPanel / Phusion Passenger entry point for FastAPI.

In cPanel → Setup Python App:
  - Application startup file: passenger_wsgi.py
  - Application entry point: application
"""

import os
import sys

# Ensure the app directory is on the import path.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from a2wsgi import ASGIMiddleware
from app import app

application = ASGIMiddleware(app)
