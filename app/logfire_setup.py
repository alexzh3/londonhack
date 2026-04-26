"""Logfire configuration and span helpers for the MVP backend."""

from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any
from urllib.parse import quote


_last_trace_url: str | None = None
_configured = False


def span(name: str, **attributes: Any):
    if not os.getenv("LOGFIRE_TOKEN"):
        return nullcontext()

    configure_logfire()
    try:
        import logfire

        return logfire.span(name, **attributes)
    except Exception:
        return nullcontext()


def configure_logfire() -> None:
    """Configure Logfire once when a write token is available."""
    global _configured
    if _configured or not os.getenv("LOGFIRE_TOKEN"):
        return

    try:
        import logfire

        logfire.configure(
            service_name=os.getenv("LOGFIRE_SERVICE_NAME", "cafetwin-mvp"),
            environment=os.getenv("LOGFIRE_ENVIRONMENT", "demo"),
            send_to_logfire="if-token-present",
            console=False,
            inspect_arguments=False,
        )
        _configured = True
        try:
            logfire.instrument_pydantic_ai()
        except Exception:
            pass
    except Exception:
        _configured = False


def instrument_fastapi(app: Any) -> None:
    """Instrument FastAPI after configure_logfire() and after app creation."""
    if not _configured:
        return

    try:
        import logfire

        logfire.instrument_fastapi(app)
    except Exception:
        pass


def trace_url_from_span(active_span: Any) -> str | None:
    """Return a Logfire live-view URL filtered to the span trace when possible."""
    if active_span is None:
        return None

    project_url = _project_url()
    if not project_url:
        return None

    try:
        context = active_span.get_span_context()
        trace_id = f"{context.trace_id:032x}"
    except Exception:
        return None

    query = quote(f"trace_id = '{trace_id}'")
    return f"{project_url.rstrip('/')}/live?query={query}"


def set_last_trace_url(url: str | None) -> None:
    global _last_trace_url
    _last_trace_url = url


def get_last_trace_url() -> str | None:
    return _last_trace_url


def _project_url() -> str | None:
    configured_url = os.getenv("LOGFIRE_PROJECT_URL")
    if configured_url:
        return configured_url

    try:
        import logfire

        return logfire.DEFAULT_LOGFIRE_INSTANCE._config._project_url  # noqa: SLF001
    except Exception:
        return None
