#!/bin/bash

cd /home/danamate/bichart
source /home/danamate/bichart/venv/bin/activate

# 1. Export core service keys
export AVALAI_API_KEY="aa-PqX6XTobrcQv8r4zFGaIIhl4lur7e1kNswrKsIh2sAKjcczu";
export GOOGLE_CLIENT_ID="287844662924-oq9gpis6urq8g7g35pmpnejq1vvk1ofv.apps.googleusercontent.com";

# 2. Automatically load all variables from .env if present (including TURNSTILE keys)
if [ -f "/home/danamate/bichart/.env" ]; then
    set -a
    source <(grep -v '^\s*#' /home/danamate/bichart/.env | grep -v '^\s*$' | sed -e 's/\r$//')
    set +a
fi

# 3. Explicit fallback for Turnstile
export TURNSTILE_SITE_KEY="${TURNSTILE_SITE_KEY:-}";
export TURNSTILE_SECRET_KEY="${TURNSTILE_SECRET_KEY:-}";

# 4. Check and start uvicorn if not running
if ! pgrep -f "uvicorn app:app" > /dev/null
then
    echo "Starting FastAPI..."

    nohup uvicorn app:app \
        --host 0.0.0.0 \
        --port 8000 \
        > /home/danamate/bichart/uvicorn.log 2>&1 &
fi
