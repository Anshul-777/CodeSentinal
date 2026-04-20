#!/bin/bash
set -e

echo "=== CodeSentinel Backend Startup ==="

# Run database migrations before starting the server
# This is safe to run on every deploy â€” alembic skips already-applied migrations
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Start the uvicorn server
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
