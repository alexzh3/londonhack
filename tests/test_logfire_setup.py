import sys
from types import SimpleNamespace

import app.logfire_setup as logfire_setup
from app.logfire_setup import _scrub_callback, trace_url_from_span


TRACE_ID = "1" * 32


class FakeSpan:
    def get_span_context(self):
        return type("Context", (), {"trace_id": int(TRACE_ID, 16)})()


class FakeScrubMatch:
    def __init__(self, path, value):
        self.path = path
        self.value = value


def test_trace_url_from_span_uses_project_url(monkeypatch):
    monkeypatch.setenv("LOGFIRE_PROJECT_URL", "https://logfire.example/org/project")

    url = trace_url_from_span(FakeSpan())

    assert url == f"https://logfire.example/org/project/live?query=trace_id%20%3D%20%27{TRACE_ID}%27"


def test_trace_url_from_span_returns_none_without_project_url(monkeypatch):
    monkeypatch.delenv("LOGFIRE_PROJECT_URL", raising=False)

    assert trace_url_from_span(FakeSpan()) is None


def test_scrub_callback_allows_public_fixture_session_id():
    match = FakeScrubMatch(
        ("attributes", "fastapi.arguments.values", "session_id"),
        "ai_cafe_a",
    )

    assert _scrub_callback(match) == "ai_cafe_a"


def test_scrub_callback_allows_empty_optional_session_id():
    match = FakeScrubMatch(
        ("attributes", "fastapi.arguments.values", "session_id"),
        None,
    )

    assert _scrub_callback(match) == "unset"


def test_scrub_callback_keeps_other_session_values_redacted():
    match = FakeScrubMatch(
        ("attributes", "headers", "session"),
        "actual-cookie-token",
    )

    assert _scrub_callback(match) is None


def test_configure_logfire_instruments_libraries_after_configure(monkeypatch):
    calls = []
    fake_logfire = SimpleNamespace(
        ScrubbingOptions=lambda callback: ("scrubbing", callback),
        configure=lambda **kwargs: calls.append(("configure", kwargs)),
        instrument_pydantic_ai=lambda: calls.append(("instrument_pydantic_ai", None)),
        instrument_httpx=lambda: calls.append(("instrument_httpx", None)),
        instrument_fastapi=lambda app: calls.append(("instrument_fastapi", app)),
    )
    monkeypatch.setitem(sys.modules, "logfire", fake_logfire)
    monkeypatch.setenv("LOGFIRE_TOKEN", "token")
    monkeypatch.setattr(logfire_setup, "_configured", False)

    logfire_setup.configure_logfire()
    logfire_setup.instrument_fastapi("app")

    assert [call[0] for call in calls] == [
        "configure",
        "instrument_pydantic_ai",
        "instrument_httpx",
        "instrument_fastapi",
    ]
