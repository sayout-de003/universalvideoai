import { Mic, Volume2 } from "lucide-react";
import { API_BASE } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props { project: ProjectDetail; }

const STEMS = [
  { id: "master_mix", label: "Final mix", note: "Everything together, as heard in the video" },
  { id: "narration", label: "Narration", note: "Voice only" },
  { id: "music", label: "Music", note: "Background score" },
  { id: "sfx", label: "Sound effects", note: "Transitions and accents" },
];

export function AudioStudioView({ project }: Props) {
  const audioAssets = project.assets.filter((a) => a.asset_type === "audio");
  const pid = project.project.id;
  const made = project.project.status === "completed" || project.project.status === "qa_failed";
  return (
    <div className="space-y-8">
      <section>
        <h2 className="font-bold mb-3 flex items-center gap-2"><Mic className="w-4 h-4" /> Voices</h2>
        {project.speakers.length === 0 ? <div className="card p-5 hint">Voices are assigned when the script is written.</div> : (
          <ul className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {project.speakers.map((sp) => (
              <li key={sp.id} className="card p-4 text-[13px]">
                <div className="font-bold">{sp.name}</div>
                <div className="text-slate mt-0.5">{sp.role}</div>
                <div className="hint mt-1.5">{sp.voice_id} · {sp.voice_provider} · {sp.language}</div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-bold mb-3 flex items-center gap-2"><Volume2 className="w-4 h-4" /> Listen</h2>
        {!made ? <div className="card p-5 hint">Audio tracks are mixed near the end of production. They'll be playable here once the video is finished.</div> : (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {STEMS.map((s) => (
              <li key={s.id} className="card p-4">
                <div className="font-semibold text-[13px]">{s.label}</div>
                <div className="hint mb-2">{s.note}</div>
                <audio controls preload="none" className="w-full h-9" src={`${API_BASE}/api/projects/${pid}/media/stems/${s.id}.wav`} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-bold mb-3">Recorded segments ({audioAssets.length})</h2>
        {audioAssets.length === 0 ? <div className="card p-5 hint">Nothing recorded yet.</div> : (
          <ul className="card divide-y divide-rule">
            {audioAssets.map((a) => (
              <li key={a.id} className="px-4 py-2.5 flex items-center justify-between gap-3 text-[13px]">
                <span className="truncate">{a.file_path.split("/").pop()}</span>
                <span className="hint shrink-0">{a.duration_sec?.toFixed(1)}s · {a.provider}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
