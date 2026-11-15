import { useEffect, useMemo, useRef, useState } from "react";
import { Check, CheckCircle2, ChevronDown, ChevronRight, Download, Pause, Play, RotateCcw, Sparkles, XCircle } from "lucide-react";
import { API_BASE } from "../api/client";
import { PIPELINE, generatedSeconds, isIdle, humanDuration, progressOfDetail, timecode } from "../lib/progress";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  liveEvents: Array<Record<string, unknown>>;
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onGoToScript: () => void;
}

function describeEvent(ev: Record<string, unknown>): string | null {
  switch (ev.type) {
    case "production_started":
      return `[Production Orchestrator] Production started across ${ev.scenes} scenes.`;
    case "stage_progress":
      return `[Stage: ${ev.stage}] ${ev.message}`;
    case "ai_decision":
      return `[AI Decision · ${ev.parameter}] Selected '${ev.selected}' (${ev.chosen_by === "user" ? "User choice" : "AI Auto-Decided"}) — Why: ${ev.reasoning}`;
    case "scene_started":
      return `[Scene ${ev.index}/${ev.total} Started] ${ev.title} — Engine: ${ev.engine} | Voice: ${ev.voice} | Transition: ${ev.transition}`;
    case "tts_synthesized":
      return `[Voice Studio · Scene ${ev.index}] Synthesized ${ev.voice} (${ev.duration_sec}s via ${ev.provider || "edge_neural_tts"}).`;
    case "scene_generated":
      return `[Renderer · Scene ${ev.index}/${ev.total}] Finished ${ev.title || ""} (${ev.duration_sec || ""}s via ${ev.engine_used || "hyperframes"}).`;
    case "scene_regenerated":
      return "[Video Editor Agent] Regenerated scene in isolation while preserving timeline edits.";
    case "production_paused":
      return "[Production Orchestrator] Production paused.";
    case "production_completed":
      return ev.status === "completed"
        ? "[Quality Assurance Agent] Master video finished and passed automated verification."
        : "[Quality Assurance Agent] Video finished, but quality check flagged issues.";
    case "agent_message":
      return `[${ev.agent}] ${ev.content}`;
    default:
      return null;
  }
}

const fmtTime = (iso?: string) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "");

interface DecisionEntry {
  key: string;
  label: string;
  selected: string;
  chosen_by: string;
  reasoning: string;
}

function extractAiDecisions(project: ProjectDetail): DecisionEntry[] {
  const meta = (project.project.metadata || {}) as Record<string, unknown>;
  const rawDec = (meta.ai_decisions || {}) as Record<string, Record<string, unknown>>;
  const labels: Record<string, string> = {
    video_format: "Video Format & Structure",
    target_duration_sec: "Runtime & Pacing",
    render_engine: "Visual & Animation Engine",
    voice_casting: "Human Voice Casting",
    transitions_and_audio: "Transitions & Sound Design",
  };
  const entries: DecisionEntry[] = [];
  for (const [k, v] of Object.entries(rawDec)) {
    if (v && typeof v === "object") {
      entries.push({
        key: k,
        label: labels[k] || k.replace(/_/g, " "),
        selected: String(v.selected || ""),
        chosen_by: String(v.chosen_by || "ai_director"),
        reasoning: String(v.reasoning || ""),
      });
    }
  }
  if (entries.length > 0) return entries;

  // Fallback synthesized reasoning for older projects
  return [
    {
      key: "video_format",
      label: "Video Format & Structure",
      selected: `${project.project.category} (${project.project.pipeline_name})`,
      chosen_by: "ai_director",
      reasoning: `AI Director classified prompt into '${project.project.category}' pipeline '${project.project.pipeline_name}' based on topic and narrative structure.`,
    },
    {
      key: "target_duration_sec",
      label: "Runtime & Pacing",
      selected: `${project.project.target_duration_sec}s (${project.scenes.length} scenes)`,
      chosen_by: "ai_director",
      reasoning: `Calculated ${project.scenes.length} scenes (~${Math.round(project.project.target_duration_sec / Math.max(1, project.scenes.length))}s/scene) to match spoken narration budget.`,
    },
    {
      key: "render_engine",
      label: "Visual & Animation Engine",
      selected: "Hybrid Pixar 2D/3D (HyperFrames) + Remotion Motion Graphics",
      chosen_by: "ai_director",
      reasoning: "Combined 2D/3D articulated character/world Canvas animation with Remotion kinetic telemetry cards and FFmpeg xfade transitions.",
    },
    {
      key: "voice_casting",
      label: "Human Voice Casting",
      selected: "Dual Neural Voices (Male ChristopherNeural + Female AriaNeural)",
      chosen_by: "ai_director",
      reasoning: "Alternated real human Male and Female neural voices across scenes for dynamic documentary/narrative contrast.",
    },
  ];
}

