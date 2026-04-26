#!/usr/bin/env bash
# scripts/transcode_annotated_for_web.sh
#
# Tier 1D — produce H.264-encoded `annotated_before.web.mp4` siblings for
# every session that has an `annotated_before.mp4` on disk.
#
# Why: `cv2.VideoWriter` defaults to the `mp4v` fourcc (MPEG-4 part 2),
# which Chromium's HTML5 `<video>` element rejects with
# MEDIA_ERR_SRC_NOT_SUPPORTED. The frontend canvas (real CCTV pane) needs
# H.264 to play. We keep the original raw `.mp4` because it's the YOLO
# script's direct output and useful for debugging in non-browser tools.
#
# The `.web.mp4` artifacts are gitignored so a fresh clone regenerates
# them locally after running `scripts/run_yolo_offline.py` (Tier 1B).
#
# Usage:
#   ./scripts/transcode_annotated_for_web.sh                # all sessions
#   ./scripts/transcode_annotated_for_web.sh ai_cafe_a      # specific session

set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg is required but not installed." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSIONS_DIR="$REPO_ROOT/demo_data/sessions"

if [[ $# -gt 0 ]]; then
  TARGETS=("$@")
else
  TARGETS=()
  for d in "$SESSIONS_DIR"/*/; do
    [[ -d "$d" ]] || continue
    TARGETS+=("$(basename "$d")")
  done
fi

count=0
for sid in "${TARGETS[@]}"; do
  src="$SESSIONS_DIR/$sid/annotated_before.mp4"
  dst="$SESSIONS_DIR/$sid/annotated_before.web.mp4"
  if [[ ! -f "$src" ]]; then
    echo "[skip] $sid — no annotated_before.mp4 (run scripts/run_yolo_offline.py first)" >&2
    continue
  fi
  echo "[transcode] $sid → annotated_before.web.mp4"
  ffmpeg -y -loglevel error \
    -i "$src" \
    -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -movflags +faststart \
    -an \
    "$dst"
  ls -lh "$dst" | awk '{print "    " $5 "  " $9}'
  count=$((count + 1))
done

if [[ $count -eq 0 ]]; then
  echo "No sessions transcoded. Run scripts/run_yolo_offline.py first." >&2
  exit 1
fi
echo "[done] transcoded $count session(s)"
