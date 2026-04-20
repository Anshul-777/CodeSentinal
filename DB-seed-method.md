# CodeSentinel — Database Auto-Migration Method (Without Render Shell)

## The Problem

Render's free plan does **NOT** include Shell access.  
Shell access is the standard way to run `alembic upgrade head` to create database tables.  
Without it, every deployment starts with an **empty database** — the PostgreSQL instance exists and accepts connections, but has zero tables.

This means:
- The `/health` endpoint reports `"database": "connected"` (because `SELECT 1` works on an empty DB)
- But every actual query fails with `relation "users" does not exist`
- Registration, login, and all API endpoints crash with **500 Internal Server Error**

## The Solution: Docker Startup Script

Instead of running migrations manually via shell, we embed the migration command directly into the Docker container startup process.

### How It Works

#### 1. `backend/start.sh` — Startup Script

```bash
#!/bin/bash
set -e

echo "=== CodeSentinel Backend Startup ==="

# Run database migrations before starting the server
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Start the uvicorn server
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Key points:**
- `set -e` means the script will **stop** if migrations fail (so the container won't start with a broken DB)
- `alembic upgrade head` is **idempotent** — if tables already exist, it does nothing
- `exec` replaces the shell process with uvicorn (proper signal handling for container shutdown)
- This runs **every time** the container starts, including every Render redeploy

#### 2. `backend/Dockerfile` — Uses the Startup Script

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libffi-dev libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN grep -Ev "^(qdrant-client|sentence-transformers)==" requirements.txt > requirements.runtime.txt \
    && pip install --no-cache-dir -r requirements.runtime.txt

COPY . .

# Make startup script executable
RUN chmod +x start.sh

EXPOSE 8000
CMD ["bash", "start.sh"]
```

**Before** (broken):
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**After** (fixed):
```dockerfile
RUN chmod +x start.sh
CMD ["bash", "start.sh"]
```

#### 3. `backend/alembic/env.py` — Handles DATABASE_URL Automatically

The alembic env.py reads `DATABASE_URL` from the environment:

```python
db_url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "+psycopg2")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
```

**Critical detail:** The Render `DATABASE_URL` uses `postgresql+asyncpg://...` (async driver). But alembic migrations need the **sync** driver (`psycopg2`). The `.replace("+asyncpg", "+psycopg2")` handles this conversion automatically.

Both `asyncpg` and `psycopg2-binary` are in `requirements.txt`, so both drivers are available in the Docker image.

## What Tables Are Created

The migration file `backend/alembic/versions/001_initial_schema.py` creates ALL platform tables:

| # | Table | Purpose |
|---|-------|---------|
| 1 | `users` | User accounts (email, password hash, profile, notification prefs, tour state) |
| 2 | `organizations` | Multi-tenant workspaces (plan, limits, settings, compliance profiles) |
| 3 | `organization_members` | User-to-org membership with roles (owner, admin, developer, viewer) |
| 4 | `repositories` | Connected GitHub repos (installation ID, access tokens, scan config, webhook config) |
| 5 | `scans` | Security scan runs (status, agent results, risk scores, PR info) |
| 6 | `findings` | Individual security vulnerabilities found (severity, CVE, CWE, code location) |
| 7 | `fixes` | Auto-fix suggestions (diff patches, sandbox test results, PR links) |
| 8 | `audit_logs` | Action audit trail (who did what, when, from where) |
| 9 | `policies` | Security policies (block rules, severity thresholds, branch targeting) |
| 10 | `notification_configs` | Alert channels (Slack, Teams, email triggers, severity filters) |
| 11 | `integrations` | Third-party integrations (Jira, Linear, etc.) |

Plus associated indexes and foreign key constraints.

## How to Verify Tables Exist

### Option A: Check Render Logs After Deploy
After pushing to GitHub and Render auto-deploys, check the Render service logs for:
```
=== CodeSentinel Backend Startup ===
Running database migrations...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, Initial schema — all CodeSentinel tables
Migrations complete.
Starting uvicorn...
```

If you see `Running upgrade -> 001_initial`, tables were just created.  
If you see just `Context impl...Will assume transactional DDL` with no upgrade line, tables already exist (no-op).

### Option B: Test via API
After deploy, try registering a user at `https://code-sentinal-chi.vercel.app/register`.  
If it succeeds, the `users`, `organizations`, and `organization_members` tables all exist.

### Option C: Via psql (External Connection)
If you have `psql` installed locally:
```bash
PGPASSWORD=ZqrXa1IRhEvgxYSMJtgknltqAYV5svsf psql -h dpg-d7j0ph7lk1mc73a74ep0-a.oregon-postgres.render.com -U codesentinel_user codesentinel_prod
```
Then run: `\dt` to list all tables.

## How to Add New Tables in the Future

1. Create a new model in `backend/app/models/`
2. Import it in `backend/app/models/__init__.py`
3. Generate a new migration:
   ```bash
   cd backend
   alembic revision --autogenerate -m "add_new_table_name"
   ```
4. Review the generated migration in `backend/alembic/versions/`
5. Commit and push to GitHub
6. Render auto-deploys → `start.sh` runs → `alembic upgrade head` applies the new migration
7. No manual intervention needed!

## Important Notes

- **Never delete** `backend/alembic/versions/001_initial_schema.py` — it's the base migration
- **Line endings matter**: `start.sh` MUST have Unix line endings (LF, not CRLF). Windows editors may save with CRLF which causes `bash: start.sh: not found` errors in the Linux Docker container
- **The migration is idempotent**: Running `alembic upgrade head` multiple times is safe. It only applies pending migrations
- **Render Postgres uses INTERNAL hostname** for services on the same Render account. The DATABASE_URL should use the internal hostname (`dpg-xxx-a`) not the external one (`dpg-xxx-a.oregon-postgres.render.com`) for the web service
- **Railway worker uses EXTERNAL hostname** since Railway is a different cloud provider and cannot access Render's internal network
