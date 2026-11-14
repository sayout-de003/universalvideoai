import { RefreshCw, Users } from "lucide-react";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onRegenerateScene: (sceneId: string) => Promise<void>;
}

export function StoryboardView({ project, onRegenerateScene }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Storyboard & Character Continuity</h1>
        <p className="text-xs text-zinc-400 mt-1">Hierarchical Chapters → Scenes → Shots. Regenerate any individual scene without rebuilding the entire film.</p>
      </div>
      {project.characters.length > 0 && (
        <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800">
          <div className="text-xs font-semibold text-zinc-200 flex items-center gap-2 mb-3"><Users className="w-4 h-4 text-amber-400" /> Character Continuity Bible</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {project.characters.map((ch) => (
              <div key={ch.id} className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs">
                <div className="font-semibold text-amber-300">{ch.name} <span className="text-zinc-500 font-normal">({ch.role})</span></div>
                <div className="text-zinc-400 mt-1">{ch.visual_description}</div>
                <div className="text-[11px] text-zinc-500 mt-1">Voice ID: {ch.voice_id}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      {project.chapters.map((ch) => {
        const chScenes = project.scenes.filter((s) => s.chapter_id === ch.id);
        return (
          <div key={ch.id} className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800 space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">{ch.title}</h2>
              <div className="text-[11px] text-zinc-500">Target: {ch.target_duration_sec}s · Status: {ch.status}</div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {chScenes.map((sc) => {
                const shot = project.shots.find((sh) => sh.scene_id === sc.id);
                return (
                  <div key={sc.id} className="p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 flex flex-col justify-between space-y-3">
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-zinc-200 truncate">{sc.title}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">{sc.duration_sec}s</span>
                      </div>
                      <p className="text-[11px] text-zinc-400 mt-2 line-clamp-3">{sc.narration_segment}</p>
                      {shot && <div className="text-[10px] text-zinc-500 mt-2">Shot: {shot.shot_type} · {shot.camera_movement} · {sc.render_engine}</div>}
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-zinc-900">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${sc.quality_status === "generated" ? "bg-emerald-500/15 text-emerald-300" : "bg-zinc-800 text-zinc-400"}`}>{sc.quality_status}</span>
                      <button onClick={() => onRegenerateScene(sc.id)} className="flex items-center gap-1 text-[11px] text-amber-400 hover:text-amber-300"><RefreshCw className="w-3 h-3" /> Regenerate Scene</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
