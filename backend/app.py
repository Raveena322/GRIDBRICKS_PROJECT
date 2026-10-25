"""Flask API for the UK Wind Power Forecast Dashboard."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from analysis import AnalysisError, align_and_score, parse_analysis_dates
from config import (
    ANALYSIS_END,
    ANALYSIS_START,
    ASSUMPTIONS,
    CACHE_DIR,
    CACHE_PATH,
    CACHE_TTL_SECONDS,
)
from elexon_client import ElexonError, fetch_fuelhh_wind, fetch_windfor_for_analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

_cache_lock = threading.Lock()
_memory_cache: dict | None = None


def _load_disk_cache() -> dict | None:
    path = Path(CACHE_PATH)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    fetched_at = payload.get("fetchedAt")
    if not fetched_at:
        return None
    fetched = datetime.fromisoformat(fetched_at)
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    if age > CACHE_TTL_SECONDS:
        return None
    return payload


def _save_disk_cache(payload: dict) -> None:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    Path(CACHE_PATH).write_text(json.dumps(payload), encoding="utf-8")


def _fetch_live_window() -> dict:
    logger.info("Fetching live Elexon FUELHH and WINDFOR for January 2026")
    actuals = fetch_fuelhh_wind(ANALYSIS_START, ANALYSIS_END)
    forecasts = fetch_windfor_for_analysis(ANALYSIS_START, ANALYSIS_END)
    payload = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "actuals": actuals,
        "forecasts": forecasts,
    }
    _save_disk_cache(payload)
    return payload


def get_source_data(*, refresh: bool = False) -> dict:
    global _memory_cache
    with _cache_lock:
        if not refresh and _memory_cache is not None:
            return _memory_cache
        if not refresh:
            disk = _load_disk_cache()
            if disk is not None:
                _memory_cache = disk
                return disk
        payload = _fetch_live_window()
        _memory_cache = payload
        return payload


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "uk-wind-forecast-api"})


@app.get("/api/meta")
def meta():
    return jsonify(
        {
            "assumptions": ASSUMPTIONS,
            "supportedRange": {
                "from": ANALYSIS_START.isoformat(),
                "to": ANALYSIS_END.isoformat(),
            },
        }
    )


@app.get("/api/analysis")
def analysis_endpoint():
    try:
        date_from, date_to = parse_analysis_dates(
            request.args.get("from"), request.args.get("to")
        )
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400

    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    started = time.monotonic()
    try:
        source = get_source_data(refresh=refresh)
        result = align_and_score(
            source["actuals"], source["forecasts"], date_from, date_to
        )
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 422
    except ElexonError as exc:
        logger.exception("Elexon fetch failed")
        return jsonify(
            {
                "error": "Live Elexon data could not be retrieved. No substitute data was used.",
                "details": str(exc),
            }
        ), 502
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures cleanly
        logger.exception("Unexpected analysis failure")
        return jsonify(
            {
                "error": "The analysis pipeline failed before results could be produced.",
                "details": str(exc),
            }
        ), 500

    result["source"] = {
        "fetchedAt": source["fetchedAt"],
        "actualRows": len(source["actuals"]),
        "forecastRows": len(source["forecasts"]),
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "liveElexon": True,
        "mocked": False,
    }
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
