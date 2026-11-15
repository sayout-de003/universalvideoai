import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { API_BASE } from "../api/client";
import { humanDuration } from "../lib/progress";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onRegenerateScene: (sceneId: string) => Promise<void>;
}

function cleanCharacterDesc(raw: string, fallbackTitle: string): string {
  const s = (raw || "").trim();
  if (s.includes("# SCREENPLAY") || s.includes("## SCENE") || s.length > 260) {
    const visMatch = s.match(/\*\*VISUAL:\*\*\s*([^*#]+)/i);
    if (visMatch && visMatch[1]) {
      return visMatch[1].trim().slice(0, 220);
    }
    return `Consistent visual identity for ${fallbackTitle.replace(/^[#*\s]+|SCREENPLAY:\s*|\*Format:.*$/gi, "").trim() || "Lead Subject"}: locked facial features, wardrobe, silhouette, and cinematic color grading across all scenes.`;
  }
  return s;
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
          <h2 className="font-bold mb-3">Characters & Visual Continuity</h2>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {project.characters.map((ch) => (
              <li key={ch.id} className="card p-4 text-[13px]">
                <div className="font-bold">{ch.name} <span className="font-normal text-slate">· {ch.role}</span></div>
                <p className="text-slate mt-1">{cleanCharacterDesc(ch.visual_description, project.project.title)}</p>
                <div className="hint mt-1.5">Voice profile: {ch.voice_id} · Neural Human TTS</div>
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
            <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {scenes.map((sc) => {
                const shot = project.shots.find((sh) => sh.scene_id === sc.id);
                const made = sc.quality_status === "generated";
                const voiceBadge = String(sc.provider || "").includes("warm") || String(sc.provider || "").includes("female") ? "Female Voice" : "Male Voice";
                return (
                  <li key={sc.id} className="card p-4 flex flex-col justify-between gap-3">
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-[13px]">{sc.title}</span>
                        <span className="timecode text-xs text-slate shrink-0">{humanDuration(sc.duration_sec)}</span>
                      </div>
                      {made && (
                        <div className="rounded-md bg-ink overflow-hidden aspect-video mt-2.5">
                          <video
                            controls
                            preload="metadata"
                            className="w-full h-full object-contain"
                            src={`${API_BASE}/api/projects/${project.project.id}/media/renders/${sc.id}.mp4`}
                          />
                        </div>
                      )}
                      <p className="text-[13px] text-ink font-medium mt-2.5 line-clamp-3" title={sc.narration_segment}>
                        “{sc.narration_segment}”
                      </p>
                      {sc.visual_description && (
                        <p className="text-[12px] text-slate mt-1.5 line-clamp-3" title={sc.visual_description}>
                          <span className="font-semibold">Visual:</span> {sc.visual_description}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-1.5 mt-2.5">
                        <span className="chip text-[11px]">{sc.render_engine || "hyperframes"}</span>
                        <span className="chip text-[11px]">{voiceBadge}</span>
                        <span className="chip text-[11px]">xfade: {sc.transition || "smoothleft"}</span>
                        {shot && <span className="chip text-[11px]">{shot.shot_type} · {shot.camera_movement}</span>}
                      </div>
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
