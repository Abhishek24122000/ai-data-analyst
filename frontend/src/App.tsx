import { useEffect, useState } from "react";
import { checkHealth, loadSampleDataset, sendChatMessage, uploadDataset } from "./api";
import ChatPanel from "./components/ChatPanel";
import DatasetPanel from "./components/DatasetPanel";
import SuggestionsPanel from "./components/SuggestionsPanel";
import UploadPanel from "./components/UploadPanel";
import type { ChatMessage, ProfileResponse } from "./types";

function newId() {
  return Math.random().toString(36).slice(2);
}

export default function App() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingDataset, setLoadingDataset] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmEnabled, setLlmEnabled] = useState(true);
  const [sessionId] = useState(newId());

  useEffect(() => {
    checkHealth()
      .then((h) => setLlmEnabled(h.llm_enabled))
      .catch(() => setLlmEnabled(true)); // don't show the warning banner just because health check failed
  }, []);

  const handleUpload = async (file: File) => {
    setError(null);
    setLoadingDataset(true);
    try {
      const p = await uploadDataset(file);
      setProfile(p);
      setMessages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setLoadingDataset(false);
    }
  };

  const handleLoadSample = async () => {
    setError(null);
    setLoadingDataset(true);
    try {
      const p = await loadSampleDataset();
      setProfile(p);
      setMessages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load sample dataset.");
    } finally {
      setLoadingDataset(false);
    }
  };

  const handleAsk = async (question: string) => {
    if (!profile) return;
    setMessages((prev) => [...prev, { id: newId(), role: "user", text: question }]);
    setLoadingChat(true);
    try {
      const resp = await sendChatMessage(sessionId, profile.dataset_id, question);
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "assistant", text: resp.answer, response: resp },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          text: e instanceof Error ? `Error: ${e.message}` : "Something went wrong.",
        },
      ]);
    } finally {
      setLoadingChat(false);
    }
  };

  if (!profile) {
    return (
      <div className="h-screen bg-ink flex flex-col">
        <UploadPanel onUpload={handleUpload} onLoadSample={handleLoadSample} loading={loadingDataset} />
        {error && <p className="text-center text-rose-400 text-sm pb-6">{error}</p>}
      </div>
    );
  }

  return (
    <div className="h-screen bg-ink flex">
      <aside className="w-72 border-r border-slate-800 bg-panel flex flex-col shrink-0">
        <DatasetPanel profile={profile} onReset={() => setProfile(null)} />
        <SuggestionsPanel suggestions={profile.suggestions} onAsk={handleAsk} disabled={loadingChat} />
      </aside>
      <main className="flex-1 flex flex-col min-w-0">
        <header className="border-b border-slate-800 px-6 py-3.5">
          <h1 className="font-semibold tracking-tight">AI Data Analyst</h1>
        </header>
        <ChatPanel messages={messages} onSend={handleAsk} loading={loadingChat} llmEnabled={llmEnabled} />
      </main>
    </div>
  );
}
