#!/usr/bin/env bash
# scripts/test.sh — run pytest and ruff against the backend.
#
# Usage:
#   ./scripts/test.sh
#
# Tests deliberately blank local secret env via tests/conftest.py so this is
# safe to run with a populated .env — it will not export traces or hit the
# Pydantic AI Gateway.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "ERROR: .venv missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi

echo "[test] pytest..."
.venv/bin/pytest -q

echo
echo "[test] ruff check app tests..."
.venv/bin/ruff check app tests

echo
echo "[test] all green."
