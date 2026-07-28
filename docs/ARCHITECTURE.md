# Architecture

## Modular Monolith (recommended for this product)

BiChart uses a **modular monolith**: one deployable FastAPI process with
strict **bounded-context modules**. This matches modern practice for
LLM/BI apps of this size (small team, shared SQLite, tightly coupled
text-to-SQL pipeline). True microservices can be peeled off later via the
Strangler Fig pattern when a module needs independent scale (e.g. LLM).

```
┌─────────────────────────────────────────────────────────────┐
│  app.py  (API gateway / composition root)                   │
│  auth middleware · static · include_router(...)             │
└─────────────┬───────────────────────────────────────────────┘
              │
   ┌──────────┼──────────┬──────────┬──────────┬──────────┐
   ▼          ▼          ▼          ▼          ▼          ▼
 identity   chat       llm      sql_guard   bi_data   reporting
 users+     orchestr.  avalai   SELECT-     engine+   PDF/Excel
 session    analyze    ollama   only +      mock
                       prompts  normalize
              │
         conversation · polls
         history/prefs   feature votes
```

| Module | Responsibility | Future microservice candidate |
|--------|----------------|------------------------------|
| `modules/identity` | Login, sessions, app_users CRUD | Auth service |
| `modules/llm` | AvalAI + Ollama providers | Inference service |
| `modules/sql_guard` | SQL safety / normalize | Policy sidecar |
| `modules/bi_data` | SQLAlchemy + mock seed | Data / warehouse API |
| `modules/chat` | Text-to-SQL orchestration | Query agent service |
| `modules/conversation` | History, prefs, feedback | Memory service |
| `modules/reporting` | PDF / Excel export | Report worker |
| `modules/polls` | Feature voting | Optional |

Root `*.py` files (`auth.py`, `database.py`, …) remain as **thin shims**
so Docker (`db_mock.py`) and older imports keep working.
