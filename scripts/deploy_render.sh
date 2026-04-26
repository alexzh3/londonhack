#!/usr/bin/env bash
# scripts/deploy_render.sh — deploy the FastAPI backend to Render.com.
#
# Render is configured via render.yaml (Infrastructure-as-Code). The first
# deploy is a one-time GitHub connect + Blueprint create in the Render
# dashboard; subsequent deploys are either automatic on git push or
# triggered via the deploy hook URL.
#
# Modes:
#   1. First-time setup (default): prints the steps to follow in the Render
#      dashboard.
#   2. Trigger redeploy: if RENDER_DEPLOY_HOOK is set in .env or env, this
#      script POSTs to it to kick off a fresh build without going through
#      the dashboard.
#   3. Smoke test: if CAFETWIN_RENDER_URL is set, runs the smoke script
#      against the live URL after deploy.
#
# Usage:
#   ./scripts/deploy_render.sh
#   RENDER_DEPLOY_HOOK=... ./scripts/deploy_render.sh
#   CAFETWIN_RENDER_URL=https://... ./scripts/deploy_render.sh --smoke

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f render.yaml ]; then
  echo "ERROR: render.yaml is missing at the repo root." >&2
  echo "  Restore from git or recreate it before deploying." >&2
  exit 1
fi

# Pick up RENDER_DEPLOY_HOOK / CAFETWIN_RENDER_URL from .env if set there.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

run_smoke=0
for arg in "$@"; do
  case "$arg" in
    --smoke) run_smoke=1 ;;
  esac
done

if [ -n "${RENDER_DEPLOY_HOOK:-}" ]; then
  echo "[deploy_render] triggering Render deploy hook..."
  if curl -fsS -X POST "$RENDER_DEPLOY_HOOK" >/dev/null; then
    echo "[deploy_render] deploy queued. Watch progress at https://dashboard.render.com"
  else
    echo "ERROR: deploy hook POST failed. Check that RENDER_DEPLOY_HOOK is correct." >&2
    exit 1
  fi
else
  cat <<'EOF'

[deploy_render] First-time setup walkthrough:

  1. Push this repo (with render.yaml) to GitHub.

  2. Open https://dashboard.render.com → New → Blueprint.
     Connect your GitHub repo. Render reads render.yaml and provisions the
     `cafetwin-backend` web service.

  3. In the service Environment tab, set these secrets (do NOT commit them):

        LOGFIRE_TOKEN
        LOGFIRE_PROJECT_URL
        ANTHROPIC_API_KEY              (or PYDANTIC_AI_GATEWAY_API_KEY)
        PYDANTIC_AI_GATEWAY_ROUTE      (if using Gateway)
        MUBIT_API_KEY                  (optional; Tier 1)

  4. Once the service is live, copy its public URL (e.g.
        https://cafetwin-backend.onrender.com)
     into your local .env as:

        CAFETWIN_RENDER_URL=https://cafetwin-backend.onrender.com

     Then run ./scripts/deploy_vercel.sh to ship the frontend.

  5. (Optional) Copy the deploy hook URL from
        Render → cafetwin-backend → Settings → Deploy Hook
     into .env as:

        RENDER_DEPLOY_HOOK=https://api.render.com/deploy/srv-...?key=...

     Subsequent runs of ./scripts/deploy_render.sh will use that hook to
     trigger a fresh deploy without going through the dashboard.

EOF
fi

if [ "$run_smoke" -eq 1 ]; then
  if [ -z "${CAFETWIN_RENDER_URL:-}" ]; then
    echo "[deploy_render] --smoke requested but CAFETWIN_RENDER_URL is not set." >&2
    exit 1
  fi
  echo
  echo "[deploy_render] smoke-testing $CAFETWIN_RENDER_URL ..."
  SMOKE_BASE="$CAFETWIN_RENDER_URL" "$(dirname "$0")/smoke.sh"
fi
