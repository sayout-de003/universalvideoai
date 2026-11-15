import type { ProjectDetail, ProjectSummary } from "../types/studio";

/** Pipeline steps shown to the user, mapped onto the backend's ProductionStage values. */
export const PIPELINE: Array<{ id: string; label: string; stages: string[] }> = [
  { id: "plan", label: "Plan", stages: ["idea", "research", "creative_proposal", "script", "storyboard", "asset_plan", "audio_plan"] },
  { id: "scenes", label: "Scenes", stages: ["generation", "review", "editing"] },
  { id: "mix", label: "Audio mix", stages: ["audio_sync"] },
  { id: "render", label: "Render", stages: ["rendering"] },
  { id: "qa", label: "Quality check", stages: ["quality_assurance"] },
  { id: "done", label: "Delivered", stages: ["delivery"] },
];

export interface Progress {
  percent: number;
  stepIndex: number;
  scenesDone: number;
  scenesTotal: number;
  headline: string;
  tone: "idle" | "live" | "done" | "hold";
  label: string;
}

type Statusish = Pick<ProjectSummary, "status" | "current_stage">;

/** Not started yet: "planned", or an intake status such as "brief_confirmed". */
export const isIdle = (status: string) => !["running", "paused", "completed", "qa_failed"].includes(status);

export function stepIndexOf(stage: string): number {
  const i = PIPELINE.findIndex((s) => s.stages.includes(stage));
  return i < 0 ? 0 : i;
}

export function computeProgress(p: Statusish, scenesDone: number, scenesTotal: number): Progress {
  const step = stepIndexOf(p.current_stage);
  const frac = scenesTotal > 0 ? Math.min(1, scenesDone / scenesTotal) : 0;
  let percent = 0;
  if (p.status === "completed" || p.status === "qa_failed") percent = 100;
  else if (isIdle(p.status)) percent = scenesTotal > 0 ? 8 : 3;
  else if (step <= 1) percent = Math.round(10 + 70 * frac);
  else percent = [0, 0, 84, 90, 96, 99][step];

  const n = Math.min(scenesTotal, scenesDone + 1);
  let headline = "Ready to produce";
  let tone: Progress["tone"] = "idle";
  let label = "Ready";
  if (p.status === "completed") { headline = "Your video is finished"; tone = "done"; label = "Finished"; }
  else if (p.status === "qa_failed") { headline = "Finished, but the quality check found problems"; tone = "hold"; label = "Needs review"; }
  else if (p.status === "paused") { headline = `Paused after ${scenesDone} of ${scenesTotal} scenes`; tone = "hold"; label = "Paused"; }
  else if (p.status === "running") {
    tone = "live"; label = "Producing";
    headline = step <= 1 ? `Making scene ${n} of ${scenesTotal}`
      : step === 2 ? "Mixing voice, music and sound effects"
      : step === 3 ? "Joining scenes into the final video"
      : step === 4 ? "Checking quality" : "Wrapping up";
  }
  return { percent, stepIndex: step, scenesDone, scenesTotal, headline, tone, label };
}

export function progressOfDetail(d: ProjectDetail): Progress {
  const done = d.scenes.filter((s) => s.quality_status === "generated").length;
  return computeProgress(d.project, done, d.scenes.length);
}

export function progressOfSummary(p: ProjectSummary): Progress {
  return computeProgress(p, p.scenes_done ?? 0, p.scenes_total ?? 0);
}

/** 83 -> "1:23", 3725 -> "1:02:05" */
export function timecode(totalSec: number): string {
  const s = Math.max(0, Math.round(totalSec));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(sec).padStart(2, "0")}`;
}

export function generatedSeconds(d: ProjectDetail): { done: number; total: number } {
  let done = 0, total = 0;
  for (const s of d.scenes) {
    total += s.duration_sec;
    if (s.quality_status === "generated") done += s.duration_sec;
  }
  return { done, total: total || d.project.target_duration_sec };
}

export function humanDuration(sec: number): string {
  if (!isFinite(sec) || sec <= 0) return "";
  if (sec < 90) return `${Math.round(sec)} sec`;
  const m = Math.round(sec / 60);
  if (m < 90) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}
