from app.logfire_setup import trace_url_from_span


TRACE_ID = "1" * 32


class FakeSpan:
    def get_span_context(self):
        return type("Context", (), {"trace_id": int(TRACE_ID, 16)})()


def test_trace_url_from_span_uses_project_url(monkeypatch):
    monkeypatch.setenv("LOGFIRE_PROJECT_URL", "https://logfire.example/org/project")

    url = trace_url_from_span(FakeSpan())

    assert url == f"https://logfire.example/org/project/live?query=trace_id%20%3D%20%27{TRACE_ID}%27"


def test_trace_url_from_span_returns_none_without_project_url(monkeypatch):
    monkeypatch.delenv("LOGFIRE_PROJECT_URL", raising=False)

    assert trace_url_from_span(FakeSpan()) is None
