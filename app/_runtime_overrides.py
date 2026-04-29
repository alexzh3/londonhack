"""Per-request runtime overrides that complement the static env-var config.

The static `CAFETWIN_FORCE_FALLBACK=1` env var disables every live agent
call for the entire process. We also want a *per-request* fallback path:
when an IP hits the daily rate-limit cap on `/api/run`, we want THAT
request (and any nested agent calls within its handler) to silently use
the cached fallback path instead of returning a 429 error.

Implementation: a `contextvars.ContextVar` that the rate-limit middleware
sets to `True` when the daily cap is reached. The agent gating helpers
(`_live_agent_enabled` in each agent module) read both the env var and
this contextvar. Because contextvars propagate through `await`/asyncio
tasks within the same request, the middleware can set it in
`_rate_limit_middleware` and every downstream agent call will see it
without explicit threading.
"""

from __future__ import annotations

import os
from contextvars import ContextVar

_force_fallback: ContextVar[bool] = ContextVar(
    "cafetwin_force_fallback_request", default=False
)


def force_fallback_active() -> bool:
    """True if either the static env-var or the per-request flag is set.

    Agents call this from `_live_agent_enabled()` in place of a bare
    `os.getenv("CAFETWIN_FORCE_FALLBACK") == "1"` check.
    """
    if os.getenv("CAFETWIN_FORCE_FALLBACK") == "1":
        return True
    return _force_fallback.get()


def force_fallback_for_current_request() -> None:
    """Mark the current async context as fallback-only.

    Called by the rate-limit middleware when an IP hits the daily cap.
    The flag lives only within the current request's contextvars copy and
    does not leak into other concurrently-handled requests.
    """
    _force_fallback.set(True)
