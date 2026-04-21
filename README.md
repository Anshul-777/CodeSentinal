# CodeSentinel — AI-Powered DevSecOps Security Platform

A production-grade, 5-agent AI security platform that integrates directly into your GitHub CI/CD pipeline via GitHub App. Scans every pull request for vulnerabilities, checks real CVEs, enforces compliance, generates auto-fixes, and posts results back as GitHub Check Runs — with merge blocking for critical issues.

## Architecture

```
GitHub PR/Push
     │
     ▼  HMAC-validated webhook
FastAPI Backend (Python)
     │
     ├── Celery Task Queue (Redis)
     │        │
     │        └── 5-Agent Pipeline (parallel)
     │              ├── Agent 1: Static Analysis (Bandit + AST + LLM)
     │              ├── Agent 2: Dependency (OSV.dev CVE + SBOM)
     │              ├── Agent 3: Business Logic (LLM semantic)
     │              ├── Agent 4: Auto-Fix (patch + sandbox verify)
     │              └── Agent 5: Compliance (SOC2/HIPAA/PCI/GDPR)
     │
     ├── PostgreSQL (all state, findings, fixes, audit logs)
     └── React Frontend (real-time pipeline visualizer)
```

## Tech Stack

|----------------------|------------------------------------------------|
|        Layer         |                   Technology                   |
|----------------------|------------------------------------------------|
| Backend API          | FastAPI 0.111, Python 3.12                     |
| Database             | PostgreSQL 15 + SQLAlchemy 2.0 async           |
| Task Queue           | Celery 5.4 + Redis                             |
| AI — Local           | Ollama + CodeLlama 13B                         |
| AI — Cloud Free      | Groq (Llama 3.1 70B)                           |
| AI — Optional        | OpenAI, Anthropic, Gemini                      |
| Static Analysis      | Bandit, custom AST scanner                     |
| CVE Database         | OSV.dev API (free, no key needed)              |
| Frontend             | React 18 + TypeScript + Vite + Tailwind        |
| Auth                 | JWT (RS256) + bcrypt                           |
| GitHub Integration   | GitHub App (webhooks, check runs, PR reviews)  |
|----------------------|------------------------------------------------|

## Quick Start

See [RUN.md](RUN.md) for complete setup instructions.

```bash
# 1. Clone and setup
git clone <repo> codesentinel && cd codesentinel

# 2. Backend
cd backend && cp .env.example .env
# Edit .env with your PostgreSQL and Redis URLs
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_test_account.py
uvicorn app.main:app --reload

# 3. Frontend (new terminal)
cd frontend && npm install && npm run dev

# 4. Celery worker (new terminal)
cd backend && celery -A app.core.celery_app worker --loglevel=info
```

## Test Account

After running `seed_test_account.py`, log in with these credentials (share in chat only — never displayed in UI):

- **Email:** `sentinel.test@codesentinel.dev`
- **Password:** `CodeSentinel#Test2024`

This account has `is_test_user=True` which enables the guided product tour.

## Test Repository

Generate a real vulnerable Flask app to test with:

```bash
cd backend
python tests/generate_test_repo.py
cd codesentinel-test-app
git init && git add . && git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/codesentinel-test-app.git
git push -u origin main
```

Then connect it in the Repositories page and open a PR.

## Environment Variables

See `backend/.env.example` for all available settings with documentation.

**Required:**
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis URL
- `JWT_SECRET_KEY` — Random 64-char string

**For GitHub integration:**
- `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_WEBHOOK_SECRET`
- `GITHUB_APP_NAME` should be a unique app slug like `CodeSentinelAI` if `Code-Sentinel` is reserved for your account.
- `GITHUB_WEBHOOK_URL` should point to your permanent public backend URL ending in `/webhooks/github`.

**For AI (at least one):**
- `OLLAMA_BASE_URL` (default: local, no config needed)
- `GROQ_API_KEY` (free at console.groq.com)

## AI Model Configuration

The system uses a fallback chain: **Ollama (local) → Groq (free) → OpenAI → Anthropic**

To use local models:
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull codellama:13b
```

To use Groq (free tier, no credit card):
1. Register at https://console.groq.com
2. Copy your API key
3. Add `GROQ_API_KEY=gsk_your_key` to `.env`

## Features

- **5-Agent Security Pipeline** — static analysis, dependency CVE lookup, business logic review, auto-fix, compliance
- **Real CVE Detection** — queries OSV.dev (Google's vulnerability database) for every dependency
- **Auto-Fix with Sandbox Verification** — generates patches, tests in isolation, only marks verified if validation passes
- **GitHub App Integration** — webhooks, check runs, PR reviews, merge blocking
- **Compliance** — SOC2, HIPAA, PCI-DSS 4.0, GDPR Article 32 rule packs
- **SBOM Generation** — Software Bill of Materials in SPDX format
- **Secret Scanning** — 15+ secret pattern types (AWS, GitHub, Stripe, etc.)
- **Policy-as-Code** — configurable blocking rules per repository
- **Audit Logs** — immutable trail of all security-relevant actions
- **RBAC** — Owner, Admin, Analyst, Developer, Viewer roles
- **Multi-tenant** — organization/workspace separation
- **AI Model Switching** — Ollama, Groq, OpenAI, Anthropic, Gemini, OpenRouter
- **False Positive Feedback** — mark findings as false positives to improve future scans
- **Observability Dashboard** — system health, queue depth, scan metrics

## Deployment

### Render (Backend)
1. Create PostgreSQL database on Render
2. Create Redis instance on Render
3. Create Web Service: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Create Worker: `celery -A app.core.celery_app worker --loglevel=info`
5. Set all environment variables in Render dashboard

### Vercel (Frontend)
1. Set `VITE_API_URL=https://your-backend.onrender.com/api/v1`
2. Deploy with: `npm run build`

See [RUN.md](RUN.md) for full deployment guide.
