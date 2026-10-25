function mw(value) {
  return Number(value).toLocaleString("en-GB", { maximumFractionDigits: 1 });
}

export default function ErrorTable({ rows }) {
  return (
    <section className="panel table-wrap">
      <h2>Daily error analysis</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Settlement date</th>
              <th>Periods</th>
              <th>Actual mean</th>
              <th>Forecast mean</th>
              <th>MAE</th>
              <th>RMSE</th>
              <th>Bias</th>
            </tr>
          </thead>
          <tbody>
            {(rows || []).map((row) => (
              <tr key={row.settlementDate}>
                <td>{row.settlementDate}</td>
                <td>{row.periods}</td>
                <td>{mw(row.actualMeanMw)}</td>
                <td>{mw(row.forecastMeanMw)}</td>
                <td>{mw(row.mae)}</td>
                <td>{mw(row.rmse)}</td>
                <td>{mw(row.bias)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
