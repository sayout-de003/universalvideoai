import { Redo2, Scissors, Trash2, Undo2 } from "lucide-react";
import { API_BASE } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onTimelineOp: (op: Record<string, unknown>) => Promise<void>;
  onUndo: () => Promise<void>;
  onRedo: () => Promise<void>;
}

const TRACKS = ["main_video","secondary_video","overlay_video","background","narration","dialogue","music","sfx","ambience","captions","titles","graphics"];

export function TimelineEditorView({ project, onTimelineOp, onUndo, onRedo }: Props) {
  const pid = project.project.id;
  const maxDur = Math.max(15, ...project.timeline.map((c) => c.start_sec + c.duration_sec));
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Multitrack Timeline Editor</h1>
          <p className="text-xs text-zinc-400 mt-1">12-track non-destructive NLE timeline. Manual edits are locked and preserved during single-scene AI regeneration.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={onUndo} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200"><Undo2 className="w-3.5 h-3.5" /> Undo</button>
          <button onClick={onRedo} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200"><Redo2 className="w-3.5 h-3.5" /> Redo</button>
        </div>
      </div>
      <div className="rounded-xl bg-black border border-zinc-800 overflow-hidden aspect-video max-h-[340px] mx-auto">
        <video controls className="w-full h-full object-contain" src={`${API_BASE}/api/projects/${pid}/media/exports/final_production.mp4`} />
      </div>
      <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-2 overflow-x-auto">
        {TRACKS.map((track) => {
          const clips = project.timeline.filter((c) => c.track === track);
          return (
            <div key={track} className="flex items-center gap-2 min-w-[780px]">
              <div className="w-32 shrink-0 text-[11px] font-medium text-zinc-400 uppercase tracking-wider">{track.replace("_", " ")}</div>
              <div className="flex-1 h-9 rounded bg-zinc-950 border border-zinc-800 relative overflow-hidden">
                {clips.map((c) => (
                  <div
                    key={c.id}
                    style={{ left: `${(c.start_sec / maxDur) * 100}%`, width: `${Math.max(2, (c.duration_sec / maxDur) * 100)}%` }}
                    title={`${c.label} (${c.start_sec.toFixed(1)}s - ${(c.start_sec + c.duration_sec).toFixed(1)}s)`}
                    className={`absolute top-1 bottom-1 rounded px-2 flex items-center justify-between text-[10px] truncate border ${c.manual_edited ? "bg-amber-500/25 border-amber-400 text-amber-200" : "bg-sky-500/20 border-sky-500/40 text-sky-200"}`}
                  >
                    <span className="truncate">{c.label}</span>
                    <span className="flex items-center gap-1 ml-1 shrink-0">
                      <button onClick={() => onTimelineOp({ operation: "split", clip_id: c.id })} title="Split clip" className="hover:text-white"><Scissors className="w-2.5 h-2.5" /></button>
                      <button onClick={() => onTimelineOp({ operation: "ripple_delete", clip_id: c.id })} title="Ripple delete" className="hover:text-red-300"><Trash2 className="w-2.5 h-2.5" /></button>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
