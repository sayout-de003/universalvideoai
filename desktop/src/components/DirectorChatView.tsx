import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onSendMessage: (msg: string, confirmed?: boolean) => Promise<Record<string, unknown>>;
}

const SUGGESTIONS = ["Redo scene 2", "Add subtitles in Hindi and English", "Make the narration slower"];

export function DirectorChatView({ project, onSendMessage }: Props) {
  const [input, setInput] = useState("");
  const [pendingConfirmMsg, setPendingConfirmMsg] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [project.messages.length]);

  const send = async (msg: string, confirmed = false) => {
    if (!msg.trim()) return;
    setSending(true);
    setError(null);
    try {
      const res = await onSendMessage(msg, confirmed);
      setPendingConfirmMsg(res.requires_confirmation ? msg : null);
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="max-w-3xl flex flex-col gap-3">
      <p className="text-slate">Ask the production team to change something. For example, redo a scene, change a voice, or add subtitles.</p>
      <div className="card p-4 space-y-3 min-h-[320px] max-h-[55vh] overflow-y-auto">
        {project.messages.length === 0 && <div className="hint">No messages yet. Try one of the suggestions below.</div>}
        {project.messages.map((m) => (
          <div key={m.id} className={`rounded-lg px-3.5 py-2.5 text-[13px] max-w-[85%] ${m.role === "user" ? "bg-ink text-white ml-auto" : "bg-sunken border border-rule"}`}>
            {m.role !== "user" && <div className="text-xs font-bold text-slate mb-0.5">{m.agent_name}</div>}
            <div className="whitespace-pre-wrap">{m.content}</div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      {error && <div role="alert" className="px-3 py-2 rounded-lg text-[13px] bg-live-soft border border-live/40 text-live">{error}</div>}
      {pendingConfirmMsg && (
        <div className="px-4 py-3 rounded-lg bg-hold-soft border border-hold/40 flex items-center justify-between gap-3 text-[13px]">
          <span>This will change or remove work: “{pendingConfirmMsg}”. Go ahead?</span>
          <span className="flex gap-2 shrink-0">
            <button onClick={() => send(pendingConfirmMsg, true)} className="btn btn-primary py-1.5">Yes, do it</button>
            <button onClick={() => setPendingConfirmMsg(null)} className="btn btn-quiet py-1.5">Cancel</button>
          </span>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => <button key={s} onClick={() => setInput(s)} className="chip hover:text-ink">{s}</button>)}
      </div>
      <div className="flex gap-2">
        <input aria-label="Message to the director" className="field" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(input)} placeholder="What should change?" />
        <button disabled={sending || !input.trim()} onClick={() => send(input)} className="btn btn-primary"><Send className="w-4 h-4" /> Send</button>
      </div>
    </div>
  );
}
