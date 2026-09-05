import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";
import ChartView from "./ChartView";
import ExecutionTrace from "./ExecutionTrace";

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
  llmEnabled: boolean;
}

export default function ChatPanel({ messages, onSend, loading, llmEnabled }: Props) {
  const [text, setText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const submit = () => {
    if (!text.trim() || loading) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div className="flex flex-col h-full">
      {!llmEnabled && (
        <div className="bg-amber-500/10 border-b border-amber-500/30 text-amber-300 text-xs px-4 py-2">
          No LLM API key configured on the backend -- running in deterministic fallback mode (handles common
          totals / breakdowns / trends / rankings; open-ended questions will be less accurate). Set{" "}
          <code>LLM_API_KEY</code> in the backend .env to enable full natural-language understanding.
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5">
        {messages.length === 0 && (
          <p className="text-slate-500 text-sm">
            Ask a question below, or click a suggested question on the left to get started.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "self-end max-w-lg" : "self-start max-w-xl"}>
            {m.role === "user" ? (
              <div className="bg-accent text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">{m.text}</div>
            ) : (
              <div className="bg-panel border border-slate-800 rounded-2xl rounded-bl-sm px-4 py-3.5">
                <p className="text-sm leading-relaxed">{m.text}</p>
                {m.response?.chart && <ChartView chart={m.response.chart} />}
                {m.response?.sql && (
                  <details className="mt-2.5 text-xs">
                    <summary className="cursor-pointer text-slate-500 hover:text-slate-300 select-none">
                      Generated SQL
                    </summary>
                    <pre className="mt-1.5 bg-ink border border-slate-800 rounded-md p-2.5 overflow-x-auto text-[11px] text-accent2">
                      {m.response.sql}
                    </pre>
                  </details>
                )}
                {m.response && (
                  <ExecutionTrace steps={m.response.execution_trace} ms={m.response.execution_ms} />
                )}
                {m.response?.low_confidence && (
                  <p className="mt-2 text-[11px] text-amber-400">
                    ⚠ Low-confidence match -- consider rephrasing or enabling a real LLM key for this question.
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="self-start bg-panel border border-slate-800 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-slate-500">
            Analyzing...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-800 p-4 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Ask a question about your data..."
          className="flex-1 bg-panel2 rounded-lg px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent placeholder:text-slate-500"
        />
        <button
          onClick={submit}
          disabled={loading || !text.trim()}
          className="px-5 py-2.5 rounded-lg bg-accent hover:bg-indigo-500 transition-colors font-medium text-sm disabled:opacity-40"
        >
          Ask
        </button>
      </div>
    </div>
  );
}
