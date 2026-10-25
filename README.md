# UK Wind Power Forecast Dashboard

Day-ahead view of Great Britain national wind generation for **January 2026**. The backend pulls live Elexon Insights data, aligns actuals to forecasts, and scores forecast quality. The frontend is a React dashboard. If Elexon is unavailable, the API returns an error and **does not substitute mock values**.

This repository is an assignment-scoped app (roughly a 16-hour build). It is **not deployed** from this README; follow the deployment section if you want to host it yourself.

## Architecture

```
Browser (Vite/React + Recharts)
        |  /api/analysis
Flask (Gunicorn)
        |  pandas / numpy alignment & MAE/RMSE/bias
Elexon Insights (no API key)
        |-- GET /datasets/FUELHH/stream?fuelType=WIND
        |-- GET /datasets/WINDFOR/stream?publishDateTimeFrom&publishDateTimeTo
```

- **Actuals:** FUELHH half-hourly generation outturn, filtered to `fuelType=WIND`.
- **Forecasts:** WINDFOR wind generation forecast publications.
- **Join key:** `startTime` (UTC instant of the settlement period).
- **Interval resolution:** FUELHH is half-hourly while WINDFOR is hourly. Records are joined exactly by `startTime`; the app does not interpolate or duplicate hourly forecasts into half-hourly periods. Coverage reports how many actual periods were paired, and the metrics use paired periods only.
- **Decision filter:** `publishTime` must be on or before the day-ahead cutoff defined below.

Verified against the live API on 24 Oct 2026:

| Dataset | Shape | Pagination | January 2026 coverage |
| --- | --- | --- | --- |
| `FUELHH` JSON | `{ data: [...] }` | None. `page` / `pageSize` were ignored. | 1,488 WIND rows for 2026-01-01..31 (31 × 48) in one stream call. |
| `FUELHH/stream` | JSON array | None | Same records, smaller payload. |
| `WINDFOR` / `WINDFOR/stream` | `{ data }` or array of `{ dataset, publishTime, startTime, generation }` | None | Historical publishes work via `publishDateTimeFrom` / `To`. One winter day had 8 publications (~584 rows). |

FUELHH fields used: `startTime`, `publishTime`, `settlementDate`, `settlementPeriod`, `fuelType`, `generation` (MW).

WINDFOR fields used: `startTime`, `publishTime`, `generation` (MW). The dataset endpoint does not include settlement date; settlement date is taken from the actuals row (or derived from `startTime` in `Europe/London` if missing).

### Day-ahead decision cutoff (assumption)

For settlement date **D**, only forecasts with

`publishTime <= 09:00 Europe/London on D-1`

are eligible. If several WINDFOR rows share the same `startTime`, the **latest eligible `publishTime`** is kept.

**Why 09:00?** The GB day-ahead auction (EPEX SPOT) typically closes around **09:20 UK time**. 09:00 is a conservative cutoff so a trader could have used the forecast before gate closure. In January 2026 the UK is on GMT, so the cutoff is 09:00 UTC.

Live WINDFOR `publishTime` values on 2025-12-31 were 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30 and 22:30 UTC. Under this rule only 02:30, 04:30 and 07:30 UTC are eligible for 1 January delivery.

### Metrics

Error is `forecast - actual` in MW.

- **MAE** = mean(|error|)
- **RMSE** = sqrt(mean(error²))
- **Bias** = mean(error). Positive bias means the forecast overstated generation.

The live January 2026 check found 1,488 FUELHH actual periods and 744 eligible matching WINDFOR hourly periods. Thus January metrics cover 744 aligned periods rather than all actual half-hours; the dashboard displays that coverage explicitly. Values are recomputed on a successful live Elexon fetch and should not be treated as permanent API results.

## Directory structure

```
backend/                 Flask API, pandas/numpy analysis, pytest
  app.py                 HTTP endpoints
  analysis.py            Alignment + metrics
  elexon_client.py       Live Elexon HTTP client
  config.py              Window, cutoff, cache, documented assumptions
  tests/                 Unit and API tests (synthetic fixtures only)
frontend/               Vite + React dashboard
  src/App.jsx            Page composition, loading/error states
  src/components/        KPI cards, chart, filters, error table
docker-compose.yml      Local backend + nginx frontend
README.md
```

## Setup

### Backend

Requires Python 3.11+. From the repository root, set up the backend environment:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest
python app.py
```

Alternatively, after creating `backend\.venv` and installing dependencies, run tests from the repository root with:

```powershell
backend\.venv\Scripts\python.exe -m pytest -c backend\pytest.ini backend\tests
```

API: `http://127.0.0.1:8000/api/health` and `http://127.0.0.1:8000/api/analysis?from=2026-01-01&to=2026-01-07`.

The first live analysis call fetches Elexon. FUELHH for the month is one request (~20s). WINDFOR is requested in 7-day publish windows and can take **1–3 minutes**. Results are cached on disk (`backend/data/`, TTL 6 hours). Subsequent date-filter changes reuse that cache. On failure the JSON body contains `error` (and `details` when useful). No sample series is returned.

### Frontend

```powershell
cd frontend
npm install
npm test
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Open `http://127.0.0.1:5173`.

To point at a remote API, set `VITE_API_URL` (no trailing slash), for example `https://your-service.onrender.com`.

### Docker

```powershell
docker compose up --build
```

- Frontend: `http://127.0.0.1:4173` (nginx proxies `/api` to the backend)
- Backend: `http://127.0.0.1:8000`

## Deployment

Not performed as part of this assignment unless you run the steps below.

**Frontend (Vercel)**

1. Import the `frontend/` directory (or this repo with root `frontend`).
2. Build command: `npm run build`. Output: `dist`.
3. Set `VITE_API_URL` to the public backend origin before building.
4. Set the backend's `CORS_ORIGINS` to the exact deployed frontend origin (for example, `https://your-dashboard.vercel.app`). The development default is permissive; do not use `*` for a public deployment.

**Backend (Render, or any Python host that can run Gunicorn)**

Render is a straightforward match for Flask:

1. Create a Web Service from `backend/`.
2. Build: `pip install -r requirements.txt`
3. Start: the included `Procfile` (`gunicorn --timeout 180 ...`).
4. Allow 180s request timeout for the first Elexon fill.
5. Set `CORS_ORIGINS` to the Vercel origin in production.

Railway or Fly.io work the same way: containerise with `backend/Dockerfile` and persist `/app/data` if you want the Elexon cache to survive restarts.

## AI tool usage

Cursor (Grok 4.6) was used to:

- Inspect Elexon FUELHH / WINDFOR docs and call the live API to confirm schemas, January 2026 coverage, and the absence of pagination.
- Propose the folder layout, cutoff assumption, and implementation order.
- Generate Flask/React/Docker/test scaffolding and iterate on alignment logic.

API field names, row counts, and publish-time schedules in this README come from those live responses, not from invented samples. Dashboard numbers are computed only after a successful Elexon fetch.
