"""Per-IP rate limit middleware on the LLM-spending routes.

The middleware itself is `_rate_limit_middleware` in `app.api.main`. These
tests exercise the underlying `_IpRateBucket` (pure logic, no FastAPI
plumbing) so the rate-limit semantics are pinned without spinning up the
whole TestClient stack. The TestClient suite (`test_api.py`) keeps the
limiter disabled via `CAFETWIN_DISABLE_RATE_LIMIT=1` in `conftest.py`.

Three-state contract under test:
- `allow`     — under both caps; live agents proceed.
- `daily_cap` — daily cap exceeded; handler still runs but agents fall
                back to cached output (graceful degradation).
- `burst_cap` — burst cap exceeded; middleware returns 429 immediately.
"""

from app.api.main import (
    _BURST_PER_MINUTE,
    _DAILY_CAP,
    _DECISION_ALLOW,
    _DECISION_BURST_CAP,
    _DECISION_DAILY_CAP,
    _IpRateBucket,
)


def test_first_request_is_allowed():
    bucket = _IpRateBucket()

    decision, retry_after = bucket.check_and_record("1.1.1.1", now=1000.0)

    assert decision == _DECISION_ALLOW
    assert retry_after == 0


def test_burst_cap_returns_burst_decision():
    bucket = _IpRateBucket()
    ip = "1.1.1.1"

    for i in range(_BURST_PER_MINUTE):
        decision, _ = bucket.check_and_record(ip, now=1000.0 + i)
        assert decision == _DECISION_ALLOW, f"request {i + 1} should still fit"

    decision, retry_after = bucket.check_and_record(ip, now=1000.0 + _BURST_PER_MINUTE)
    assert decision == _DECISION_BURST_CAP
    assert 1 <= retry_after <= 60


def test_burst_window_slides_after_a_minute():
    bucket = _IpRateBucket()
    ip = "2.2.2.2"

    for i in range(_BURST_PER_MINUTE):
        bucket.check_and_record(ip, now=1000.0 + i)

    # 65s later: burst window has slid; should be allowed again (we're
    # still well under the daily cap).
    decision, _ = bucket.check_and_record(ip, now=1000.0 + 65)
    assert decision == _DECISION_ALLOW


def test_daily_cap_degrades_gracefully_to_fallback():
    """Once the daily cap is reached, additional requests return the
    `daily_cap` decision instead of being blocked. The middleware reads
    this and forces the agents to serve cached output for those
    requests, so the visitor still gets a working 200 response."""
    bucket = _IpRateBucket()
    ip = "3.3.3.3"

    # Spread requests two seconds apart so we never trip the burst limit
    # before reaching the daily cap.
    base = 1_000_000.0
    spacing = 60.0 / (_BURST_PER_MINUTE - 1)
    for i in range(_DAILY_CAP):
        decision, _ = bucket.check_and_record(ip, now=base + i * spacing)
        assert decision == _DECISION_ALLOW, f"request {i + 1} should fit under the daily cap"

    decision, retry_after = bucket.check_and_record(ip, now=base + _DAILY_CAP * spacing)
    assert decision == _DECISION_DAILY_CAP
    assert retry_after >= 60


def test_daily_cap_keeps_recording_after_first_overflow():
    """Each over-cap hit still consumes a slot, otherwise an attacker
    could loop forever once they crossed the cap. Daily decisions
    should keep coming back as daily_cap until the window slides."""
    bucket = _IpRateBucket()
    ip = "3a.3a.3a.3a"

    base = 1_000_000.0
    spacing = 60.0 / (_BURST_PER_MINUTE - 1)
    for i in range(_DAILY_CAP):
        bucket.check_and_record(ip, now=base + i * spacing)

    # Several follow-up requests should all be daily_cap, not flip back
    # to allow.
    for j in range(3):
        decision, _ = bucket.check_and_record(
            ip, now=base + (_DAILY_CAP + j) * spacing
        )
        assert decision == _DECISION_DAILY_CAP


def test_separate_ips_have_independent_buckets():
    bucket = _IpRateBucket()

    for i in range(_BURST_PER_MINUTE):
        bucket.check_and_record("4.4.4.4", now=1000.0 + i)

    # Fresh IP should not be affected by 4.4.4.4's burst.
    decision, _ = bucket.check_and_record("5.5.5.5", now=1000.0 + _BURST_PER_MINUTE)
    assert decision == _DECISION_ALLOW


