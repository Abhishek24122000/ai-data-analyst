import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSpec } from "../types";

function fmtValue(v: unknown): string {
  if (typeof v === "number") {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
    if (Math.abs(v) >= 1_000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(v);
}

export default function ChartView({ chart }: { chart: ChartSpec }) {
  if (!chart || chart.type === "empty") return null;

  if (chart.type === "stat") {
    const row = chart.data?.[0];
    const value = row ? Object.values(row)[0] : undefined;
    return (
      <div className="mt-3 bg-panel2 rounded-lg px-5 py-4 inline-block">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">{chart.value_key}</p>
        <p className="text-2xl font-semibold text-accent2 mt-1">{fmtValue(value)}</p>
      </div>
    );
  }

  const data = chart.data || [];

  if (chart.type === "line" && chart.x_key && chart.y_key) {
    return (
      <div className="mt-3 h-64 w-full max-w-xl">
        <ResponsiveContainer>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#232a40" />
            <XAxis dataKey={chart.x_key} tick={{ fontSize: 11, fill: "#8b93ac" }} />
            <YAxis tick={{ fontSize: 11, fill: "#8b93ac" }} tickFormatter={fmtValue} />
            <Tooltip
              contentStyle={{ background: "#161c2b", border: "1px solid #2a3350", fontSize: 12 }}
              formatter={(v: number) => fmtValue(v)}
            />
            <Line type="monotone" dataKey={chart.y_key} stroke="#22d3ee" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "bar" && chart.x_key && chart.y_key) {
    return (
      <div className="mt-3 h-64 w-full max-w-xl">
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#232a40" />
            <XAxis dataKey={chart.x_key} tick={{ fontSize: 11, fill: "#8b93ac" }} />
            <YAxis tick={{ fontSize: 11, fill: "#8b93ac" }} tickFormatter={fmtValue} />
            <Tooltip
              contentStyle={{ background: "#161c2b", border: "1px solid #2a3350", fontSize: 12 }}
              formatter={(v: number) => fmtValue(v)}
            />
            <Bar dataKey={chart.y_key} fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "scatter" && chart.x_key && chart.y_key) {
    return (
      <div className="mt-3 h-64 w-full max-w-xl">
        <ResponsiveContainer>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#232a40" />
            <XAxis dataKey={chart.x_key} tick={{ fontSize: 11, fill: "#8b93ac" }} />
            <YAxis dataKey={chart.y_key} tick={{ fontSize: 11, fill: "#8b93ac" }} />
            <Tooltip contentStyle={{ background: "#161c2b", border: "1px solid #2a3350", fontSize: 12 }} />
            <Scatter data={data} fill="#22d3ee" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // table fallback
  const columns = chart.columns || (data[0] ? Object.keys(data[0]) : []);
  return (
    <div className="mt-3 overflow-x-auto max-w-xl border border-slate-800 rounded-lg">
      <table className="text-sm w-full">
        <thead className="bg-panel2">
          <tr>
            {columns.map((c) => (
              <th key={c} className="text-left px-3 py-1.5 font-medium text-slate-400">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.slice(0, 20).map((row, i) => (
            <tr key={i} className="border-t border-slate-800">
              {columns.map((c) => (
                <td key={c} className="px-3 py-1.5">
                  {fmtValue(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
