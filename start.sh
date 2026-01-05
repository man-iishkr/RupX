#!/bin/bash
# start.sh - Optimized start script for Render

# Set memory limits
export MALLOC_ARENA_MAX=2
export PYTHONUNBUFFERED=1

# Start gunicorn with optimized settings
exec gunicorn backend.app:app \
  --worker-class gevent \
  --workers 1 \
  --threads 2 \
  --worker-connections 100 \
  --max-requests 500 \
  --max-requests-jitter 50 \
  --timeout 120 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --bind 0.0.0.0:$PORT \
  --log-level info \
  --access-logfile - \
  --error-logfile -