#!/usr/bin/env bash
# scripts/deploy_vercel.sh — deploy the static frontend to Vercel.
#
# Strategy: Vercel hosts cafetwin.html + assets, and Vercel rewrites all
# /api/* requests to the Render backend. The deployed frontend stays same-
# origin so no CORS preflight, no hardcoded backend URL in the JSX bundle.
#
# Prereqs:
#   - A Vercel account.
#   - vercel CLI (npm install -g vercel) OR npx available.
#   - One-time: vercel login.
#   - Render backend already deployed (see ./scripts/deploy_render.sh).
#
# Required env (or in .env):
#   CAFETWIN_RENDER_URL — full https URL of the Render backend, e.g.
#                         https://cafetwin-backend-tier1.onrender.com
#
# Usage:
#   ./scripts/deploy_vercel.sh

set -euo pipefail

cd "$(dirname "$0")/.."

# Pick up CAFETWIN_RENDER_URL etc. from .env if set there.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${CAFETWIN_RENDER_URL:-}" ]; then
  cat <<'EOF' >&2
ERROR: CAFETWIN_RENDER_URL is not set.

Set it to the full https URL of your deployed Render backend, e.g.

    CAFETWIN_RENDER_URL=https://cafetwin-backend-tier1.onrender.com

Either add that line to .env, or pass it on the command line:

    CAFETWIN_RENDER_URL=https://... ./scripts/deploy_vercel.sh

If you have not deployed the backend yet, run:

    ./scripts/deploy_render.sh
EOF
  exit 1
fi

# Strip any trailing slash so concatenated paths stay clean.
RENDER_URL="${CAFETWIN_RENDER_URL%/}"

# Sanity check: must be https://...
case "$RENDER_URL" in
  http://*|https://*) ;;
  *)
    echo "ERROR: CAFETWIN_RENDER_URL must start with http:// or https:// (got: $RENDER_URL)" >&2
    exit 1
    ;;
esac

# Resolve the Vercel CLI: prefer a globally-installed vercel, fall back to npx.
if command -v vercel >/dev/null 2>&1; then
  VERCEL=(vercel)
elif command -v npx >/dev/null 2>&1; then
  echo "[deploy_vercel] vercel CLI not found, falling back to: npx --yes vercel@latest"
  VERCEL=(npx --yes vercel@latest)
else
  echo "ERROR: vercel CLI not found and npx unavailable." >&2
  echo "  Install: npm install -g vercel" >&2
  exit 1
fi

echo "[deploy_vercel] Render backend: $RENDER_URL"
echo "[deploy_vercel] writing frontend/vercel.json with /api/* rewrite..."

# vercel.json is gitignored — generated fresh per deploy because the rewrite
# target is environment-specific.
cat > frontend/vercel.json <<EOF
{
  "version": 2,
  "rewrites": [
    { "source": "/api/(.*)", "destination": "$RENDER_URL/api/\$1" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=0, must-revalidate" }
      ]
    }
  ]
}
EOF

echo "[deploy_vercel] running 'vercel deploy --prod' from frontend/..."
echo "  (first-time runs will ask you to link or create a Vercel project)"
echo

( cd frontend && "${VERCEL[@]}" deploy --prod --yes )

cat <<EOF

[deploy_vercel] Done.

The deployed frontend serves cafetwin.html and rewrites /api/* to:
  $RENDER_URL

If the page loads but API calls 404, double-check that the Render backend is
reachable at that URL (curl ${RENDER_URL}/api/sessions should return JSON).
EOF
