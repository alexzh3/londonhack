#!/usr/bin/env bash
# scripts/dev.sh — local development: backend + frontend in parallel.
#
# Backend  (FastAPI + uvicorn --reload):  http://127.0.0.1:8000
# Frontend (python -m http.server):       http://127.0.0.1:5500/cafetwin.html
#
# Override ports via env: BACKEND_PORT=8001 FRONTEND_PORT=5501 ./scripts/dev.sh
#
# Press Ctrl-C to stop both servers.

set -euo pipefail

cd "$(dirname "$0")/.."

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5500}"

if [ ! -d .venv ]; then
  echo "ERROR: .venv missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env missing. Run ./scripts/setup.sh first (it explains what to put in it)." >&2
  exit 1
fi

# Refuse to start if the requested ports are already taken — clearer than a
# late uvicorn ImportError or the frontend silently colliding.
port_in_use() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :$p" 2>/dev/null | grep -q LISTEN
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$p" -sTCP:LISTEN -n -P >/dev/null 2>&1
  else
    return 1
  fi
}
for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if port_in_use "$p"; then
    echo "ERROR: port $p is already in use. Stop the other process or override BACKEND_PORT/FRONTEND_PORT." >&2
    exit 1
  fi
done

cleanup() {
  echo
  echo "[dev] shutting down..."
  if [ -n "${BACKEND_PID:-}" ];  then kill "$BACKEND_PID"  2>/dev/null || true; fi
  if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[dev] starting backend on :${BACKEND_PORT}..."
.venv/bin/uvicorn app.api.main:app --reload --host 127.0.0.1 --port "${BACKEND_PORT}" &
BACKEND_PID=$!

echo "[dev] starting frontend static server on :${FRONTEND_PORT}..."
( cd frontend && exec ../.venv/bin/python -m http.server "${FRONTEND_PORT}" --bind 127.0.0.1 ) &
FRONTEND_PID=$!

# Give uvicorn a moment to bind before printing URLs.
sleep 1

cat <<EOF

  cafetwin · local dev

    Backend  → http://127.0.0.1:${BACKEND_PORT}
    Frontend → http://127.0.0.1:${FRONTEND_PORT}/cafetwin.html

  Press Ctrl-C to stop both.

EOF

wait
