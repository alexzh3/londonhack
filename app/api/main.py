"""FastAPI entrypoint for the CafeTwin Tier 1 backend."""

import logging
import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config as _config
from app.logfire_setup import configure_logfire, instrument_fastapi

logger = logging.getLogger(__name__)


# Allowed origins for browser CORS. The Vercel frontend rewrites /api/* to
# Render so production is technically same-origin (the browser sees the
# Vercel host on both ends), but we list it explicitly anyway. Local dev
# serves the JSX bundle on :5500/:5588 against a separate :8000 backend,
# which IS cross-origin and needs to be allowed.
_DEFAULT_CORS_ORIGINS = [
    "https://frontend-tier1.vercel.app",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5588",
    "http://127.0.0.1:5588",
]


def _allowed_origins() -> list[str]:
    """Configurable CORS origins. Override with comma-separated env var."""
    override = os.getenv("CAFETWIN_CORS_ORIGINS")
    if override:
        return [o.strip() for o in override.split(",") if o.strip()]
    return _DEFAULT_CORS_ORIGINS


# ── Per-IP rate limiter ──────────────────────────────────────────────────────
# Sponsor-funded LLM gateway is the cost-sensitive resource, so the
# LLM-spending routes get a hard per-IP cap. The cheap routes (state,
# memories, sessions, logfire_url, static mounts) are exempt — they don't
# burn credits and the public demo needs them on every page load.
#
# In-memory storage is per-process (fine for the single Render instance);
# bump to a Redis-backed solution if you ever scale horizontally. Toggle
# off in tests / local dev with CAFETWIN_DISABLE_RATE_LIMIT=1.

_LIMITED_PATHS = frozenset(
    {
        "/api/run",
        "/api/run/stream",
        "/api/sim/prompt",
    }
)
_DAILY_CAP = 100
_BURST_PER_MINUTE = 10
_DAY_SECONDS = 24 * 60 * 60
_MINUTE_SECONDS = 60


_DECISION_ALLOW = "allow"
_DECISION_DAILY_CAP = "daily_cap"
_DECISION_BURST_CAP = "burst_cap"


class _IpRateBucket:
    """Sliding-window timestamps per IP. Thread-safe; small memory footprint
    because old entries are pruned on every check."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check_and_record(self, ip: str, now: float) -> tuple[str, int]:
        """Returns (decision, retry_after_seconds).

        - ``allow``      → handler proceeds normally (LLM calls allowed).
        - ``daily_cap``  → handler proceeds, but agents fall back to cached
                            output (graceful degradation; the visitor still
                            gets a working response, no LLM cost is incurred).
        - ``burst_cap``  → middleware returns 429 immediately (the burst cap
                            protects against sudden script attacks where a
                            cached response wouldn't help anyway).

        We record the hit on ``allow`` and ``daily_cap`` so each cached-only
        response still counts toward the daily total — otherwise a single
        IP could keep hitting the demo forever once they cross the cap.
        """
        with self._lock:
            bucket = self._buckets[ip]
            day_cutoff = now - _DAY_SECONDS
            minute_cutoff = now - _MINUTE_SECONDS
            while bucket and bucket[0] < day_cutoff:
                bucket.popleft()

            recent_minute = sum(1 for ts in bucket if ts >= minute_cutoff)
            if recent_minute >= _BURST_PER_MINUTE:
                oldest_minute_ts = next((ts for ts in bucket if ts >= minute_cutoff), now)
                return _DECISION_BURST_CAP, max(
                    1, _MINUTE_SECONDS - int(now - oldest_minute_ts)
                )

            bucket.append(now)
            if len(bucket) > _DAILY_CAP:
                # The just-recorded hit is over the daily cap; degrade to
                # cached fallback rather than 429 so the visitor still sees
                # a working demo. retry_after is informational here — the
                # response is a normal 200, just with `used_fallback=true`.
                return _DECISION_DAILY_CAP, max(60, _DAY_SECONDS - int(now - bucket[0]))
            return _DECISION_ALLOW, 0


_rate_bucket = _IpRateBucket()


def _client_ip(request: Request) -> str:
    """Real client IP. Render sits behind a proxy, so request.client.host is
    the load balancer; X-Forwarded-For carries the original visitor IP
    (first hop is the real client, subsequent hops are intermediaries)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _rate_limit_middleware(request: Request, call_next):
    """Per-IP rate limit on LLM-spending endpoints.

    Burst (10/min) → hard 429 (script-attack deterrent).
    Daily (100/day) → graceful degradation: set the per-request fallback
    flag so the agent layer returns the cached recommendation, no LLM
    call is made, and the visitor sees a working response with
    ``used_fallback=true``.
    """
    if (
        request.url.path not in _LIMITED_PATHS
        or os.getenv("CAFETWIN_DISABLE_RATE_LIMIT") == "1"
    ):
        return await call_next(request)

    ip = _client_ip(request)
    decision, retry_after = _rate_bucket.check_and_record(ip, time.time())

    if decision == _DECISION_BURST_CAP:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={
                "detail": (
                    f"Burst rate limit exceeded for this IP "
                    f"({_BURST_PER_MINUTE}/minute). Try again in ~{retry_after}s."
                ),
                "limit": {"per_minute": _BURST_PER_MINUTE},
                "retry_after_seconds": retry_after,
            },
        )

    if decision == _DECISION_DAILY_CAP:
        # Mark this request's async context as fallback-only so the agents
        # serve cached output. Visitor still gets a 200 response.
        from app._runtime_overrides import force_fallback_for_current_request

        force_fallback_for_current_request()
        response = await call_next(request)
        # Surface what happened in headers so technical viewers / Logfire
        # operators can spot the daily-cap event without parsing the body.
        response.headers["X-CafeTwin-Rate-Limit"] = (
            f"daily-cap-reached; serving-cached; reset-in={retry_after}s"
        )
        return response

    return await call_next(request)


def create_app() -> FastAPI:
    configure_logfire()

    from app.api.routes import router

    app = FastAPI(title="CafeTwin Tier 1 API")
    app.middleware("http")(_rate_limit_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
        max_age=600,
    )
    app.include_router(router)
    # Static asset mounts so the frontend can load real CCTV video + frames
    # straight from the API server (no separate static origin needed). Tier
    # 1D — real video panel + future before/after image diffs. StaticFiles
    # supports HTTP Range requests so video scrubbing works in the browser.
    cafe_videos_dir = _config.ROOT_DIR / "cafe_videos"
    if cafe_videos_dir.is_dir():
        app.mount(
            "/cafe_videos",
            StaticFiles(directory=cafe_videos_dir),
            name="cafe_videos",
        )
    if _config.DEMO_DATA_DIR.is_dir():
        app.mount(
            "/demo_data",
            StaticFiles(directory=_config.DEMO_DATA_DIR),
            name="demo_data",
        )
    instrument_fastapi(app)

    # Tier 1E: register PatternAgent + OptimizationAgent in MuBit Managed
    # so the Console shows named agents with versioned system prompts.
    # Gated by `CAFETWIN_MUBIT_AGENTS=1`; falls back silently otherwise.
    @app.on_event("startup")
    async def _bootstrap_mubit_agents() -> None:
        from app.mubit_agents import bootstrap_mubit_agents, default_specs, is_enabled

        if not is_enabled():
            return
        try:
            await bootstrap_mubit_agents(default_specs())
        except Exception as exc:
            logger.warning("MuBit agent bootstrap raised: %s", exc)

    return app


app = create_app()
