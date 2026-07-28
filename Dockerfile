FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 7860

# Hugging Face Spaces sets $PORT (default 7860). Create the demo DB if missing then start.
CMD ["sh", "-c", "test -f /app/data/psp_bi_mock.db || python /app/db_mock.py; uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]

