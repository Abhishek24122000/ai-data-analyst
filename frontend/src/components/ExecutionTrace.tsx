import type { ExecutionStep } from "../types";

export default function ExecutionTrace({ steps, ms }: { steps: ExecutionStep[]; ms: number | null }) {
  if (!steps.length) return null;
  return (
    <details className="mt-2 text-xs text-slate-500">
      <summary className="cursor-pointer hover:text-slate-300 select-none">
        Agent execution trace {ms != null && `(${ms} ms)`}
      </summary>
      <ul className="mt-1.5 flex flex-col gap-1 pl-3 border-l border-slate-800">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-1.5">
            <span
              className={
                s.status === "error"
                  ? "text-rose-400"
                  : s.status === "retried"
                  ? "text-amber-400"
                  : "text-emerald-400"
              }
            >
              {s.status === "error" ? "✗" : s.status === "retried" ? "↻" : "✓"}
            </span>
            <span>
              <span className="font-medium text-slate-400">{s.label}:</span> {s.detail}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
