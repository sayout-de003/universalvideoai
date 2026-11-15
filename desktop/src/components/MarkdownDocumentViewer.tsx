import React, { useState } from "react";
import {
  AlignLeft,
  BookOpen,
  Camera,
  Clock,
  Eye,
  Film,
  Layers,
  Mic,
  Sparkles,
  Tv,
  Volume2,
} from "lucide-react";

interface Props {
  content: string;
  filename: string;
}

type ScreenplayViewFilter = "script" | "dialogue_timeline" | "story_arc";

function fmtTimecode(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function MarkdownDocumentViewer({ content, filename }: Props) {
  const text = (content || "").trim();
  const isScreenplay = filename.toLowerCase().includes("screenplay");

  if (!text) {
    return (
      <div className="py-24 text-center text-slate hint text-sm">
        Document is empty. Click "Edit Source" to add content.
      </div>
    );
  }

  if (isScreenplay) {
    return <ScreenplayFormattedView text={text} />;
  }

  return <GeneralMarkdownView text={text} />;
}

function parseInlineFormatting(str: string): React.ReactNode[] {
  const parts = str.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={idx} className="font-semibold text-ink">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return (
        <em key={idx} className="italic text-slate">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={idx} className="font-mono text-xs px-1.5 py-0.5 rounded bg-sunken border border-rule text-amber-500">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

interface ParsedScene {
  index: number;
  title: string;
  durationSec: number;
  startSec: number;
  endSec: number;
  speaker: string;
  voiceGender: string;
  metaTags: string;
  visual: string;
  camera: string;
  lighting: string;
  narration: string;
  textCue: string;
  soundCue: string;
}

function ScreenplayFormattedView({ text }: { text: string }) {
  const [activeFilter, setActiveFilter] = useState<ScreenplayViewFilter>("script");

  const lines = text.split("\n");
  let title = "Screenplay";
  let metaFormat = "";
  let metaRuntime = "";

  const sceneChunks: string[] = [];
  let curScene = "";

  for (const line of lines) {
    if (line.match(/^#\s+SCREENPLAY\s*:/i)) {
      title = line.replace(/^#\s+SCREENPLAY\s*:/i, "").trim();
      continue;
    }
    if (line.match(/^\*Format\s*:/i)) {
      const parts = line.replace(/^\*/, "").replace(/\*$/, "").split("|");
      metaFormat = parts[0]?.replace(/^Format\s*:/i, "").trim() || "";
      metaRuntime = parts[1]?.replace(/^Runtime\s*:/i, "").trim() || "";
      continue;
    }
    if (line.match(/^##+\s*SCENE\s+\d+/i)) {
      if (curScene.trim()) {
        sceneChunks.push(curScene.trim());
      }
      curScene = line + "\n";
    } else {
      curScene += line + "\n";
    }
  }
  if (curScene.trim()) {
    sceneChunks.push(curScene.trim());
  }

  // Parse structured data and calculate exact running timecodes
  let runningTime = 0.0;
  const parsedScenes: ParsedScene[] = sceneChunks.map((chunk, idx) => {
    const chunkLines = chunk.split("\n");
    const headerLine = chunkLines[0] || "";

    let scTitle = `Scene ${idx + 1}`;
    let durSec = 4.0;
    let meta = "";

    const mHeader = headerLine.match(/^##+\s*SCENE\s+\d+\s*:\s*([^(\n—]+)(?:\(([^)]+)\))?(?:[—\-]+\s*\[(.*?)\])?/i);
    if (mHeader) {
      scTitle = mHeader[1].trim();
      const rawDur = mHeader[2]?.trim() || "4.0s";
      const durMatch = rawDur.match(/(\d+(?:\.\d+)?)/);
      if (durMatch) durSec = parseFloat(durMatch[1]);
      meta = mHeader[3]?.trim() || "";
    } else {
      scTitle = headerLine.replace(/^##+\s*/, "").trim();
    }

    const body = chunkLines.slice(1).join("\n");
    const extract = (field: string) => {
      const m = body.match(new RegExp(`\\*\\*(?:${field})\\s*:\\*\\*\\s*(.*?)(?=\\n\\*\\*[A-Z/\\s-]+\\s*:\\*\\*|\\Z)`, "is"));
      return m ? m[1].trim() : "";
    };

    const visual = extract("VISUAL");
    const camera = extract("CAMERA");
    const lighting = extract("LIGHTING");
    const narration = extract("NARRATION\\s*/?\\s*VO|NARRATION|VO");
    const textCue = extract("ON-SCREEN\\s+TEXT|TEXT");
    const soundCue = extract("SOUND");

    // Detect speaker
    const isFemale = meta.toLowerCase().includes("female") || headerLine.toLowerCase().includes("aria") || headerLine.toLowerCase().includes("female");
    const speakerName = isFemale ? "Female Co-Narrator (AriaNeural)" : "Male Lead Anchor (ChristopherNeural)";
    const gender = isFemale ? "Female" : "Male";

    const startSec = runningTime;
    const endSec = runningTime + durSec;
    runningTime += durSec;

    return {
      index: idx + 1,
      title: scTitle,
      durationSec: durSec,
      startSec,
      endSec,
      speaker: speakerName,
      voiceGender: gender,
      metaTags: meta,
      visual,
      camera,
      lighting,
      narration,
      textCue,
      soundCue,
    };
  });

  const totalRuntimeSec = runningTime || (metaRuntime ? parseFloat(metaRuntime) : 30.0);
  const totalSpokenWords = parsedScenes.reduce((acc, s) => acc + (s.narration ? s.narration.split(/\s+/).length : 0), 0);

  return (
    <div className="p-7 space-y-6 max-w-4xl mx-auto">
      {/* Film Header Banner & Story Overview */}
      <div className="rounded-xl border border-rule bg-panel p-5 space-y-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-bold text-amber-500 uppercase tracking-widest">
              <Film className="w-4 h-4" /> Production Screenplay & Story Arc
            </div>
            <h1 className="text-2xl font-black tracking-tight text-ink uppercase">
              {title}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <span className="chip chip-done text-xs font-semibold">{metaFormat || "Historical & Educational"}</span>
            <span className="chip font-mono text-xs font-bold">{fmtTimecode(totalRuntimeSec)} ({totalRuntimeSec.toFixed(1)}s)</span>
          </div>
        </div>

        {/* Narrative & Dialogue Quick Ledger */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2 text-xs border-t border-rule/60">
          <div className="p-2.5 rounded-lg bg-sunken/70">
            <span className="text-mute block text-[11px]">Total Runtime</span>
            <span className="font-bold text-ink text-sm">{totalRuntimeSec.toFixed(1)}s</span>
          </div>
          <div className="p-2.5 rounded-lg bg-sunken/70">
            <span className="text-mute block text-[11px]">Scenes Planned</span>
            <span className="font-bold text-ink text-sm">{parsedScenes.length} scenes</span>
          </div>
          <div className="p-2.5 rounded-lg bg-sunken/70">
            <span className="text-mute block text-[11px]">Spoken Words</span>
            <span className="font-bold text-ink text-sm">{totalSpokenWords} words</span>
          </div>
          <div className="p-2.5 rounded-lg bg-sunken/70">
            <span className="text-mute block text-[11px]">Voice Casting</span>
            <span className="font-bold text-ink text-sm">Dual Human Neural</span>
          </div>
        </div>

        {/* View Switcher: Script Cards vs. Time-wise Dialogue vs. Story Arc */}
        <div className="flex items-center gap-1.5 pt-1">
          <button
            onClick={() => setActiveFilter("script")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeFilter === "script" ? "bg-ink text-white shadow-sm" : "bg-sunken text-slate hover:text-ink"
            }`}
          >
            <AlignLeft className="w-3.5 h-3.5" /> Full Screenplay Script
          </button>
          <button
            onClick={() => setActiveFilter("dialogue_timeline")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeFilter === "dialogue_timeline" ? "bg-ink text-white shadow-sm" : "bg-sunken text-slate hover:text-ink"
            }`}
          >
            <Clock className="w-3.5 h-3.5 text-amber-500" /> Time-Wise Dialogue & Narration
          </button>
          <button
            onClick={() => setActiveFilter("story_arc")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeFilter === "story_arc" ? "bg-ink text-white shadow-sm" : "bg-sunken text-slate hover:text-ink"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 text-blue-400" /> Story Arc & Progression
          </button>
        </div>
      </div>

      {/* FILTER 1: FULL SCREENPLAY SCRIPT */}
      {activeFilter === "script" && (
        <div className="space-y-6">
          {parsedScenes.map((sc) => (
            <DetailedSceneCard key={sc.index} scene={sc} />
          ))}
        </div>
      )}

      {/* FILTER 2: TIME-WISE DIALOGUE & NARRATION LEDGER */}
      {activeFilter === "dialogue_timeline" && (
        <div className="space-y-4">
          <div className="card p-4 bg-sunken/50 border border-rule">
            <h3 className="font-bold text-sm text-ink flex items-center gap-2">
              <Mic className="w-4 h-4 text-amber-500" /> Time-Wise Spoken Dialogue Ledger
            </h3>
            <p className="hint text-xs mt-0.5">
              Exact timestamps showing when each narration line begins and ends, paired with the active neural voice.
            </p>
          </div>

          <div className="space-y-3">
            {parsedScenes.map((sc) => (
              <div
                key={sc.index}
                className="p-4 rounded-xl border border-rule bg-panel flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-sm"
              >
                <div className="flex items-center gap-3 shrink-0">
                  <span className="font-mono text-xs font-bold px-2.5 py-1 rounded bg-amber-500/15 text-amber-500 border border-amber-500/20">
                    {fmtTimecode(sc.startSec)} → {fmtTimecode(sc.endSec)}
                  </span>
                  <span className="text-xs text-slate font-medium">({sc.durationSec.toFixed(1)}s)</span>
                </div>

                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2 text-[11px] font-semibold text-slate uppercase tracking-wide">
                    <span>Scene {sc.index}: {sc.title}</span>
                    <span>•</span>
                    <span className="text-ink font-bold">{sc.speaker}</span>
                  </div>
                  <p className="text-[14px] text-ink font-medium leading-relaxed italic">
                    "{sc.narration ? parseInlineFormatting(sc.narration) : <span className="text-mute">Instrumental transition / visual action</span>}"
                  </p>
                </div>

                <div className="shrink-0 text-right">
                  <span className="chip text-[11px]">
                    {sc.narration ? `${sc.narration.split(/\s+/).length} words` : "0 words"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FILTER 3: STORY ARC & NARRATIVE PROGRESSION */}
      {activeFilter === "story_arc" && (
        <div className="card p-6 space-y-5">
          <div className="border-b border-rule pb-3">
            <h3 className="text-base font-bold flex items-center gap-2 text-ink">
              <Layers className="w-4 h-4 text-blue-500" /> Complete Story & Dramatic Arc
            </h3>
            <p className="hint text-xs mt-1">
              How the story develops across exposition, tension, climax, and resolution.
            </p>
          </div>

          <div className="space-y-4">
            {parsedScenes.map((sc) => (
              <div key={sc.index} className="flex gap-4 items-start">
                <div className="flex flex-col items-center">
                  <div className="w-7 h-7 rounded-full bg-panel border-2 border-amber-500 flex items-center justify-center font-bold text-xs text-ink">
                    {sc.index}
                  </div>
                  {sc.index < parsedScenes.length && <div className="w-0.5 h-16 bg-rule mt-1" />}
                </div>

                <div className="flex-1 space-y-1 pt-0.5">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-ink uppercase">
                      {sc.title}
                    </h4>
                    <span className="timecode text-xs">
                      {fmtTimecode(sc.startSec)} ({sc.durationSec.toFixed(1)}s)
                    </span>
                  </div>
                  <p className="text-xs text-slate">
                    <b>Visual Action:</b> {sc.visual || "Establishing animated sequence."}
                  </p>
                  <p className="text-xs text-ink/80 italic">
                    <b>Spoken Core:</b> "{sc.narration}"
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DetailedSceneCard({ scene }: { scene: ParsedScene }) {
  return (
    <div className="rounded-xl border border-rule bg-panel overflow-hidden shadow-sm hover:shadow transition">
      {/* Scene Header with Timecode */}
      <div className="px-5 py-3.5 bg-sunken/80 border-b border-rule flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-md bg-amber-500/15 text-amber-500 font-bold text-xs flex items-center justify-center shrink-0">
            {scene.index}
          </span>
          <span className="font-bold text-sm tracking-wide text-ink uppercase">
            {scene.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Exact Timecode Range */}
          <span className="font-mono text-xs px-2.5 py-1 rounded bg-panel border border-rule font-bold text-amber-500">
            {fmtTimecode(scene.startSec)} → {fmtTimecode(scene.endSec)} ({scene.durationSec.toFixed(1)}s)
          </span>
          {scene.metaTags && (
            <span className="text-[11px] font-mono text-slate px-2 py-0.5 rounded bg-panel border border-rule">
              {scene.metaTags}
            </span>
          )}
        </div>
      </div>

      <div className="p-5 space-y-4 text-xs leading-relaxed">
        {/* Visual Direction Block */}
        {scene.visual && (
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate">
              <Eye className="w-3.5 h-3.5 text-blue-400" /> Story Context & Visual Action
            </div>
            <p className="text-[13px] text-slate pl-5 border-l-2 border-blue-400/50 py-0.5">
              {parseInlineFormatting(scene.visual)}
            </p>
          </div>
        )}

        {/* Camera & Lighting Telemetry Pills */}
        {(scene.camera || scene.lighting) && (
          <div className="flex flex-wrap items-center gap-2 pt-1 pl-5">
            {scene.camera && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-md bg-sunken border border-rule text-slate">
                <Camera className="w-3 h-3 text-slate" /> Camera: <b className="text-ink font-semibold">{scene.camera}</b>
              </span>
            )}
            {scene.lighting && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-md bg-sunken border border-rule text-slate">
                <Sparkles className="w-3 h-3 text-amber-400" /> Lighting: <b className="text-ink font-semibold">{scene.lighting}</b>
              </span>
            )}
          </div>
        )}

        {/* Spoken Dialogue Callout */}
        {scene.narration && (
          <div className="p-4 rounded-xl bg-sunken/60 border border-rule border-l-4 border-l-amber-500 space-y-1.5 mt-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[11px] font-bold text-amber-500 uppercase tracking-wider">
                <Mic className="w-3.5 h-3.5" /> Spoken Dialogue / Voice-Over
              </div>
              <span className="chip text-[10px] uppercase font-mono">{scene.speaker}</span>
            </div>
            <p className="text-[14px] text-ink font-medium leading-relaxed italic pl-1">
              "{parseInlineFormatting(scene.narration)}"
            </p>
          </div>
        )}

        {/* On-Screen Text & Sound cues */}
        {(scene.textCue || scene.soundCue) && (
          <div className="flex flex-wrap items-center gap-3 pt-2 text-[11px] text-slate border-t border-rule/50">
            {scene.textCue && (
              <span className="inline-flex items-center gap-1">
                <Tv className="w-3.5 h-3.5 text-slate" /> On-Screen: <b className="text-ink font-mono">{scene.textCue}</b>
              </span>
            )}
            {scene.soundCue && (
              <span className="inline-flex items-center gap-1">
                <Volume2 className="w-3.5 h-3.5 text-slate" /> Audio: <b className="text-ink font-mono">{scene.soundCue}</b>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function GeneralMarkdownView({ text }: { text: string }) {
  const lines = text.split("\n");

  return (
    <div className="p-8 space-y-4 max-w-4xl mx-auto text-sm leading-relaxed text-slate">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-2" />;
        }
        if (trimmed.startsWith("# ")) {
          return (
            <h1 key={idx} className="text-2xl font-extrabold text-ink tracking-tight pt-4 pb-1 border-b border-rule">
              {parseInlineFormatting(trimmed.slice(2))}
            </h1>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <h2 key={idx} className="text-lg font-bold text-ink tracking-tight pt-3 pb-0.5">
              {parseInlineFormatting(trimmed.slice(3))}
            </h2>
          );
        }
        if (trimmed.startsWith("### ")) {
          return (
            <h3 key={idx} className="text-sm font-bold text-ink pt-2">
              {parseInlineFormatting(trimmed.slice(4))}
            </h3>
          );
        }
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
          return (
            <li key={idx} className="ml-5 list-disc text-[13px] text-slate">
              {parseInlineFormatting(trimmed.slice(2))}
            </li>
          );
        }
        if (trimmed.startsWith("> ")) {
          return (
            <blockquote key={idx} className="pl-4 border-l-2 border-amber-500 text-slate italic bg-sunken/40 py-1.5 px-3 rounded-r text-[13px]">
              {parseInlineFormatting(trimmed.slice(2))}
            </blockquote>
          );
        }
        return (
          <p key={idx} className="text-[13px] text-slate leading-relaxed">
            {parseInlineFormatting(trimmed)}
          </p>
        );
      })}
    </div>
  );
}
