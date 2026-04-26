#!/usr/bin/env bash
# scripts/setup.sh — first-time local bootstrap.
#
# Verifies prerequisites, creates .venv via uv, syncs Python dependencies, and
# fails loudly with instructions if .env is missing.
#
# Usage:
#   ./scripts/setup.sh

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  cat <<'EOF' >&2
ERROR: uv is not installed.

Install it:
    curl -LsSf https://astral.sh/uv/install.sh | sh

Then re-run ./scripts/setup.sh.
EOF
  exit 1
fi

if [ ! -d .venv ]; then
  echo "[setup] creating .venv via uv venv..."
  uv venv
fi

echo "[setup] syncing dependencies (uv sync)..."
uv sync --quiet

if [ ! -f .env ]; then
  cat <<'EOF' >&2

ERROR: .env is missing.

Copy the template and fill in the keys you have:

    cp .env.example .env
    $EDITOR .env

Minimum keys for the demo:

  LOGFIRE_TOKEN          # required for live tracing on the top-bar button
  LOGFIRE_PROJECT_URL    # e.g. https://logfire.pydantic.dev/<org>/<project>
  PYDANTIC_AI_GATEWAY_API_KEY  # OR ANTHROPIC_API_KEY for direct Anthropic
  CAFETWIN_OPTIMIZATION_MODEL=gateway/anthropic:claude-sonnet-4-5

For an offline demo without external services, set:

  CAFETWIN_FORCE_FALLBACK=1

…in .env to use the cached recommendation instead of the live agent.

EOF
  exit 1
fi

echo
echo "[setup] done. next:"
echo "  ./scripts/test.sh    # verify backend tests pass"
echo "  ./scripts/dev.sh     # start backend + frontend"
