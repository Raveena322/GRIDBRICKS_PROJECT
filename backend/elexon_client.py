"""Live Elexon Insights client. Never substitutes mock data on failure."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from config import (
    ELEXON_BASE_URL,
    HTTP_MAX_RETRIES,
    HTTP_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

FUELHH_REQUIRED = {
    "startTime",
    "publishTime",
    "fuelType",
    "generation",
    "settlementDate",
    "settlementPeriod",
}
WINDFOR_REQUIRED = {"startTime", "publishTime", "generation"}


class ElexonError(RuntimeError):
    """Raised when the live Elexon API cannot be used."""


def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(2**attempt, 8))


def _get_json(path: str, params: dict[str, Any]) -> Any:
    url = f"{ELEXON_BASE_URL}{path}"
    last_error: Exception | None = None
    for attempt in range(HTTP_MAX_RETRIES):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=HTTP_TIMEOUT_SECONDS,
                headers={"Accept": "application/json", "User-Agent": "uk-wind-forecast-dashboard"},
            )
            if response.status_code in {408, 429, 500, 502, 503, 504}:
                last_error = ElexonError(
                    f"Elexon temporarily failed for {path} "
                    f"(HTTP {response.status_code}): {response.text[:400]}"
                )
                logger.warning("%s (attempt %s)", last_error, attempt + 1)
                if attempt + 1 < HTTP_MAX_RETRIES:
                    _sleep_backoff(attempt)
                continue
            if response.status_code >= 400:
                raise ElexonError(
                    f"Elexon request failed for {path} "
                    f"(HTTP {response.status_code}): {response.text[:400]}"
                )
            try:
                return response.json()
            except ValueError as exc:
                raise ElexonError(
                    f"Elexon returned non-JSON for {path}."
                ) from exc
        except ElexonError:
            raise
        except requests.RequestException as exc:
            last_error = ElexonError(
                f"Network error calling Elexon {path}: {exc}"
            )
            logger.warning("%s (attempt %s)", last_error, attempt + 1)
            if attempt + 1 < HTTP_MAX_RETRIES:
                _sleep_backoff(attempt)
    raise last_error or ElexonError(f"Elexon request failed for {path}.")


def _as_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise ElexonError(
        "Unexpected Elexon payload: expected a JSON list or an object with a data array."
    )


def _require_fields(records: list[dict[str, Any]], required: set[str], dataset: str) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        if required.issubset(row.keys()) and row.get("generation") is not None:
            valid.append(row)
    if records and not valid:
        raise ElexonError(
            f"Elexon {dataset} response had {len(records)} rows but none matched the required schema {sorted(required)}."
        )
    return valid


def fetch_fuelhh_wind(start: date, end: date) -> list[dict[str, Any]]:
    """Half-hourly national wind outturn. Stream endpoint; no pagination."""
    payload = _get_json(
        "/datasets/FUELHH/stream",
        {
            "settlementDateFrom": start.isoformat(),
            "settlementDateTo": end.isoformat(),
            "fuelType": "WIND",
        },
    )
    records = _as_records(payload)
    records = [
        row
        for row in _require_fields(records, FUELHH_REQUIRED, "FUELHH")
        if str(row.get("fuelType", "")).upper() == "WIND"
    ]
    if not records:
        raise ElexonError(
            f"Elexon FUELHH returned no WIND rows for {start.isoformat()} to {end.isoformat()}."
        )
    return records


def fetch_windfor(publish_from: datetime, publish_to: datetime) -> list[dict[str, Any]]:
    """Wind generation forecasts published in the given UTC window. No pagination."""
    if publish_from.tzinfo is None or publish_to.tzinfo is None:
        raise ValueError("WINDFOR publish window must be timezone-aware.")
    payload = _get_json(
        "/datasets/WINDFOR/stream",
        {
            "publishDateTimeFrom": publish_from.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "publishDateTimeTo": publish_to.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        },
    )
    records = _as_records(payload)
    return _require_fields(records, WINDFOR_REQUIRED, "WINDFOR")


def fetch_windfor_for_analysis(start: date, end: date) -> list[dict[str, Any]]:
    """Fetch WINDFOR publications covering D-1 of the analysis window.

    Chunked by publish-time because a single multi-week call is slow and the
    stream endpoint does not paginate.
    """
    publish_start = datetime.combine(
        start - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )
    publish_end = datetime.combine(
        end, datetime.min.time(), tzinfo=timezone.utc
    )
    records: list[dict[str, Any]] = []
    cursor = publish_start
    while cursor < publish_end:
        chunk_end = min(cursor + timedelta(days=7), publish_end)
        chunk = fetch_windfor(cursor, chunk_end)
        if not chunk:
            logger.warning(
                "WINDFOR chunk %s to %s returned no rows", cursor, chunk_end
            )
        records.extend(chunk)
        cursor = chunk_end
    if not records:
        raise ElexonError(
            f"Elexon WINDFOR returned no rows for publish window "
            f"{publish_start.isoformat()} to {publish_end.isoformat()}."
        )
    return records
