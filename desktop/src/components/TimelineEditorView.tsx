import { useState } from "react";
import { Redo2, Scissors, Trash2, Undo2 } from "lucide-react";
import { API_BASE } from "../api/client";
import { timecode } from "../lib/progress";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onTimelineOp: (op: Record<string, unknown>) => Promise<void>;
  onUndo: () => Promise<void>;
  onRedo: () => Promise<void>;
}

const TRACKS = ["main_video", "secondary_video", "overlay_video", "background", "narration", "dialogue", "music", "sfx", "ambience", "captions", "titles", "graphics"];

export function TimelineEditorView({ project, onTimelineOp, onUndo, onRedo }: Props) {
  const pid = project.project.id;
  const [showEmpty, setShowEmpty] = useState(false);
  const finished = project.project.status === "completed" || project.project.status === "qa_failed";
  const maxDur = Math.max(15, ...project.timeline.map((c) => c.start_sec + c.duration_sec));
  const ticks = Array.from({ length: 6 }, (_, i) => (maxDur / 5) * i);
  const tracks = TRACKS.filter((t) => showEmpty || project.timeline.some((c) => c.track === t));

  if (project.timeline.length === 0) {
    return <div className="card p-10 text-center"><div className="font-bold text-lg">Nothing to edit yet</div><p className="text-slate mt-1">The timeline fills in as scenes are made.</p></div>;
  }
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-slate max-w-[60ch]">Split or remove clips. Your edits are kept when a single scene is redone.</p>
        <div className="flex gap-2">
          <button onClick={onUndo} className="btn btn-quiet"><Undo2 className="w-4 h-4" /> Undo</button>
          <button onClick={onRedo} className="btn btn-quiet"><Redo2 className="w-4 h-4" /> Redo</button>
        </div>
      </div>
      {finished && (
        <div className="rounded-lg bg-ink overflow-hidden aspect-video max-h-[340px] mx-auto">
          <video controls className="w-full h-full object-contain" src={`${API_BASE}/api/projects/${pid}/media/exports/final_production.mp4`} />
        </div>
      )}
      <div className="card p-4 overflow-x-auto">
        <div className="min-w-[760px] space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-28 shrink-0" />
            <div className="flex-1 flex justify-between timecode text-xs text-mute">{ticks.map((t) => <span key={t}>{timecode(t)}</span>)}</div>
          </div>
          {tracks.map((track) => (
            <div key={track} className="flex items-center gap-2">
              <div className="w-28 shrink-0 text-xs font-semibold text-slate capitalize">{track.replace(/_/g, " ")}</div>
              <div className="flex-1 h-9 rounded bg-sunken border border-rule relative overflow-hidden">
                {project.timeline.filter((c) => c.track === track).map((c) => (
                  <div key={c.id}
                    style={{ left: `${(c.start_sec / maxDur) * 100}%`, width: `${Math.max(2, (c.duration_sec / maxDur) * 100)}%` }}
                    title={`${c.label} (${timecode(c.start_sec)} to ${timecode(c.start_sec + c.duration_sec)})`}
                    className={`absolute top-1 bottom-1 rounded px-2 flex items-center justify-between gap-1 text-[11px] border ${c.manual_edited ? "bg-hold-soft border-hold text-hold" : "bg-white border-ink/30 text-ink"}`}>
                    <span className="truncate">{c.label}</span>
                    <span className="flex items-center gap-1 shrink-0">
                      <button onClick={() => onTimelineOp({ operation: "split", clip_id: c.id })} aria-label={`Split ${c.label}`} title="Split clip" className="hover:text-live"><Scissors className="w-3 h-3" /></button>
                      <button onClick={() => { if (window.confirm(`Remove "${c.label}" and close the gap?`)) onTimelineOp({ operation: "ripple_delete", clip_id: c.id }); }} aria-label={`Remove ${c.label}`} title="Remove clip and close the gap" className="hover:text-live"><Trash2 className="w-3 h-3" /></button>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <button onClick={() => setShowEmpty((v) => !v)} className="btn btn-ghost mt-3 -ml-2 text-[13px]">{showEmpty ? "Hide empty tracks" : "Show empty tracks"}</button>
      </div>
    </div>
  );
}
