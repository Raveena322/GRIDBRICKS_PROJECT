import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function tickLabel(iso) {
  const date = new Date(iso);
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

export default function ForecastChart({ series }) {
  const data = (series || []).map((row) => ({
    ...row,
    label: tickLabel(row.startTime),
  }));

  return (
    <section className="panel chart">
      <h2>Actual vs day-ahead forecast</h2>
      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: 8, bottom: 8 }}>
          <CartesianGrid stroke="#e6dece" />
          <XAxis dataKey="label" minTickGap={28} tick={{ fontSize: 12 }} />
          <YAxis
            tick={{ fontSize: 12 }}
            label={{ value: "MW", angle: -90, position: "insideLeft" }}
          />
          <Tooltip
            formatter={(value, name) => [
              `${Number(value).toLocaleString("en-GB")} MW`,
              name,
            ]}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="actualMw"
            name="Actual (FUELHH WIND)"
            stroke="#1f6f64"
            dot={false}
            strokeWidth={2}
          />
          <Line
            type="monotone"
            dataKey="forecastMw"
            name="Forecast at cutoff (WINDFOR)"
            stroke="#c45c26"
            dot={false}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}
