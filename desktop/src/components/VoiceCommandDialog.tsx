import { useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";

interface Props {
  onClose: () => void;
  onSubmit: (transcript: string) => void;
}

const EXAMPLES = ["Regenerate scene 2", "Make the background music quieter", "Export the final film in 4K"];

// Electron has no window.prompt, so the voice-command text box lives here.
export function VoiceCommandDialog({ onClose, onSubmit }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  const submit = () => {
    if (!text.trim()) return;
    onSubmit(text.trim());
    onClose();
  };
  return (
    <div className="fixed inset-0 bg-ink/50 flex items-start justify-center pt-[18vh] z-50" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Voice command" className="card w-[520px] p-5" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.key === "Escape" && onClose()}>
        <div className="flex items-center gap-2 font-bold mb-1"><Mic className="w-4 h-4" /> Tell the studio what to do</div>
        <p className="hint mb-3">Type it, or dictate with your OpenWhispr hotkey while this box is focused.</p>
        <input ref={ref} className="field" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="e.g. Regenerate scene 2" />
        <div className="flex flex-wrap gap-2 mt-3">
          {EXAMPLES.map((ex) => <button key={ex} className="chip hover:text-ink" onClick={() => setText(ex)}>{ex}</button>)}
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button className="btn btn-quiet" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!text.trim()} onClick={submit}>Run command</button>
        </div>
      </div>
    </div>
  );
}
