"""Align actuals and forecasts and compute MAE, RMSE, and bias."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from config import (
    ANALYSIS_END,
    ANALYSIS_START,
    ASSUMPTIONS,
    DECISION_CUTOFF_TIME,
    DECISION_TIMEZONE,
)


class AnalysisError(ValueError):
    """Raised for invalid analysis inputs or empty aligned results."""


def parse_analysis_dates(
    date_from: str | None, date_to: str | None
) -> tuple[date, date]:
    start = ANALYSIS_START if not date_from else _parse_iso_date(date_from, "from")
    end = ANALYSIS_END if not date_to else _parse_iso_date(date_to, "to")
    if start > end:
        raise AnalysisError("`from` must be on or before `to`.")
    if start < ANALYSIS_START or end > ANALYSIS_END:
        raise AnalysisError(
            f"Dates must fall within {ANALYSIS_START.isoformat()} and {ANALYSIS_END.isoformat()}."
        )
    return start, end


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AnalysisError(
            f"`{field}` must be an ISO date (YYYY-MM-DD)."
        ) from exc


def decision_cutoff_for_settlement_date(settlement: date) -> datetime:
    """09:00 Europe/London on the calendar day before settlement date D."""
    cutoff_day = settlement - timedelta(days=1)
    return datetime.combine(
        cutoff_day, DECISION_CUTOFF_TIME, tzinfo=DECISION_TIMEZONE
    )


def _to_utc(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, utc=True, errors="coerce")
    return parsed


def _settlement_date_from_start(start_times: pd.Series) -> pd.Series:
    london = start_times.dt.tz_convert(DECISION_TIMEZONE)
    return london.dt.date


def select_day_ahead_forecasts(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest eligible WINDFOR row for each startTime."""
    frame = forecasts.copy()
    frame["startTime"] = _to_utc(frame["startTime"])
    frame["publishTime"] = _to_utc(frame["publishTime"])
    frame = frame.dropna(subset=["startTime", "publishTime", "generation"])
    frame["generation"] = pd.to_numeric(frame["generation"], errors="coerce")
    frame = frame.dropna(subset=["generation"])
    frame["settlementDate"] = _settlement_date_from_start(frame["startTime"])
    frame["cutoff"] = frame["settlementDate"].map(decision_cutoff_for_settlement_date)
    # pandas map of datetimes can lose tz; normalise to aware UTC comparison.
    cutoffs = pd.to_datetime(frame["cutoff"], utc=True)
    eligible = frame[frame["publishTime"] <= cutoffs].copy()
    if eligible.empty:
        return eligible
    eligible = eligible.sort_values(["startTime", "publishTime"])
    selected = eligible.groupby("startTime", as_index=False).tail(1)
    return selected.rename(columns={"generation": "forecastMw"})


def prepare_actuals(actuals: pd.DataFrame) -> pd.DataFrame:
    frame = actuals.copy()
    frame["startTime"] = _to_utc(frame["startTime"])
    frame["generation"] = pd.to_numeric(frame["generation"], errors="coerce")
    frame = frame.dropna(subset=["startTime", "generation"])
    if "fuelType" in frame.columns:
        frame = frame[frame["fuelType"].astype(str).str.upper() == "WIND"]
    frame = frame.sort_values("startTime").drop_duplicates("startTime", keep="last")
    return frame.rename(
        columns={"generation": "actualMw", "publishTime": "actualPublishTime"}
    )


def align_and_score(
    actual_records: list[dict[str, Any]],
    forecast_records: list[dict[str, Any]],
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    if not actual_records:
        raise AnalysisError("No actual WIND generation rows were available.")
    if not forecast_records:
        raise AnalysisError("No WINDFOR forecast rows were available.")

    actuals = prepare_actuals(pd.DataFrame(actual_records))
    forecasts = select_day_ahead_forecasts(pd.DataFrame(forecast_records))
    if forecasts.empty:
        raise AnalysisError(
            "No WINDFOR rows were published at or before the day-ahead cutoff "
            "for the requested settlement dates."
        )

    merged = actuals.merge(
        forecasts[["startTime", "forecastMw", "publishTime"]],
        on="startTime",
        how="inner",
    )
    if "settlementDate" in actuals.columns:
        actuals = actuals.copy()
        actuals["settlementDate"] = pd.to_datetime(actuals["settlementDate"]).dt.date
    else:
        actuals = actuals.copy()
        actuals["settlementDate"] = _settlement_date_from_start(actuals["startTime"])
    merged = merged.drop(columns=["settlementDate"], errors="ignore").merge(
        actuals[["startTime", "settlementDate"]], on="startTime", how="left"
    )
    actuals = actuals[
        (actuals["settlementDate"] >= date_from) & (actuals["settlementDate"] <= date_to)
    ]
    merged = merged[
        (merged["settlementDate"] >= date_from)
        & (merged["settlementDate"] <= date_to)
    ]
    if merged.empty:
        raise AnalysisError(
            "Actual and forecast series could not be aligned on startTime "
            "for the requested dates after applying the decision cutoff."
        )

    merged = merged.sort_values("startTime")
    actual = merged["actualMw"].to_numpy(dtype=float)
    forecast = merged["forecastMw"].to_numpy(dtype=float)
    error = forecast - actual
    abs_error = np.abs(error)
    mae = float(np.mean(abs_error))
    rmse = float(np.sqrt(np.mean(np.square(error))))
    bias = float(np.mean(error))
    merged["errorMw"] = error
    merged["absErrorMw"] = abs_error

    daily = (
        merged.groupby("settlementDate", as_index=False)
        .agg(
            periods=("startTime", "size"),
            actualMeanMw=("actualMw", "mean"),
            forecastMeanMw=("forecastMw", "mean"),
            mae=("absErrorMw", "mean"),
            rmse=("errorMw", lambda s: float(np.sqrt(np.mean(np.square(s))))),
            bias=("errorMw", "mean"),
        )
        .sort_values("settlementDate")
    )

    series = [
        {
            "startTime": row.startTime.isoformat(),
            "settlementDate": row.settlementDate.isoformat(),
            "settlementPeriod": int(row.settlementPeriod)
            if "settlementPeriod" in merged.columns and pd.notna(row.settlementPeriod)
            else None,
            "actualMw": round(float(row.actualMw), 3),
            "forecastMw": round(float(row.forecastMw), 3),
            "errorMw": round(float(row.errorMw), 3),
            "forecastPublishTime": row.publishTime.isoformat(),
        }
        for row in merged.itertuples(index=False)
    ]

    table = [
        {
            "settlementDate": row.settlementDate.isoformat(),
            "periods": int(row.periods),
            "actualMeanMw": round(float(row.actualMeanMw), 3),
            "forecastMeanMw": round(float(row.forecastMeanMw), 3),
            "mae": round(float(row.mae), 3),
            "rmse": round(float(row.rmse), 3),
            "bias": round(float(row.bias), 3),
        }
        for row in daily.itertuples(index=False)
    ]

    expected_periods = int(actuals["startTime"].nunique())
    return {
        "kpis": {
            "maeMw": round(mae, 3),
            "rmseMw": round(rmse, 3),
            "biasMw": round(bias, 3),
            "pairedPeriods": int(len(merged)),
            "meanActualMw": round(float(np.mean(actual)), 3),
            "meanForecastMw": round(float(np.mean(forecast)), 3),
        },
        "coverage": {
            "alignedPeriods": int(len(merged)),
            "actualPeriodsInWindow": expected_periods,
        },
        "series": series,
        "dailyErrors": table,
        "assumptions": ASSUMPTIONS,
        "filters": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        },
    }
