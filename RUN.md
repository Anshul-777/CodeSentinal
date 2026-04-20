# Running CodeSentinel in VS Code

## Prerequisites

Install these before starting:

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | https://python.org |
| Node.js | 20+ | https://nodejs.org |
| PostgreSQL | 15+ | https://postgresql.org/download |
| Redis | 7+ | https://redis.io/download |
| Ollama (optional) | latest | https://ollama.com/download |

---

## Step 1 — Clone and open in VS Code

```bash
git clone <your-repo-url> codesentinel
cd codesentinel
code .
```

---

## Step 2 — Database Setup

```bash
# Start PostgreSQL (macOS with Homebrew)
brew services start postgresql@15

# Or on Linux
sudo systemctl start postgresql

# Create database and user
psql -U postgres -c "CREATE USER codesentinel WITH PASSWORD 'password';"
psql -U postgres -c "CREATE DATABASE codesentinel OWNER codesentinel;"
```

---

## Step 3 — Redis Setup

```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis-server

# Verify
redis-cli ping  # should return: PONG
```

---

## Step 4 — Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Open .env and set at minimum:
# DATABASE_URL=postgresql+asyncpg://codesentinel:password@localhost:5432/codesentinel
# REDIS_URL=redis://localhost:6379/0
# JWT_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_urlsafe(64))">
# ENCRYPTION_KEY=<run: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Run database migrations
alembic upgrade head

# Seed the test account (one-time)
python scripts/seed_test_account.py
```

---

## Step 5 — (Optional) Install Ollama for local AI

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh  # Linux/macOS

# Pull a code model (choose one based on your RAM)
ollama pull codellama:7b    # 4GB RAM minimum
ollama pull codellama:13b   # 8GB RAM recommended
ollama pull llama3.1:8b     # Alternative general model

# Verify
ollama list
```

**OR** use Groq free tier instead:
1. Register at https://console.groq.com (free, no credit card)
2. Create an API key
3. Add `GROQ_API_KEY=gsk_your_key` to `backend/.env`

---

## Step 6 — Start the Backend (Terminal 1)

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     CodeSentinel starting up env=development version=1.0.0
INFO:     Database connection verified
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## Step 7 — Start Celery Worker (Terminal 2)

```bash
cd backend
source .venv/bin/activate
celery -A app.core.celery_app worker --loglevel=info -Q default,scans,agents
```

---

## Step 8 — Start Frontend (Terminal 3)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Step 9 — Set up GitHub App (for real scans)

1. Go to https://github.com/settings/apps/new
2. Fill in:
   - **App name:** codesentinel-yourname
   - **Homepage URL:** http://localhost:5173
   - **Webhook URL:** Use ngrok: `ngrok http 8000` → `https://xxxx.ngrok.io/webhooks/github`
   - **Webhook secret:** Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
3. **Permissions:**
   - Repository: Contents (Read), Pull requests (Read & Write), Checks (Read & Write), Issues (Read & Write), Metadata (Read), Commit statuses (Read & Write)
4. **Events:** Pull request, Push, Check run, Check suite
5. Click **Create GitHub App**
6. Generate a **Private Key** and download the .pem file
7. Copy values to `backend/.env`:
   ```
   GITHUB_APP_ID=your_app_id
   GITHUB_APP_NAME=codesentinel-yourname
   GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
   GITHUB_APP_WEBHOOK_SECRET=your_webhook_secret
   GITHUB_APP_CLIENT_ID=Iv1.xxxxx
   GITHUB_APP_CLIENT_SECRET=your_client_secret
   ```

---

## Step 10 — Create and connect a test repository

```bash
# Generate the test repo
cd backend
python tests/generate_test_repo.py

# Initialize and push to GitHub
cd codesentinel-test-app
git init
git add .
git commit -m "Initial commit — vulnerable Flask app for CodeSentinel testing"
git remote add origin https://github.com/YOUR_USERNAME/codesentinel-test-app.git
git push -u origin main
```

Then in CodeSentinel:
1. Go to **Repositories** → **Connect GitHub**
2. Install the GitHub App on your `codesentinel-test-app` repo
3. The repo will appear in your dashboard

---

## Step 11 — Trigger your first scan

```bash
# Create a feature branch
cd codesentinel-test-app
git checkout -b feature/test-scan
echo "# test change" >> README.md
git add . && git commit -m "Test PR for CodeSentinel scan"
git push -u origin feature/test-scan
```

Then open a Pull Request from `feature/test-scan` → `main` on GitHub.

Watch the 5-agent pipeline run in real-time in your CodeSentinel dashboard at **Scans** → click the scan.

---

## Test Account

Log in with these credentials to see the product tour and guided experience:

```
Email:    sentinel.test@codesentinel.dev
Password: CodeSentinel#Test2024
```

(Keep private — do not share publicly)

---

## VS Code Recommended Extensions

Install these for the best development experience:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next",
    "mtxr.sqltools",
    "mtxr.sqltools-driver-pg"
  ]
}
```

---

## VS Code Launch Configuration

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Backend",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/backend/.env"
    }
  ]
}
```

---

## Deployment to Render + Vercel

### Backend on Render

1. Push code to GitHub
2. Go to https://render.com → New → Web Service
3. Connect your repo, set:
   - **Build command:** `pip install -r requirements.txt && alembic upgrade head`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add PostgreSQL and Redis from Render dashboard
5. Set all environment variables

### Celery Worker on Render

Create another Render service (Background Worker):
- **Start command:** `celery -A app.core.celery_app worker --loglevel=info`

### Frontend on Vercel

```bash
cd frontend
# Set environment variable
echo "VITE_API_URL=https://your-backend.onrender.com/api/v1" > .env.production
npm run build

# Deploy
npx vercel --prod
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `asyncpg` connection refused | Check PostgreSQL is running and DATABASE_URL is correct |
| `celery` tasks not running | Verify Redis is running: `redis-cli ping` |
| GitHub webhooks not arriving | Use ngrok and update webhook URL in GitHub App settings |
| LLM not responding | Check `GROQ_API_KEY` or ensure Ollama is running with `ollama list` |
| `ENCRYPTION_KEY` error | Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| Alembic migration fails | Check DATABASE_URL uses `+psycopg2` not `+asyncpg` for migrations |
