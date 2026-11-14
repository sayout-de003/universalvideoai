import { useState } from "react";
import { Send } from "lucide-react";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onSendMessage: (msg: string, confirmed?: boolean) => Promise<Record<string, unknown>>;
}

export function DirectorChatView({ project, onSendMessage }: Props) {
  const [input, setInput] = useState("");
  const [pendingConfirmMsg, setPendingConfirmMsg] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const send = async (msg: string, confirmed = false) => {
    if (!msg.trim()) return;
    setSending(true);
    try {
      const res = await onSendMessage(msg, confirmed);
      setPendingConfirmMsg(res.requires_confirmation ? msg : null);
      setInput("");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-4xl">
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-zinc-100">AI Director & Production Team</h1>
        <p className="text-xs text-zinc-400 mt-1">Direct the 11-agent workforce, edit scenes, change voices, or issue voice/text production commands.</p>
      </div>
      <div className="flex-1 overflow-y-auto space-y-3 p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
        {project.messages.map((m) => (
          <div key={m.id} className={`p-3 rounded-lg text-xs ${m.role === "user" ? "bg-amber-500/10 border border-amber-500/30 ml-12 text-zinc-100" : "bg-zinc-950 border border-zinc-800 mr-12 text-zinc-300"}`}>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-amber-400 mb-1">{m.agent_name}</div>
            <div>{m.content}</div>
          </div>
        ))}
      </div>
      {pendingConfirmMsg && (
        <div className="mt-3 p-3 rounded-lg bg-amber-500/15 border border-amber-500/40 flex items-center justify-between text-xs">
          <span className="text-amber-200">Confirm destructive/voice-directed action: "{pendingConfirmMsg}"?</span>
          <div className="flex gap-2">
            <button onClick={() => send(pendingConfirmMsg, true)} className="px-3 py-1 rounded bg-amber-500 text-zinc-950 font-semibold">Confirm</button>
            <button onClick={() => setPendingConfirmMsg(null)} className="px-3 py-1 rounded bg-zinc-800 text-zinc-300">Cancel</button>
          </div>
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(input)} placeholder="Instruct the AI Director (e.g. 'Regenerate scene 2', 'Generate subtitles in Hindi and English')..." className="flex-1 rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2.5 text-xs text-zinc-100 focus:outline-none focus:border-amber-500" />
        <button disabled={sending || !input.trim()} onClick={() => send(input)} className="px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-zinc-950 text-xs font-semibold flex items-center gap-1.5">
          <Send className="w-3.5 h-3.5" /> Send
        </button>
      </div>
    </div>
  );
}