export function BacklotMonitorView({ project, liveEvents, onRun, onPause, onResume, onGoToScript }: Props) {
  const pr = progressOfDetail(project);
  const { done, total } = generatedSeconds(project);
  const status = project.project.status;
  const running = status === "running";
  const finished = status === "completed" || status === "qa_failed";
  const latestQa = project.qa_reports[0];
  const [showSteps, setShowSteps] = useState(false);
  const [showDecisions, setShowDecisions] = useState(true);
  const [videoError, setVideoError] = useState(false);
  const decisions = useMemo(() => extractAiDecisions(project), [project]);

  // Estimate time left from how fast scenes finished since this page started watching the run.
  const base = useRef<{ t: number; n: number } | null>(null);
  useEffect(() => {
    if (!running) { base.current = null; return; }
    if (!base.current) base.current = { t: Date.now(), n: pr.scenesDone };
  }, [running, pr.scenesDone]);
  const b = base.current;
  const inScenes = pr.stepIndex <= 1;
  const etaSec = running && inScenes && b && pr.scenesDone > b.n
    ? ((Date.now() - b.t) / 1000 / (pr.scenesDone - b.n)) * (pr.scenesTotal - pr.scenesDone) : null;

  const currentSceneId = running && inScenes ? project.scenes.find((s) => s.quality_status !== "generated")?.id : undefined;

  const feed = useMemo(() => {
    const liveItems = liveEvents
      .map((ev) => ({ text: describeEvent(ev), time: String(ev.timestamp || "") }))
      .filter((e): e is { text: string; time: string } => Boolean(e.text));
    const msgItems = [...project.messages]
      .reverse()
      .map((m) => ({ text: `[${m.agent_name}] ${m.content}`, time: m.created_at }));
    const seen = new Set<string>();
    const combined: Array<{ text: string; time: string }> = [];
    for (const item of [...liveItems, ...msgItems]) {
      if (!seen.has(item.text)) {
        seen.add(item.text);
        combined.push(item);
      }
    }
    return combined.slice(0, 60);
  }, [liveEvents, project.messages]);

  const accent = pr.tone === "done" ? "bg-done" : pr.tone === "hold" ? "bg-hold" : "bg-live";

  return (
    <div className="space-y-6">
      <section className="card p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <div className="text-xl font-bold">{pr.headline}</div>
            <div className="hint mt-1">
              {running && etaSec !== null ? `About ${humanDuration(etaSec) || "a few seconds"} left for the scenes.` : running ? "Working out how long this will take…" : finished ? "Review the result below, then edit or export." : status === "paused" ? "Resume to continue where it stopped." : "Approve the script, then start production."}
            </div>
          </div>
          <div className="text-right">
            <div className="timecode text-4xl font-semibold leading-none">{timecode(done)}</div>
            <div className="hint mt-1.5">of {timecode(total)} generated · {pr.percent}%</div>
          </div>
        </div>

        <div className="h-2.5 rounded-full bg-rule mt-6 overflow-hidden" role="progressbar" aria-valuenow={pr.percent} aria-valuemin={0} aria-valuemax={100} aria-label="Production progress">
          <div className={`h-full rounded-full transition-all duration-700 ${accent}`} style={{ width: `${pr.percent}%` }} />
        </div>

        <ol className="grid grid-cols-6 gap-2 mt-5" aria-label="Production stages">
          {PIPELINE.map((s, i) => {
            const complete = finished || i < pr.stepIndex || (isIdle(status) && i === 0);
            const current = !finished && i === pr.stepIndex && !isIdle(status);
            return (
              <li key={s.id} className="min-w-0">
                <div className={`h-1 rounded-full ${complete ? "bg-done" : current ? (running ? "bg-live tally" : "bg-hold") : "bg-rule"}`} />
                <div className={`mt-1.5 text-xs flex items-center gap-1 ${current ? "font-bold text-ink" : complete ? "text-done font-semibold" : "text-mute"}`}>
                  {complete && <Check className="w-3 h-3 shrink-0" />}<span className="truncate">{s.label}</span>
                </div>
                {current && s.id === "scenes" && pr.scenesTotal > 0 && <div className="timecode text-xs text-slate">{pr.scenesDone}/{pr.scenesTotal}</div>}
              </li>
            );
          })}
        </ol>

        <div className="flex flex-wrap items-center gap-2 mt-6 pt-5 border-t border-rule">
          {running && <button onClick={onPause} className="btn btn-quiet"><Pause className="w-4 h-4" /> Pause</button>}
          {status === "paused" && <button onClick={onResume} className="btn btn-live"><RotateCcw className="w-4 h-4" /> Resume</button>}
          {isIdle(status) && <button onClick={onRun} className="btn btn-live"><Play className="w-4 h-4" /> Make the video</button>}
          {finished && <button onClick={onRun} className="btn btn-quiet"><RotateCcw className="w-4 h-4" /> Make it again</button>}
          {isIdle(status) && <button onClick={onGoToScript} className="btn btn-ghost">Review the script first</button>}
        </div>
      </section>

      {project.scenes.length > 0 && (
        <section className="card p-6">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="font-bold">Scenes</h2>
            <div className="hint flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-3 rounded-sm bg-done" /> Made</span>
              <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-3 rounded-sm bg-live tally" /> Making now</span>
              <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-3 rounded-sm border border-mute" /> Waiting</span>
            </div>
          </div>
          <div className="space-y-4">
            {project.chapters.map((ch) => {
              const scenes = project.scenes.filter((s) => s.chapter_id === ch.id);
              const made = scenes.filter((s) => s.quality_status === "generated").length;
              return (
                <div key={ch.id}>
                  <div className="flex justify-between text-[13px] mb-1.5">
                    <span className="font-semibold truncate">{ch.title}</span>
                    <span className="timecode text-slate shrink-0 ml-3">{made}/{scenes.length}</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {scenes.map((s) => {
                      const isDone = s.quality_status === "generated";
                      const isNow = s.id === currentSceneId;
                      return (
                        <div key={s.id} title={`${s.title} · ${timecode(s.duration_sec)}${isDone ? " · made" : isNow ? " · making now" : " · waiting"}`}
                          className={`h-7 rounded-[3px] ${isDone ? "bg-done" : isNow ? "bg-live tally" : "border border-rule bg-sunken"}`}
                          style={{ width: `${Math.max(14, Math.min(64, s.duration_sec * 1.4))}px` }} />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {finished && (
        <section className="card p-6 space-y-4">
          <h2 className="font-bold">Result</h2>
          <div className="rounded-lg bg-ink overflow-hidden aspect-video max-h-[420px] mx-auto relative flex items-center justify-center">
            {videoError ? (
              <div className="text-center p-6 text-white space-y-3">
                <p className="text-sm text-slate-300">Video preview could not be streamed by browser.</p>
                <a
                  href={`${API_BASE}/api/projects/${project.project.id}/media/exports/final_production.mp4?download=true`}
                  download="final_production.mp4"
                  className="btn btn-primary btn-sm inline-flex items-center gap-2"
                >
                  <Download className="w-4 h-4" /> Download Video Directly
                </a>
              </div>
            ) : (
              <video
                controls
                preload="metadata"
                className="w-full h-full object-contain"
                src={`${API_BASE}/api/projects/${project.project.id}/media/exports/final_production.mp4`}
                onError={() => setVideoError(true)}
              />
            )}
          </div>
          {latestQa && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="font-semibold text-[13px]">Quality check</div>
                <span className={`chip ${latestQa.passed ? "chip-done" : "chip-hold"}`}>{latestQa.summary}</span>
              </div>
              <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {latestQa.checks.map((c) => (
                  <li key={c.name} className="card-sunken px-3 py-2 flex items-start gap-2 text-[13px]">
                    {c.passed ? <CheckCircle2 className="w-4 h-4 text-done shrink-0 mt-0.5" /> : <XCircle className="w-4 h-4 text-live shrink-0 mt-0.5" />}
                    <div><div className="font-semibold">{c.name}</div><div className="hint">{c.details}</div></div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <section className="card p-6">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-ink" />
            <h2 className="font-bold">AI Director Decisions & Reasoning</h2>
          </div>
          <button onClick={() => setShowDecisions((v) => !v)} className="btn btn-ghost text-xs">
            {showDecisions ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />} {showDecisions ? "Hide" : "Show"}
          </button>
        </div>
        {showDecisions && (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {decisions.map((d) => {
              const isUser = d.chosen_by === "user";
              return (
                <li key={d.key} className="card-sunken p-3.5 text-[13px] space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-ink">{d.label}</span>
                    <span className={`chip text-[11px] ${isUser ? "chip-done" : "chip-hold"}`}>
                      {isUser ? "Chosen by You" : "AI Decided"}
                    </span>
                  </div>
                  <div className="font-medium text-ink">{d.selected}</div>
                  <p className="text-xs text-slate leading-relaxed">
                    <strong className="text-ink">Why:</strong> {d.reasoning}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="card p-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold">Live Log Stream & Agent Reasoning</h2>
          <span className="hint">{feed.length} events streamed</span>
        </div>
        {feed.length === 0 ? <div className="hint">Updates and AI reasoning show up here in real time.</div> : (
          <ul className="divide-y divide-rule max-h-96 overflow-y-auto font-mono text-[12.5px]" aria-live="polite">
            {feed.map((e, i) => (
              <li key={i} className="py-2 flex gap-3">
                <span className="timecode text-xs text-mute w-20 shrink-0 pt-0.5">{fmtTime(e.time)}</span>
                <span className="leading-relaxed break-words">{e.text}</span>
              </li>
            ))}
          </ul>
        )}
        {project.checkpoints.length > 0 && (
          <div className="mt-4 pt-3 border-t border-rule">
            <button onClick={() => setShowSteps((v) => !v)} className="btn btn-ghost -ml-2" aria-expanded={showSteps}>
              {showSteps ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />} Step history ({project.checkpoints.length})
            </button>
            {showSteps && (
              <ul className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-1.5 max-h-60 overflow-y-auto">
                {project.checkpoints.map((ck) => (
                  <li key={ck.id} className="card-sunken px-3 py-1.5 flex justify-between text-[13px]">
                    <span className="capitalize">{ck.stage.replace(/_/g, " ")}</span><span className="hint">{ck.status}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
