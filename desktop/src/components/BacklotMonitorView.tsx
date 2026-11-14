import { CheckCircle2, Pause, Play, RotateCcw, XCircle } from "lucide-react";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  liveEvents: Array<Record<string, unknown>>;
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
}

export function BacklotMonitorView({ project, liveEvents, onRun, onPause, onResume }: Props) {
  const latestQa = project.qa_reports[0];
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Backlot Production Monitor</h1>
          <p className="text-xs text-zinc-400 mt-1">Live SSE telemetry, stage checkpoints, pause/resume controls, and real FFprobe QA results.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onRun} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 text-xs font-semibold"><Play className="w-3.5 h-3.5" /> Run Production</button>
          <button onClick={onPause} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium"><Pause className="w-3.5 h-3.5" /> Pause</button>
          <button onClick={onResume} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"><RotateCcw className="w-3.5 h-3.5" /> Resume</button>
        </div>
      </div>
      {latestQa && (
        <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-zinc-200">Quality Assurance Report (FFprobe / FFmpeg Verified)</div>
            <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${latestQa.passed ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>{latestQa.summary}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {latestQa.checks.map((c) => (
              <div key={c.name} className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 flex items-start gap-2 text-xs">
                {c.passed ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" /> : <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />}
                <div><div className="font-medium text-zinc-200">{c.name}</div><div className="text-[11px] text-zinc-500">{c.details}</div></div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
          <div className="text-xs font-semibold text-zinc-200 mb-3">Stage Checkpoints ({project.checkpoints.length})</div>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {project.checkpoints.map((ck) => (
              <div key={ck.id} className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 flex items-center justify-between text-xs">
                <span className="font-medium text-zinc-200 capitalize">{ck.stage.replace(/_/g, " ")}</span>
                <span className="text-[11px] text-zinc-400">{ck.status}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
          <div className="text-xs font-semibold text-zinc-200 mb-3">Live Production Events (SSE)</div>
          <div className="space-y-1.5 max-h-72 overflow-y-auto font-mono text-[11px]">
            {liveEvents.length === 0 ? <div className="text-zinc-500">Listening for live events...</div> : liveEvents.map((ev, i) => (
              <div key={i} className="p-2 rounded bg-zinc-950 border border-zinc-900 text-zinc-300"><span className="text-amber-400">{String(ev.type)}</span> {JSON.stringify(ev)}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
