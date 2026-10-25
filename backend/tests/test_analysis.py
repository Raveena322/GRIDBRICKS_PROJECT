"""Unit tests for alignment, cutoff selection, and error metrics.

Fixtures below are synthetic and are never presented as Elexon observations.
"""

from datetime import date, datetime

import numpy as np
import pandas as pd

from analysis import (
    AnalysisError,
    align_and_score,
    decision_cutoff_for_settlement_date,
    parse_analysis_dates,
    select_day_ahead_forecasts,
)


def test_parse_analysis_dates_defaults_to_january_2026():
    start, end = parse_analysis_dates(None, None)
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 31)


def test_parse_analysis_dates_rejects_inverted_range():
    try:
        parse_analysis_dates("2026-01-10", "2026-01-02")
        assert False, "expected AnalysisError"
    except AnalysisError as exc:
        assert "on or before" in str(exc)


def test_parse_analysis_dates_rejects_outside_window():
    try:
        parse_analysis_dates("2025-12-31", "2026-01-02")
        assert False, "expected AnalysisError"
    except AnalysisError:
        pass


def test_decision_cutoff_is_0900_london_on_d_minus_1():
    cutoff = decision_cutoff_for_settlement_date(date(2026, 1, 15))
    assert cutoff.tzinfo is not None
    assert cutoff.hour == 9
    assert cutoff.minute == 0
    assert str(cutoff.date()) == "2026-01-14"


def test_select_day_ahead_forecasts_keeps_latest_eligible_publish():
    # Settlement period starting 2026-01-15 12:00 UTC = 12:00 London in January.
    start = "2026-01-15T12:00:00Z"
    rows = pd.DataFrame(
        [
            {"startTime": start, "publishTime": "2026-01-14T04:30:00Z", "generation": 1000},
            {"startTime": start, "publishTime": "2026-01-14T07:30:00Z", "generation": 1100},
            {"startTime": start, "publishTime": "2026-01-14T09:30:00Z", "generation": 9999},
            {"startTime": start, "publishTime": "2026-01-15T02:30:00Z", "generation": 50},
        ]
    )
    selected = select_day_ahead_forecasts(rows)
    assert len(selected) == 1
    assert float(selected.iloc[0]["forecastMw"]) == 1100
    assert selected.iloc[0]["publishTime"] == datetime.fromisoformat(
        "2026-01-14T07:30:00+00:00"
    )


def test_metrics_match_known_vectors():
    actuals = [
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-02T00:30:00Z",
            "fuelType": "WIND",
            "generation": 10,
            "settlementDate": "2026-01-02",
            "settlementPeriod": 1,
        },
        {
            "startTime": "2026-01-02T00:30:00Z",
            "publishTime": "2026-01-02T01:00:00Z",
            "fuelType": "WIND",
            "generation": 20,
            "settlementDate": "2026-01-02",
            "settlementPeriod": 2,
        },
    ]
    forecasts = [
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-01T07:30:00Z",
            "generation": 12,
        },
        {
            "startTime": "2026-01-02T00:30:00Z",
            "publishTime": "2026-01-01T07:30:00Z",
            "generation": 17,
        },
    ]
    result = align_and_score(actuals, forecasts, date(2026, 1, 2), date(2026, 1, 2))
    errors = np.array([2.0, -3.0])
    assert result["kpis"]["pairedPeriods"] == 2
    assert result["kpis"]["maeMw"] == round(float(np.mean(np.abs(errors))), 3)
    assert result["kpis"]["rmseMw"] == round(float(np.sqrt(np.mean(errors**2))), 3)
    assert result["kpis"]["biasMw"] == round(float(np.mean(errors)), 3)


def test_filter_uses_actual_settlement_date_for_joined_periods():
    # UTC startTime is still on Jan 1, but this FUELHH row is assigned to Jan 2.
    actuals = [
        {
            "startTime": "2026-01-01T23:00:00Z",
            "publishTime": "2026-01-01T23:30:00Z",
            "fuelType": "WIND",
            "generation": 10,
            "settlementDate": "2026-01-02",
            "settlementPeriod": 47,
        }
    ]
    forecasts = [
        {
            "startTime": "2026-01-01T23:00:00Z",
            "publishTime": "2025-12-31T07:30:00Z",
            "generation": 12,
        }
    ]

    result = align_and_score(actuals, forecasts, date(2026, 1, 2), date(2026, 1, 2))

    assert result["series"][0]["settlementDate"] == "2026-01-02"
    assert result["kpis"]["pairedPeriods"] == 1


def test_align_and_score_fails_closed_when_no_overlap():
    actuals = [
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-02T00:30:00Z",
            "fuelType": "WIND",
            "generation": 10,
            "settlementDate": "2026-01-02",
            "settlementPeriod": 1,
        }
    ]
    forecasts = [
        {
            "startTime": "2026-01-03T00:00:00Z",
            "publishTime": "2026-01-02T07:30:00Z",
            "generation": 12,
        }
    ]
    try:
        align_and_score(actuals, forecasts, date(2026, 1, 2), date(2026, 1, 2))
        assert False, "expected AnalysisError"
    except AnalysisError as exc:
        assert "aligned" in str(exc)
