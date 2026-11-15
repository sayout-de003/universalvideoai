import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { humanDuration } from "../lib/progress";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onRegenerateScene: (sceneId: string) => Promise<void>;
}

export function StoryboardView({ project, onRegenerateScene }: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const regenerate = async (id: string) => {
    setBusyId(id);
    try { await onRegenerateScene(id); } finally { setBusyId(null); }
  };

  if (project.scenes.length === 0) {
    return <div className="card p-10 text-center"><div className="font-bold text-lg">No scenes yet</div><p className="text-slate mt-1">Scenes appear here once the script is written.</p></div>;
  }
  return (
    <div className="space-y-8">
      {project.characters.length > 0 && (
        <section>
          <h2 className="font-bold mb-3">Characters</h2>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {project.characters.map((ch) => (
              <li key={ch.id} className="card p-4 text-[13px]">
                <div className="font-bold">{ch.name} <span className="font-normal text-slate">· {ch.role}</span></div>
                <p className="text-slate mt-1">{ch.visual_description}</p>
                <div className="hint mt-1.5">Voice: {ch.voice_id}</div>
              </li>
            ))}
          </ul>
        </section>
      )}
      {project.chapters.map((ch) => {
        const scenes = project.scenes.filter((s) => s.chapter_id === ch.id);
        return (
          <section key={ch.id}>
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="font-bold">{ch.title}</h2>
              <span className="hint">{scenes.length} scenes · about {humanDuration(ch.target_duration_sec)}</span>
            </div>
            <ul className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {scenes.map((sc) => {
                const shot = project.shots.find((sh) => sh.scene_id === sc.id);
                const made = sc.quality_status === "generated";
                return (
                  <li key={sc.id} className="card p-4 flex flex-col justify-between gap-3">
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-[13px]">{sc.title}</span>
                        <span className="timecode text-xs text-slate shrink-0">{humanDuration(sc.duration_sec)}</span>
                      </div>
                      <p className="text-[13px] text-slate mt-2 line-clamp-4">{sc.narration_segment}</p>
                      {shot && <div className="hint mt-2">{shot.shot_type}, {shot.camera_movement}</div>}
                    </div>
                    <div className="flex items-center justify-between pt-3 border-t border-rule">
                      <span className={`chip ${made ? "chip-done" : ""}`}>{made ? "Made" : "Not made yet"}</span>
                      <button onClick={() => regenerate(sc.id)} disabled={busyId !== null} className="btn btn-ghost text-[13px]">
                        <RefreshCw className={`w-3.5 h-3.5 ${busyId === sc.id ? "animate-spin" : ""}`} /> {busyId === sc.id ? "Redoing…" : "Redo this scene"}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
