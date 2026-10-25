"""Flask API tests for validation and error handling."""

from datetime import datetime, timezone

import pytest

import app as app_module
from elexon_client import ElexonError


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_analysis_rejects_invalid_date(client):
    response = client.get("/api/analysis?from=01-01-2026&to=2026-01-02")
    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


def test_analysis_returns_502_when_elexon_fails(client, monkeypatch):
    def fail_source(**_kwargs):
        raise ElexonError("timed out talking to Elexon")

    monkeypatch.setattr(app_module, "get_source_data", fail_source)
    response = client.get("/api/analysis?from=2026-01-01&to=2026-01-02")
    assert response.status_code == 502
    body = response.get_json()
    assert "No substitute data was used" in body["error"]
    assert "series" not in body


def test_analysis_scores_cached_live_shaped_rows(client, monkeypatch):
    source = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "actuals": [
            {
                "dataset": "FUELHH",
                "startTime": "2026-01-05T00:00:00Z",
                "publishTime": "2026-01-05T00:30:00Z",
                "fuelType": "WIND",
                "generation": 1000,
                "settlementDate": "2026-01-05",
                "settlementPeriod": 1,
            }
        ],
        "forecasts": [
            {
                "dataset": "WINDFOR",
                "startTime": "2026-01-05T00:00:00Z",
                "publishTime": "2026-01-04T07:30:00Z",
                "generation": 1080,
            }
        ],
    }
    monkeypatch.setattr(app_module, "get_source_data", lambda **_k: source)
    response = client.get("/api/analysis?from=2026-01-05&to=2026-01-05")
    assert response.status_code == 200
    body = response.get_json()
    assert body["source"]["mocked"] is False
    assert body["kpis"]["pairedPeriods"] == 1
    assert body["kpis"]["biasMw"] == 80.0
    assert body["series"][0]["actualMw"] == 1000
