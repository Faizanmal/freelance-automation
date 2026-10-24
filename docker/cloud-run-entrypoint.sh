#!/bin/sh
# Cloud Run entrypoint: SERVICE_ROLE=api|worker|beat
# API listens on $PORT. Worker/beat run a tiny HTTP probe so Cloud Run
# accepts the service while Celery stays the main process.
set -eu

ROLE="${SERVICE_ROLE:-api}"
PORT="${PORT:-8080}"

start_probe() {
  python -c "
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ.get('PORT', '8080'))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *_args):
        return

HTTPServer(('0.0.0.0', port), Handler).serve_forever()
" &
  PROBE_PID=$!
  trap 'kill "$PROBE_PID" 2>/dev/null || true' EXIT INT TERM
}

case "$ROLE" in
  api)
    alembic -c database/alembic.ini upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers
    ;;
  worker)
    start_probe
    celery -A workers.app.celery_app worker --loglevel=info --concurrency=2 &
    CELERY_PID=$!
    wait "$CELERY_PID"
    ;;
  beat)
    start_probe
    celery -A workers.app.celery_app beat --loglevel=info &
    CELERY_PID=$!
    wait "$CELERY_PID"
    ;;
  *)
    echo "Unknown SERVICE_ROLE='$ROLE' (expected api|worker|beat)" >&2
    exit 1
    ;;
esac
