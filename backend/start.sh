#!/bin/bash
set -e

echo "=== CodeSentinel Backend Startup ==="

# Run database migrations before starting the server
# This is safe to run on every deploy - alembic skips already-applied migrations
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Start the Celery worker in the background if not explicitly disabled
# This allows the app to work on single-service hosting plans like Render Free Tier
if [ "$SKIP_WORKER" != "true" ]; then
    echo "Starting Celery worker in background..."
    celery -A app.core.celery_app worker --loglevel=info -Q default,scans,agents --concurrency=2 &
fi

# Start the uvicorn server
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
