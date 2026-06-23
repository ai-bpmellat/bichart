# PSP BI — Conversational Report Builder

A chat-based BI tool for a Payment Service Provider. Ask questions in
Persian or English ("نمایش تراکنش های دیروز" / "Show top 10 merchants by
volume"), and the app turns them into SQL via a local Gemma model, runs the
query against a row-level-secured mock transaction database, and follows up
with an AI-generated analysis/forecast — all rendered in a minimal chat UI
with a table and a lightweight bar chart.

## Why FastAPI instead of Flask

The brief allowed swapping frameworks if something fits better, so this
build uses **FastAPI + Uvicorn** rather than Flask. Reasoning: each chat
turn makes **two sequential, network-bound calls to Ollama** (SQL
generation, then analysis). FastAPI's native `async`/sync handling means a
slow Ollama response on one request doesn't have to block others, you get
free request validation via Pydantic, and interactive API docs at `/docs`
for testing the backend without the UI. Everything else — the pipeline
shape, file layout, prompts, and frontend — follows the brief as given.

## Project layout

```
psp_bi_chat/
├── app.py              # FastAPI app: routes /, /api/chat, /api/health, /api/login, /api/customers
├── database.py         # SQLAlchemy engine config — swap SQLite for DB2/SQL Server here
├── db_mock.py           # Generates schema + ~10k mock rows (run once)
├── auth.py              # Authorization: maps access_key -> customer, scopes SQL to owned merchants
├── sql_safety.py         # Validates SELECT-only SQL, blocks destructive statements, caps rows
├── ollama_client.py      # HTTP client for Ollama, with JSON-parsing fallback chain
├── memory_manager.py     # In-memory + history.json conversation persistence
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css
    └── script.js
```

## Pipeline (per chat message)

1. **Auth** — the request's `access_key` is matched to a row in `dim_customer`.
2. **Text-to-SQL** — Gemma is called with a strict JSON-only system prompt,
   producing `{"sql": ..., "explanation": ...}`.
3. **Safety check** — `sql_safety.py` rejects anything that isn't a single
   read-only `SELECT`/`WITH` statement (no `DROP`/`UPDATE`/`INSERT`/etc.),
   and caps the result at 100 rows.
4. **Authorization & scoping** *(added per your request)* — `auth.py`
   rewrites the query so every reference to `fact_transactions`,
   `dim_merchant`, or `dim_terminal` is wrapped in a subquery filtered to
   only the merchants that customer owns. Admin-role customers (PSP
   internal BI staff) bypass this and see all data. This runs even if the
   model never selected a `merchant_id` column — the FROM/JOIN clauses
   themselves are rewritten, not the result set.
5. **Execution** — the scoped SQL runs against SQLite via SQLAlchemy.
6. **Analysis** — the first 20 result rows + the original question are sent
   back to Gemma for a plain-text analysis/forecast.
7. **Memory** — the full turn (question, SQL, explanation, row count,
   analysis) is appended to in-process memory and to `history.json` on disk.

The frontend then renders: the user's question, a collapsible `<code>`
block with the generated SQL, the result table, an auto-generated bar chart
when the data shape supports one, and the analysis paragraph.

## Authorization model (demo)

`dim_customer` holds six demo companies, each with a plaintext `access_key`
(stand-in for a real API key / session token) and a `role` of `admin` or
`customer`. `dim_merchant.owner_customer_id` links each merchant to the
customer that owns it. Run `db_mock.py` to print the demo keys, or open the
app — the login screen lists them with one click to autofill.

To swap this for real authentication later: keep `auth.authorize_and_scope_sql()`
exactly as-is, and only replace `auth.get_customer_by_key()` with a lookup
against your real identity provider (JWT claim, session, OAuth token, etc.)
that still resolves to a `{"customer_id", "customer_name", "role"}` dict.

## Setup

### 1. Install Ollama and pull the model

```bash
# Install Ollama if you haven't: https://ollama.com/download
ollama pull gemma4:latest
```

> If `gemma4:latest` isn't available in your Ollama registry, substitute
> the closest model you have (e.g. `gemma2:latest` or `gemma3:latest`) and
> update `MODEL_NAME` in `ollama_client.py` to match.

Make sure the Ollama server is running:

```bash
ollama serve
```

### 2. Install Python dependencies

```bash
cd psp_bi_chat
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Generate the mock database (run once)

```bash
python db_mock.py
```

This creates `psp_bi_mock.db` with `dim_date`, `dim_customer`,
`dim_merchant`, `dim_terminal`, and `fact_transactions` (~10,000 rows),
including realistic Iranian PSP merchant names in Persian. It prints the
demo customer access keys at the end — keep that terminal output handy.
Re-running this script wipes and rebuilds the database.

### 4. Run the app

```bash
python app.py
```

or, for auto-reload during development:

```bash
uvicorn app:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser. Sign in with one of
the demo access keys shown on the login screen (click one to autofill),
and start asking questions.

### Quick health check

```bash
curl http://localhost:8000/api/health
```

Returns `{"db": "ok", "ollama": "ok"}` if both the database and Ollama are
reachable — useful for confirming the `127.0.0.1` / `trust_env=False`
Ollama connection settings in `ollama_client.py` are working on your machine
before testing through the UI.

## Notes on the Windows `localhost` → Ollama 503 issue

`ollama_client.py` connects to `http://127.0.0.1:11434` (not `localhost`)
and disables `requests`' environment-proxy lookup (`session.trust_env =
False`) before calling Ollama. This avoids the intermittent `503`/connection
errors some Windows setups hit when a system HTTP proxy variable interferes
with loopback requests, or when `localhost` resolves to `::1` while Ollama
is only listening on `127.0.0.1`.

## Switching the database later

Everything goes through `database.py`. To move off SQLite, set the
`DATABASE_URL` environment variable (or edit the default in `database.py`)
to your target, e.g.:

```bash
# DB2 (pip install ibm_db ibm_db_sa)
export DATABASE_URL="db2+ibm_db://user:password@host:50000/DBNAME"

# SQL Server (pip install pyodbc)
export DATABASE_URL="mssql+pyodbc://user:password@host/DBNAME?driver=ODBC+Driver+17+for+SQL+Server"
```

No other file needs to change — `app.py`, `auth.py`, and `db_mock.py` all
import `engine`/`SessionLocal` from `database.py`.
