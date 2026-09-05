import type { ProfileResponse } from "../types";

interface Props {
  profile: ProfileResponse;
  onReset: () => void;
}

export default function DatasetPanel({ profile, onReset }: Props) {
  const p = profile.profile;
  const cleanPct = p.n_rows
    ? (100 - (p.duplicate_rows / p.n_rows) * 100 - (p.missing_cells / (p.n_rows * p.n_cols)) * 100).toFixed(1)
    : "100";

  return (
    <div className="p-4 border-b border-slate-800">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Dataset</p>
          <p className="font-medium truncate max-w-[180px]" title={profile.name}>
            {profile.name}
          </p>
        </div>
        <button onClick={onReset} className="text-xs text-slate-500 hover:text-slate-300 underline">
          change
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 mt-3 text-sm">
        <Stat label="Rows" value={p.n_rows.toLocaleString()} />
        <Stat label="Columns" value={p.n_cols.toString()} />
        <Stat label="Numeric cols" value={p.numeric_columns.length.toString()} />
        <Stat label="Categorical cols" value={p.categorical_columns.length.toString()} />
      </div>
      <div className="mt-3 text-sm">
        <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Data quality</p>
        <div className="flex items-center gap-2">
          <span className="text-emerald-400 font-medium">{cleanPct}% clean</span>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          {p.duplicate_rows.toLocaleString()} duplicate rows &middot; {p.missing_cells.toLocaleString()} missing
          cells
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-panel2 rounded-md px-2.5 py-1.5">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}
