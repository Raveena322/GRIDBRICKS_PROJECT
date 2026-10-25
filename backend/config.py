"""Application configuration and documented analysis assumptions."""

from __future__ import annotations

import os
from datetime import date, time
from zoneinfo import ZoneInfo

ELEXON_BASE_URL = os.environ.get(
    "ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1"
).rstrip("/")

# Analysis window for the assignment.
ANALYSIS_START = date(2026, 1, 1)
ANALYSIS_END = date(2026, 1, 31)

# Day-ahead decision cutoff (see README and API `assumptions`).
# GB day-ahead auction gate closure is typically around 09:20 Europe/London.
# 09:00 is used as a conservative cutoff so only forecasts published strictly
# in time for a day-ahead purchase decision are eligible.
DECISION_TIMEZONE = ZoneInfo("Europe/London")
DECISION_CUTOFF_TIME = time(9, 0)

HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "90"))
HTTP_MAX_RETRIES = int(os.environ.get("HTTP_MAX_RETRIES", "4"))

CACHE_DIR = os.environ.get(
    "CACHE_DIR", os.path.join(os.path.dirname(__file__), "data")
)
CACHE_PATH = os.path.join(CACHE_DIR, "january_2026_cache.json")
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", str(6 * 60 * 60)))

ASSUMPTIONS = {
    "analysisWindow": {
        "start": ANALYSIS_START.isoformat(),
        "end": ANALYSIS_END.isoformat(),
        "timezone": "Europe/London",
    },
    "decisionCutoff": {
        "rule": (
            "For each GB settlement date D, the day-ahead decision cutoff is "
            "09:00 Europe/London on calendar date D-1."
        ),
        "localTime": "09:00",
        "timezone": "Europe/London",
        "rationale": (
            "EPEX SPOT GB day-ahead auction gate closure is typically near "
            "09:20 UK time. A 09:00 cutoff keeps only WINDFOR publications "
            "that would have been available before that auction, with a "
            "small operational buffer. In January 2026 (GMT) this is 09:00 UTC. "
            "Observed WINDFOR publishTimes on 2025-12-31 were 02:30, 04:30, "
            "07:30, 09:30, 11:30, 15:30, 18:30 and 22:30 UTC; only the first "
            "three are eligible under this cutoff."
        ),
    },
    "alignment": {
        "key": "startTime",
        "forecastSelection": (
            "Among WINDFOR rows sharing an actual startTime, keep the row "
            "with the latest publishTime that is still <= the D-1 09:00 "
            "Europe/London cutoff."
        ),
        "units": "MW (half-hourly average generation)",
    },
    "metrics": {
        "error": "forecast - actual",
        "mae": "mean(|error|)",
        "rmse": "sqrt(mean(error^2))",
        "bias": "mean(error); positive means the forecast overstated generation",
    },
    "dataSources": {
        "actuals": "GET /datasets/FUELHH/stream with fuelType=WIND",
        "forecasts": "GET /datasets/WINDFOR/stream filtered by publishDateTime",
        "baseUrl": ELEXON_BASE_URL,
        "pagination": (
            "These dataset/stream endpoints do not paginate. FUELHH for "
            "January 2026 returned 1488 rows (31 * 48) in a single request. "
            "WINDFOR is fetched in multi-day publish-time windows because "
            "the API is latency-heavy (~20s per request) but does not page."
        ),
    },
}
