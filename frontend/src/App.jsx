import { useEffect, useState } from "react";
import DateFilters from "./components/DateFilters.jsx";
import ErrorTable from "./components/ErrorTable.jsx";
import ForecastChart from "./components/ForecastChart.jsx";
import KpiCards from "./components/KpiCards.jsx";
import { ANALYSIS_MAX, ANALYSIS_MIN, fetchAnalysis, validateDateRange } from "./api";

export default function App() {
  const [from, setFrom] = useState(ANALYSIS_MIN);
  const [to, setTo] = useState(ANALYSIS_MAX);
  const [query, setQuery] = useState({
    from: ANALYSIS_MIN,
    to: ANALYSIS_MAX,
    refresh: false,
    key: 0,
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [validation, setValidation] = useState(null);

  useEffect(() => {
    const invalid = validateDateRange(query.from, query.to);
    if (invalid) {
      setValidation(invalid);
      setLoading(false);
      return undefined;
    }
    setValidation(null);
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchAnalysis({
      from: query.from,
      to: query.to,
      refresh: query.refresh,
      signal: controller.signal,
    })
      .then((payload) => setData(payload))
      .catch((err) => {
        if (err.name === "AbortError") return;
        setData(null);
        setError(err);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [query]);

  const cutoff = data?.assumptions?.decisionCutoff;

  return (
    <main className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">January 2026 · Great Britain</p>
          <h1>UK Wind Power Forecast Dashboard</h1>
          <p className="lede">
            Day-ahead purchasing view of national wind generation: Elexon FUELHH
            actuals aligned to WINDFOR on <code>startTime</code>, using only
            forecasts published by the D-1 09:00 Europe/London cutoff.
          </p>
        </div>
        <aside className="panel filters">
          <DateFilters
            from={from}
            to={to}
            loading={loading}
            onChange={({ from: nextFrom, to: nextTo }) => {
              setFrom(nextFrom);
              setTo(nextTo);
            }}
            onSubmit={() =>
              setQuery((current) => ({
                from,
                to,
                refresh: false,
                key: current.key + 1,
              }))
            }
            onRefresh={() =>
              setQuery((current) => ({
                from,
                to,
                refresh: true,
                key: current.key + 1,
              }))
            }
          />
          <p className="cutoff">
            {cutoff
              ? cutoff.rule
              : "Cutoff assumption is returned with live analysis results."}
          </p>
        </aside>
      </header>

      {validation && (
        <div className="banner error" role="alert">
          {validation}
        </div>
      )}
      {error && (
        <div className="banner error" role="alert">
          {error.message}
          {error.details ? ` ${error.details}` : ""}
        </div>
      )}
      {loading && (
        <div className="banner info">
          Loading live Elexon series. The first request can take a couple of
          minutes because WINDFOR is fetched in weekly publish-time windows and
          is not replaced with sample data.
        </div>
      )}
      {!loading && data?.coverage &&
        data.coverage.alignedPeriods < data.coverage.actualPeriodsInWindow && (
          <div className="banner info" role="status">
            Metrics use only matching <code>startTime</code> intervals: {data.coverage.alignedPeriods} of{" "}
            {data.coverage.actualPeriodsInWindow} actual periods aligned. Unmatched actual periods are
            excluded, not filled or interpolated.
          </div>
        )}

      <KpiCards kpis={data?.kpis} loading={loading} />
      {!error && data?.series?.length ? <ForecastChart series={data.series} /> : null}
      {!error && data?.dailyErrors?.length ? (
        <ErrorTable rows={data.dailyErrors} />
      ) : null}

      {data?.source && (
        <p className="footnote">
          Live Elexon rows: {data.source.actualRows} actual, {data.source.forecastRows}{" "}
          forecast. Fetched at {data.source.fetchedAt}. Paired periods:{" "}
          {data.kpis.pairedPeriods}. Mocked: {String(data.source.mocked)}.
        </p>
      )}
    </main>
  );
}
