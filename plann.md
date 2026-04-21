# CodeSentinal Hybrid Worker Plan (Render + Railway)

## Goal
Run backend on Render and worker on Railway.
Try Railway Redis first.
If it fails, move to Upstash Redis.

## Current Status
- [x] Render backend is deployed and running.
- [x] Render Postgres is deployed and running.
- [x] Railway worker is deployed and starts.
- [x] Celery error identified from logs: Redis host not reachable from Railway.
- [x] Upstash shared Redis is created (Plan B selected).
- [x] Shared Redis URL captured for deployment.
- [x] Worker is connected and consuming tasks.

## Why It Failed
Railway worker used Render internal Redis host.
Render internal host is private to Render network.
So Railway cannot resolve/connect to it.

## Architecture (Target)
```mermaid
flowchart LR
	 A[GitHub Webhook] --> B[Render FastAPI Backend]
	 B --> C[(Render Postgres)]
	 B --> D[(Shared Redis)]
	 E[Railway Celery Worker] --> D
	 E --> C
```

## Plan A (Try Railway Redis First)
1. Create Redis service in Railway.
2. Get Railway Redis connection URL.
3. Update Render backend env:
	- REDIS_URL
	- CELERY_BROKER_URL
	- CELERY_RESULT_BACKEND
4. Update Railway worker env with the exact same 3 values.
5. Redeploy Render backend and Railway worker.
6. Validate worker logs:
	- Expect: Connected to redis...
	- No more: Name or service not known

### Plan A Success Criteria
- [ ] Worker boots without Redis DNS/connect errors.
- [ ] A test scan job is consumed by worker.

## Plan B (Fallback If Plan A Fails)
Use Upstash Redis (public TLS URL) as shared Redis.

1. Create Upstash Redis.
2. Copy full Redis URL.
3. Set same URL in Render backend and Railway worker for:
	- REDIS_URL
	- CELERY_BROKER_URL
	- CELERY_RESULT_BACKEND
4. Redeploy both services.
5. Re-test worker logs and one scan task.

### Plan B Success Criteria
- [ ] Worker stable for 24h without Redis disconnect loops.

## Deployment Log (Latest)
- [x] Plan B chosen (free path).
- [x] Upstash database created: codesentinel-shared-redis (Oregon).
- [x] Redis TLS URL received and saved to session memory for this workspace.
- [x] Render backend env updated with shared Upstash Redis URL (+ TLS option in URL).
- [x] Railway worker env updated with shared Upstash Redis URL (+ TLS option in URL).
- [x] Both services redeployed.
- [x] Worker log verification passed (connected + ready).
- [ ] Frontend registration still fails from Vercel due to CORS/origin mismatch on Render.

## Register Failure Diagnosis
- Frontend is calling the correct API path: `/api/v1/auth/register`.
- The backend route exists at `/api/v1/auth/register`.
- The browser error shows CORS origin rejection, not a frontend route bug.
- No frontend code change is needed right now.

## Exact Render Fix For Register
Update Render backend env to include the deployed Vercel origin:
- FRONTEND_URL=https://code-sentinal-chi.vercel.app
- ALLOWED_ORIGINS=["https://code-sentinal-chi.vercel.app","http://localhost:5173"]

Keep these unchanged in Render:
- DATABASE_URL=postgresql+asyncpg://codesentinel_user:ZqrXa1IRhEvgxYSMJtgknltqAYV5svsf@dpg-d7j0ph7lk1mc73a74ep0-a.oregon-postgres.render.com/codesentinel_prod
- REDIS_URL=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379?ssl_cert_reqs=required
- CELERY_BROKER_URL=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379?ssl_cert_reqs=required
- CELERY_RESULT_BACKEND=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379?ssl_cert_reqs=required

## Frontend Env Still Required
- VITE_API_URL=https://codesentinal-ty40.onrender.com/api/v1

## Frontend Deployment (Vercel)

### Vercel Project Settings
- Root Directory: frontend
- Build Command: vite build
- Output Directory: dist

