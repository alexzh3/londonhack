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
