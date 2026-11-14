import { Mic, Volume2 } from "lucide-react";
import { API_BASE } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props { project: ProjectDetail; }

export function AudioStudioView({ project }: Props) {
  const audioAssets = project.assets.filter((a) => a.asset_type === "audio");
  const pid = project.project.id;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Audio Production Studio</h1>
        <p className="text-xs text-zinc-400 mt-1">Speaker assignments, TTS narration segments, ducked music score, sound effects, and separate audio stems.</p>
      </div>
      <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800">
        <div className="text-xs font-semibold text-zinc-200 flex items-center gap-2 mb-3"><Mic className="w-4 h-4 text-amber-400" /> Speaker & Voice Bible</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {project.speakers.map((sp) => (
            <div key={sp.id} className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs">
              <div className="font-semibold text-zinc-100">{sp.name}</div>
              <div className="text-zinc-400 mt-0.5">Role: {sp.role} · Voice: {sp.voice_id} ({sp.voice_provider})</div>
              <div className="text-[11px] text-zinc-500 mt-0.5">Language: {sp.language}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
        <div className="text-xs font-semibold text-zinc-200 flex items-center gap-2"><Volume2 className="w-4 h-4 text-sky-400" /> Audio Stems & Master Mix</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {["master_mix", "narration", "music", "sfx"].map((stem) => (
            <div key={stem} className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
              <div className="text-xs font-medium text-zinc-300 capitalize mb-2">{stem.replace("_", " ")} Stem</div>
              <audio controls className="w-full h-8" src={`${API_BASE}/api/projects/${pid}/media/stems/${stem}.wav`} />
            </div>
          ))}
        </div>
      </div>
      <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
        <div className="text-xs font-semibold text-zinc-200 mb-3">Generated Voice & Audio Segments ({audioAssets.length})</div>
        <div className="space-y-2">
          {audioAssets.map((a) => (
            <div key={a.id} className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs">
              <div className="text-zinc-200">{a.file_path.split("/").pop()}</div>
              <div className="text-[11px] text-zinc-500">Provider: {a.provider} · Duration: {a.duration_sec?.toFixed(2)}s · License: {a.license}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
