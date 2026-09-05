import type { Suggestion } from "../types";

interface Props {
  suggestions: Suggestion[];
  onAsk: (question: string) => void;
  disabled: boolean;
}

export default function SuggestionsPanel({ suggestions, onAsk, disabled }: Props) {
  const grouped = suggestions.reduce<Record<string, Suggestion[]>>((acc, s) => {
    (acc[s.category] ||= []).push(s);
    return acc;
  }, {});

  return (
    <div className="p-4 flex-1 overflow-y-auto">
      <p className="text-xs uppercase tracking-wide text-slate-500 mb-2">Suggested questions</p>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="mb-4">
          <p className="text-[11px] font-semibold text-accent2 mb-1">{category}</p>
          <div className="flex flex-col gap-1.5">
            {items.map((s, i) => (
              <button
                key={i}
                disabled={disabled}
                onClick={() => onAsk(s.question)}
                className="text-left text-sm px-2.5 py-1.5 rounded-md bg-panel2 hover:bg-slate-700 transition-colors disabled:opacity-40"
              >
                {s.question}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
