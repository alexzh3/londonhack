#!/usr/bin/env bash
# scripts/smoke.sh — hit a running CafeTwin backend and verify response shapes.
#
# Default target: http://127.0.0.1:8000.
# Override:        SMOKE_BASE=https://your-backend.onrender.com ./scripts/smoke.sh
#
# Useful after starting ./scripts/dev.sh in another terminal, or after a Render
# deploy to confirm the frontend will get the shapes it expects.

set -euo pipefail

BASE="${SMOKE_BASE:-http://127.0.0.1:8000}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is not installed." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed (used to validate JSON shapes)." >&2
  exit 1
fi

echo "[smoke] target: $BASE"

echo
echo "[smoke] GET /api/sessions"
curl -fsS "$BASE/api/sessions" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert isinstance(d, list), 'expected list'
assert any(s['slug'] == 'ai_cafe_a' for s in d), 'ai_cafe_a session manifest missing'
print(f'  ok · {len(d)} session(s)')
"

echo
echo "[smoke] GET /api/state?session_id=ai_cafe_a"
curl -fsS "$BASE/api/state?session_id=ai_cafe_a" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['missing_required'] == [], f'missing fixtures: {d[\"missing_required\"]}'
assert d['pattern']['id'] == 'pattern_queue_counter_crossing', 'unexpected pattern id'
print(f'  ok · {len(d[\"kpi_windows\"])} kpi windows · {len(d[\"object_inventory\"][\"objects\"])} objects · {len(d[\"zones\"])} zones')
"

echo
echo "[smoke] POST /api/run {session_id: ai_cafe_a}"
curl -fsS -X POST "$BASE/api/run" \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"ai_cafe_a"}' | python3 -c "
import json, sys
d = json.load(sys.stdin)
stages = [s['name'] for s in d['stages']]
assert stages == ['evidence_pack', 'optimization_agent', 'memory_write'], f'unexpected stages: {stages}'
lc = d['layout_change']
assert lc.get('fingerprint'), 'layout_change.fingerprint missing'
assert lc.get('evidence_ids'), 'layout_change.evidence_ids empty'
assert lc.get('expected_kpi_delta'), 'layout_change.expected_kpi_delta empty'
assert isinstance(lc['simulation']['from_position'], list)
print(f'  ok · used_fallback={d[\"used_fallback\"]} · prior_count={d[\"prior_recommendation_count\"]}')
print(f'  logfire_trace_url: {d[\"logfire_trace_url\"] or \"(none)\"}')
"

echo
echo "[smoke] POST /api/feedback {decision: reject}"
curl -fsS -X POST "$BASE/api/feedback" \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"ai_cafe_a","pattern_id":"pattern_queue_counter_crossing","proposal_fingerprint":"ai_cafe_a_open_pickup_lane_v1","decision":"reject","reason":"smoke-test"}' | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['decision'] == 'reject', 'feedback decision did not round-trip'
assert d['memory_record']['lane'] == 'location:demo:feedback'
print(f'  ok · fallback_only={d[\"memory_record\"][\"fallback_only\"]} · mubit_id={d[\"memory_record\"][\"mubit_id\"]}')
"

echo
echo "[smoke] GET /api/memories?session_id=ai_cafe_a"
curl -fsS "$BASE/api/memories?session_id=ai_cafe_a" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['source'] in ('jsonl', 'mubit', 'merged'), f'unexpected memories source: {d[\"source\"]}'
print(f'  ok · {len(d[\"records\"])} record(s) · source={d[\"source\"]}')
"

echo
echo "[smoke] all green."
