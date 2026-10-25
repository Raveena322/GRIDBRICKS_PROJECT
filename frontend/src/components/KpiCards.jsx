function formatMw(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Number(value).toLocaleString("en-GB", { maximumFractionDigits: 1 })} MW`;
}

const CARDS = [
  ["MAE", "maeMw"],
  ["RMSE", "rmseMw"],
  ["Forecast bias", "biasMw"],
  ["Mean actual", "meanActualMw"],
];

export default function KpiCards({ kpis, loading }) {
  if (loading) {
    return (
      <section className="kpis" aria-busy="true">
        {CARDS.map(([label]) => (
          <div className="skeleton" key={label} />
        ))}
      </section>
    );
  }

  return (
    <section className="kpis">
      {CARDS.map(([label, key]) => (
        <article className="panel kpi" key={key}>
          <span>{label}</span>
          <strong>{formatMw(kpis?.[key])}</strong>
        </article>
      ))}
    </section>
  );
}