def test_daily_window_slides_after_24h():
    bucket = _IpRateBucket()
    ip = "6.6.6.6"

    base = 1_000_000.0
    spacing = 60.0 / (_BURST_PER_MINUTE - 1)
    for i in range(_DAILY_CAP):
        bucket.check_and_record(ip, now=base + i * spacing)

    # 25h later the entire bucket has expired and we should be allowed again.
    decision, _ = bucket.check_and_record(ip, now=base + 25 * 60 * 60)
    assert decision == _DECISION_ALLOW


# ── Per-request fallback contextvar ──────────────────────────────────────────
# The rate-limit middleware sets `_force_fallback` for the current request's
# async context when the daily cap is reached. The agent gating helpers
# (`_live_agent_enabled` in each agent module) check `force_fallback_active()`,
# which reads both that contextvar and the static env var.

def test_force_fallback_active_reads_env_var(monkeypatch):
    from app._runtime_overrides import force_fallback_active

    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "1")

    assert force_fallback_active() is True


def test_force_fallback_active_reads_contextvar_when_env_unset(monkeypatch):
    """The contextvar overrides only the current async context. The default
    is False so unrelated tests don't see a stuck flag."""
    import asyncio

    from app._runtime_overrides import (
        force_fallback_active,
        force_fallback_for_current_request,
    )

    monkeypatch.setenv("CAFETWIN_FORCE_FALLBACK", "")

    async def run_request_with_flag():
        force_fallback_for_current_request()
        return force_fallback_active()

    async def run_request_without_flag():
        return force_fallback_active()

    # The flagged request sees True; the parallel unflagged request still
    # sees False (contextvars do not leak across asyncio tasks unless
    # explicitly copied, which is exactly the isolation we want).
    flagged, unflagged = asyncio.run(_pair(run_request_with_flag, run_request_without_flag))

    assert flagged is True
    assert unflagged is False


async def _pair(coro_a, coro_b):
    import asyncio

    return await asyncio.gather(asyncio.create_task(coro_a()), asyncio.create_task(coro_b()))


# ── End-to-end middleware integration ───────────────────────────────────────
# Exercises the full FastAPI middleware → handler flow with a tiny daily
# cap so we can prove (a) over-cap requests are NOT 429'd, (b) they still
# return 200 with the standard RunResponse shape, and (c) the response
# carries the X-CafeTwin-Rate-Limit header so operators can spot it.

def test_middleware_serves_cached_after_daily_cap(monkeypatch):
    """Daily cap → graceful fallback, not 429."""
    from fastapi.testclient import TestClient

    # Force the limiter on (conftest sets it off), and shrink the daily
    # cap so we don't need 100 calls to test the contract.
    monkeypatch.setenv("CAFETWIN_DISABLE_RATE_LIMIT", "0")
    monkeypatch.setattr("app.api.main._DAILY_CAP", 3)
    monkeypatch.setattr("app.api.main._BURST_PER_MINUTE", 100)

    # Fresh bucket so we don't inherit state from any previous test.
    monkeypatch.setattr("app.api.main._rate_bucket", _IpRateBucket())

    from app.api.main import app

    client = TestClient(app)
    body = {"session_id": "ai_cafe_a"}

    # Three hits land under the cap.
    for i in range(3):
        resp = client.post("/api/run", json=body)
        assert resp.status_code == 200, f"hit {i + 1} should succeed"
        assert "X-CafeTwin-Rate-Limit" not in resp.headers

    # Fourth hit is over cap → still 200 (graceful) + cached fallback +
    # explicit response header so operators can spot the daily-cap event.
    resp = client.post("/api/run", json=body)
    assert resp.status_code == 200
    assert resp.headers["X-CafeTwin-Rate-Limit"].startswith("daily-cap-reached")
    payload = resp.json()
    assert payload["used_fallback"] is True
    assert payload["layout_change"]["title"]  # cached recommendation present


def test_middleware_429s_on_burst_cap(monkeypatch):
    """Burst cap → hard 429, not graceful fallback."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("CAFETWIN_DISABLE_RATE_LIMIT", "0")
    monkeypatch.setattr("app.api.main._BURST_PER_MINUTE", 2)
    monkeypatch.setattr("app.api.main._DAILY_CAP", 100)
    monkeypatch.setattr("app.api.main._rate_bucket", _IpRateBucket())

    from app.api.main import app

    client = TestClient(app)
    body = {"session_id": "ai_cafe_a"}

    assert client.post("/api/run", json=body).status_code == 200
    assert client.post("/api/run", json=body).status_code == 200

    resp = client.post("/api/run", json=body)
    assert resp.status_code == 429
    payload = resp.json()
    assert "detail" in payload
    assert payload["limit"]["per_minute"] == 2
    assert resp.headers["Retry-After"] is not None
