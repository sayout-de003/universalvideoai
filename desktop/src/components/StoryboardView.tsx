import { useState } from "react";
import { Check, Link2, Palette, RefreshCw } from "lucide-react";
import { API_BASE, studioClient } from "../api/client";
import { humanDuration } from "../lib/progress";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onRegenerateScene: (sceneId: string, visualStyle?: string) => Promise<void>;
  onRefresh?: () => Promise<void>;
}

const STYLE_OPTIONS = [
  { id: "pixel_art", label: "Pixel Art" },
  { id: "2d_illustrated", label: "2D Illustrated" },
  { id: "3d_stylized", label: "3D Stylized" },
  { id: "hand_drawn_storybook", label: "Hand-Drawn Storybook" },
];

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

export function StoryboardView({ project, onRegenerateScene, onRefresh }: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [sceneStyleOverrides, setSceneStyleOverrides] = useState<Record<string, string>>({});
  const [globalStyleBusy, setGlobalStyleBusy] = useState(false);

  const regenerate = async (id: string) => {
    setBusyId(id);
    try {
      await onRegenerateScene(id, sceneStyleOverrides[id]);
    } finally {
      setBusyId(null);
    }
  };

  const toggleSceneApproval = async (sceneId: string, currentApproved: number) => {
    setBusyId(sceneId);
    try {
      await studioClient.approveScene(project.project.id, sceneId, currentApproved ? false : true);
      if (onRefresh) await onRefresh();
    } finally {
      setBusyId(null);
    }
  };

  const handleGlobalStyleChange = async (newStyle: string) => {
    setGlobalStyleBusy(true);
    try {
      await studioClient.updateVisualStyle(project.project.id, newStyle);
      if (onRefresh) await onRefresh();
    } finally {
      setGlobalStyleBusy(false);
    }
  };

  if (project.scenes.length === 0) {
    return <div className="card p-10 text-center"><div className="font-bold text-lg">No scenes yet</div><p className="text-slate mt-1">Scenes appear here once the script is written.</p></div>;
  }
  const refs = project.reference_assets || [];

  return (
    <div className="space-y-8">
      <section className="card p-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-bold flex items-center gap-2">
            <Palette className="w-4 h-4" /> Visual Direction & Style Profile
          </div>
          <p className="hint">Switch the production visual style globally or override individual scenes below before regenerating.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {STYLE_OPTIONS.map((st) => {
            const active = (project.project.visual_style || "2d_illustrated") === st.id;
            return (
              <button
                key={st.id}
                type="button"
                disabled={globalStyleBusy}
                onClick={() => handleGlobalStyleChange(st.id)}
                className={`btn text-xs py-1.5 px-3 ${active ? "btn-primary" : "btn-quiet"}`}
              >
                {st.label}
              </button>
            );
          })}
        </div>
      </section>

      {refs.length > 0 && (
        <section>
          <h2 className="font-bold mb-3 flex items-center gap-2"><Link2 className="w-4 h-4" /> Reference Intelligence ({refs.length})</h2>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {refs.map((r) => (
              <li key={r.id} className="card p-3.5 text-[12.5px] space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold truncate">{r.source_url || r.file_path.split("/").pop()}</span>
                  <span className="chip text-[11px]">{r.source_type || r.asset_type}</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  <span className="chip text-[10.5px]">Access: {r.access_status || "analyzed"}</span>
                  {(r.roles || [r.intended_role]).map((role) => (
                    <span key={role} className="chip text-[10.5px]">{role}</span>
                  ))}
                </div>
                {r.user_notes && <div className="text-slate italic">“{r.user_notes}”</div>}
                {Array.isArray(r.limitations) && r.limitations.length > 0 && (
                  <div className="text-[11.5px] text-slate bg-sunken rounded px-2.5 py-1.5">
                    <span className="font-semibold">Access note:</span> {r.limitations[0]}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
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
                        <span className="chip text-[11px]">{sc.visual_style || project.project.visual_style || "2d_illustrated"}</span>
                        <span className="chip text-[11px]">{voiceBadge}</span>
                        <span className="chip text-[11px]">xfade: {sc.transition || "smoothleft"}</span>
                        {shot && <span className="chip text-[11px]">{shot.shot_type} · {shot.camera_movement}</span>}
                      </div>
                    </div>
                    <div className="space-y-2 pt-3 border-t border-rule">
                      <div className="flex items-center justify-between gap-2">
                        <select
                          aria-label={`Style override for ${sc.title}`}
                          className="field text-xs py-1 px-2"
                          value={sceneStyleOverrides[sc.id] || sc.visual_style || project.project.visual_style || "2d_illustrated"}
                          onChange={(e) => setSceneStyleOverrides((prev) => ({ ...prev, [sc.id]: e.target.value }))}
                        >
                          {STYLE_OPTIONS.map((st) => <option key={st.id} value={st.id}>{st.label}</option>)}
                        </select>
                        <button
                          type="button"
                          disabled={busyId !== null}
                          onClick={() => toggleSceneApproval(sc.id, sc.approved)}
                          className={`btn text-xs py-1 px-2.5 ${sc.approved ? "btn-primary" : "btn-quiet"}`}
                        >
                          <Check className="w-3 h-3" /> {sc.approved ? "Approved" : "Approve"}
                        </button>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className={`chip ${made ? "chip-done" : ""}`}>{made ? "Made" : "Not made yet"}</span>
                        <button onClick={() => regenerate(sc.id)} disabled={busyId !== null} className="btn btn-ghost text-[13px]">
                          <RefreshCw className={`w-3.5 h-3.5 ${busyId === sc.id ? "animate-spin" : ""}`} /> {busyId === sc.id ? "Redoing…" : "Redo this scene"}
                        </button>
                      </div>
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