### Vercel Environment Variables
- VITE_API_URL=https://codesentinal-ty40.onrender.com/api/v1

### Render Backend Updates For Frontend
After Vercel gives final frontend URL, update these in Render backend:
- FRONTEND_URL=https://<your-vercel-domain>
- ALLOWED_ORIGINS=["https://<your-vercel-domain>"]

### Frontend Verification
1. Open deployed Vercel URL.
2. Open browser DevTools Network tab.
3. Confirm API calls go to https://codesentinal-ty40.onrender.com/api/v1/... and return 2xx/4xx (not CORS blocked).

## Next Steps (Exact)
1. In Render backend, set all 3 vars to the same Upstash URL:
	- REDIS_URL
	- CELERY_BROKER_URL
	- CELERY_RESULT_BACKEND
2. In Railway worker, set the same 3 vars to the same Upstash URL.
3. Redeploy Render backend.
4. Redeploy Railway worker.
5. Verify worker log has no Redis DNS/connect errors.
6. Trigger one scan from app and confirm worker picks it.

## Verification Strings To Check In Worker Logs
- Good: "Connected to redis" or worker becomes ready without retry loop.
- Bad: "Name or service not known" or repeated "Cannot connect to redis".

## Exact Execution Order (Fast)
1. Try Plan A (Railway Redis) first.
2. If worker fails to connect within 10 minutes, switch to Plan B.
3. Keep database unchanged (Render Postgres remains as is).

## Verification Strings To Check In Worker Logs
- Good: "Connected to redis" or worker becomes ready without retry loop.
- Bad: "Name or service not known" or repeated "Cannot connect to redis".

## Exact Execution Order (Fast)
1. Try Plan A (Railway Redis) first.
2. If worker fails to connect within 10 minutes, switch to Plan B.
3. Keep database unchanged (Render Postgres remains as is).

## GitHub App OAuth Configuration (Production)

### Discovery (2026-04-20)
- Registered user successfully on production app
- Clicked "Connect GitHub" button and was redirected to GitHub authorization page
- Authorized app with passkey (no login required — already authenticated with GitHub)
- After authorization, GitHub attempted callback but redirected to localhost (failed)
- Root cause identified: GitHub App Developer Settings still configured for localhost

### Why OAuth Initiation Worked but Callback Failed
- **OAuth flow start** only requires the GitHub App ID and manifest — works anywhere
- **OAuth callback** requires exact URL match in GitHub App settings — must point to live frontend
- Since settings still had localhost URLs, callback failed with "connection refused"

### Production Configuration Required
**Location:** https://github.com/settings/apps/codesentinel-devsecops → General tab

**Change these 4 URLs:**

| Setting | Current (Dev) | Production | Notes |
|---------|---------------|------------|-------|
| Homepage URL | `http://localhost:5173` | `https://code-sentinal-chi.vercel.app` | Public app link |
| Callback URL | `http://localhost:5173/app/repositories` | `https://code-sentinal-chi.vercel.app/app/repositories` | **CRITICAL** — OAuth redirect |
| Setup URL | `http://localhost:5173/app/repositories` | `https://code-sentinal-chi.vercel.app/app/repositories` | Post-install redirect |
| Webhook URL | `https://example.com/webhooks/github` | `https://codesentinal-ty40.onrender.com/webhooks/github` | GitHub event delivery |

**No credential changes needed on Render or Railway.**

### Next Step
After updating GitHub App settings above, test:
1. Click "Connect GitHub" again from Repositories page
2. Authorize the app
3. Should redirect back to https://code-sentinal-chi.vercel.app/app/repositories (not localhost)
4. Installation ID should be captured and repositories should load

## Important Notes
- Keep DATABASE_URL unchanged (Render external Postgres URL).
- Keep GITHUB_WEBHOOK_URL pointing to Render backend while backend stays on Render.
- FRONTEND_URL and ALLOWED_ORIGINS must be real deployed frontend URL in production.
