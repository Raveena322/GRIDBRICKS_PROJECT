"""Client tests. Failures must surface; mock data is never returned as live results."""

from elexon_client import (
    ElexonError,
    _as_records,
    _get_json,
    _require_fields,
    fetch_fuelhh_wind,
)


def test_as_records_accepts_stream_list():
    rows = _as_records([{"startTime": "x"}])
    assert rows == [{"startTime": "x"}]


def test_as_records_accepts_wrapped_data():
    rows = _as_records({"data": [{"startTime": "x"}]})
    assert rows == [{"startTime": "x"}]


def test_as_records_rejects_unknown_shape():
    try:
        _as_records({"unexpected": True})
        assert False, "expected ElexonError"
    except ElexonError:
        pass


def test_require_fields_errors_when_schema_does_not_match():
    try:
        _require_fields(
            [{"foo": 1}],
            {"startTime", "publishTime", "generation"},
            "WINDFOR",
        )
        assert False, "expected ElexonError"
    except ElexonError as exc:
        assert "required schema" in str(exc)


def test_fetch_fuelhh_does_not_invent_rows_on_http_error(monkeypatch):
    class FakeResponse:
        status_code = 500
        text = "upstream down"

        def json(self):
            return []

    calls = 0

    def fake_get(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse()

    monkeypatch.setattr("elexon_client.requests.get", fake_get)
    monkeypatch.setattr("elexon_client._sleep_backoff", lambda _attempt: None)
    try:
        fetch_fuelhh_wind(__import__("datetime").date(2026, 1, 1), __import__("datetime").date(2026, 1, 1))
        assert False, "expected ElexonError"
    except ElexonError as exc:
        assert "HTTP 500" in str(exc)
    assert calls == 4


def test_get_json_retries_transient_server_error(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.text = "temporary upstream failure"
            self.payload = payload

        def json(self):
            return self.payload

    responses = iter(
        [FakeResponse(503, None), FakeResponse(200, {"data": [1]})]
    )
    calls = 0

    def fake_get(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return next(responses)

    monkeypatch.setattr("elexon_client.requests.get", fake_get)
    monkeypatch.setattr("elexon_client._sleep_backoff", lambda _attempt: None)

    assert _get_json("/datasets/test/stream", {}) == {"data": [1]}
    assert calls == 2
