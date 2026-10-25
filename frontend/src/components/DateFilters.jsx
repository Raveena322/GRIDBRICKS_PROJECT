import { ANALYSIS_MAX, ANALYSIS_MIN } from "../api";

export default function DateFilters({
  from,
  to,
  onChange,
  onSubmit,
  onRefresh,
  loading,
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label>
        From
        <input
          type="date"
          min={ANALYSIS_MIN}
          max={ANALYSIS_MAX}
          value={from}
          onChange={(event) => onChange({ from: event.target.value, to })}
          required
        />
      </label>
      <label>
        To
        <input
          type="date"
          min={ANALYSIS_MIN}
          max={ANALYSIS_MAX}
          value={to}
          onChange={(event) => onChange({ from, to: event.target.value })}
          required
        />
      </label>
      <div className="actions">
        <button type="submit" disabled={loading}>
          {loading ? "Loading…" : "Apply dates"}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={onRefresh}
          disabled={loading}
        >
          Refresh live Elexon
        </button>
      </div>
    </form>
  );
}
