import { useState } from "react";
import { Check, Copy, FileCode, Film, Layers, Play, RefreshCw, Sparkles, Wand2 } from "lucide-react";
import { studioClient } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onRefresh: () => Promise<void>;
}

type HypitMode = "cloner" | "author" | "variants";

const SAMPLE_SVML = `[Role: Lead Anchor (male)]
[Role: Co-Host (female)]

[Segment: The Critical Threshold]
Lead Anchor: Most people believe the system operates in equilibrium. @{reveal} But deep inside the reactor core, an unprecedented phase shift is accelerating.

[Segment: The Pivot Beat]
Co-Host: When engineers adjusted the secondary flux coil, @{zoom} power output tripled within milliseconds.

[Segment: The Resolution]
Lead Anchor: The telemetry confirmed what theory predicted: stability had finally been reached.`;

export function HypitStudioView({ project, onRefresh }: Props) {
  const [mode, setMode] = useState<HypitMode>("cloner");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  // 1. Cloner state
  const [refUrl, setRefUrl] = useState("https://www.youtube.com/watch?v=dQw4w9WgXcQ");
  const [clonePrompt, setClonePrompt] = useState(project.project.prompt || "Top 5 Breakthrough Discoveries in Quantum Computing");
  const [cloneDuration, setCloneDuration] = useState("30");
  const [cloneResult, setCloneResult] = useState<Record<string, unknown> | null>(null);

  // 2. Author state
  const [scriptText, setScriptText] = useState(SAMPLE_SVML);
  const [authorResult, setAuthorResult] = useState<Record<string, unknown> | null>(null);

  // 3. Variant state
  const [variantType, setVariantType] = useState("voice_swap");
  const [variantVoice, setVariantVoice] = useState("narrator_warm");
  const [variantLang, setVariantLang] = useState("es");
  const [variantAspect, setVariantAspect] = useState("9:16");
  const [variantResult, setVariantResult] = useState<Record<string, unknown> | null>(null);

  const handleRunCloner = async () => {
    if (!refUrl.trim() || !clonePrompt.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await studioClient.hypitCloneReference(refUrl.trim(), clonePrompt.trim(), Number(cloneDuration) || 30);
      setCloneResult(res);
      setMsg({ kind: "ok", text: "Successfully deconstructed reference video and generated target blueprint." });
    } catch (err) {
      setMsg({ kind: "error", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };

  const handleRunAuthor = async () => {
    if (!scriptText.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await studioClient.hypitAuthor(scriptText.trim());
      setAuthorResult(res);
      setMsg({ kind: "ok", text: `Parsed ${(res.segments as unknown[])?.length || 0} segments with ${(res.moments as unknown[])?.length || 0} semantic moments.` });
    } catch (err) {
      setMsg({ kind: "error", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };

  const handleRunVariants = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const variantPayload = [
        {
          name: `${project.project.title} (${variantType === "voice_swap" ? "Female Voice" : variantType === "aspect_ratio" ? "9:16 Vertical" : "Localized Spanish"})`,
          type: variantType,
          voice_id: variantType === "voice_swap" ? variantVoice : undefined,
          language: variantType === "language_swap" ? variantLang : undefined,
          aspect_ratio: variantType === "aspect_ratio" ? variantAspect : undefined,
        },
      ];
      const res = await studioClient.hypitVariants(project.project.id, variantPayload);
      setVariantResult(res);
      setMsg({ kind: "ok", text: "Successfully spawned zero-waste production variant using cached scene renders." });
    } catch (err) {
      setMsg({ kind: "error", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Top Header Card */}
      <div className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 bg-amber-500/10 text-amber-500 rounded-md">
                <Sparkles className="w-5 h-5" />
              </span>
              <h2 className="text-lg font-bold">Hypit Studio Engine</h2>
              <span className="chip chip-done text-xs">Clean-Room Integrated</span>
            </div>
            <p className="hint mt-1 max-w-2xl">
              Deterministic semantic video authoring, reference-to-production cloning, and zero-waste multi-variant generation.
            </p>
          </div>
          <div className="flex items-center gap-2 bg-sunken p-1 rounded-lg border border-rule">
            <button
              onClick={() => setMode("cloner")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md flex items-center gap-1.5 transition ${mode === "cloner" ? "bg-panel text-ink shadow-sm" : "text-slate hover:text-ink"}`}
            >
              <Copy className="w-3.5 h-3.5" /> Reference Cloner
            </button>
            <button
              onClick={() => setMode("author")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md flex items-center gap-1.5 transition ${mode === "author" ? "bg-panel text-ink shadow-sm" : "text-slate hover:text-ink"}`}
            >
              <FileCode className="w-3.5 h-3.5" /> Semantic Authoring (SVML)
            </button>
            <button
              onClick={() => setMode("variants")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md flex items-center gap-1.5 transition ${mode === "variants" ? "bg-panel text-ink shadow-sm" : "text-slate hover:text-ink"}`}
            >
              <Layers className="w-3.5 h-3.5" /> Variant Engine
            </button>
          </div>
        </div>
      </div>

      {msg && (
        <div
          role={msg.kind === "error" ? "alert" : "status"}
          className={`px-4 py-3 rounded-lg text-sm border flex items-center gap-2 ${
            msg.kind === "error" ? "bg-live-soft border-live/40 text-live" : "bg-done-soft border-done/30 text-done"
          }`}
        >
          {msg.kind === "ok" ? <Check className="w-4 h-4 shrink-0" /> : <RefreshCw className="w-4 h-4 shrink-0" />}
          {msg.text}
        </div>
      )}

      {/* Mode 1: Reference Cloner */}
      {mode === "cloner" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <div className="card p-5 space-y-4">
            <h3 className="font-bold flex items-center gap-2 text-base">
              <Film className="w-4 h-4 text-amber-500" /> Reference Video Deconstruction
            </h3>
            <p className="hint text-xs">
              Provide any public reference video URL or media path. The engine extracts hook pacing, cut density, camera movement cadence, and caption typography, creating a targeted production blueprint.
            </p>
            <div className="space-y-3 pt-2">
              <div>
                <label className="label">Reference Video URL or File Path</label>
                <input
                  type="text"
                  value={refUrl}
                  onChange={(e) => setRefUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=... or local mp4 path"
                  className="w-full mt-1 px-3 py-2 text-sm rounded-lg border border-rule bg-panel focus:outline-none focus:ring-1 focus:ring-ink font-mono"
                />
              </div>
              <div>
                <label className="label">Target Topic / New Prompt</label>
                <textarea
                  rows={3}
                  value={clonePrompt}
                  onChange={(e) => setClonePrompt(e.target.value)}
                  placeholder="Describe the new video to produce using this reference's pacing and hook mechanics..."
                  className="w-full mt-1 px-3 py-2 text-sm rounded-lg border border-rule bg-panel focus:outline-none focus:ring-1 focus:ring-ink"
                />
              </div>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="label">Target Duration (seconds)</label>
                  <input
                    type="number"
                    value={cloneDuration}
                    onChange={(e) => setCloneDuration(e.target.value)}
                    className="w-full mt-1 px-3 py-1.5 text-sm rounded-lg border border-rule bg-panel"
                  />
                </div>
                <div className="pt-5">
                  <button
                    disabled={busy || !refUrl.trim() || !clonePrompt.trim()}
                    onClick={handleRunCloner}
                    className="btn btn-primary"
                  >
                    {busy ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />} Deconstruct & Clone
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="card p-5 space-y-4">
            <h3 className="font-bold text-base">Target Production Blueprint</h3>
            {cloneResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded bg-sunken border border-rule">
                    <span className="text-mute block">Detected Archetype</span>
                    <span className="font-bold text-ink">{String((cloneResult.target_blueprint as Record<string, unknown>)?.style_archetype || "explainer")}</span>
                  </div>
                  <div className="p-2.5 rounded bg-sunken border border-rule">
                    <span className="text-mute block">Hook Duration</span>
                    <span className="font-bold text-ink">{String((cloneResult.reference_metrics as Record<string, unknown>)?.hook_duration_sec || "2.8")}s</span>
                  </div>
                </div>
                <div className="max-h-[360px] overflow-y-auto space-y-2 pr-1">
                  {((cloneResult.target_blueprint as Record<string, unknown>)?.scenes as Array<Record<string, unknown>>)?.map((sc, i) => (
                    <div key={i} className="p-3 rounded-lg border border-rule bg-panel text-xs space-y-1">
                      <div className="flex items-center justify-between font-bold">
                        <span>{i + 1}. {String(sc.title)}</span>
                        <span className="chip">{Number(sc.target_duration_sec).toFixed(1)}s</span>
                      </div>
                      <p className="text-slate">{String(sc.role)}</p>
                      <div className="flex items-center gap-2 hint pt-1">
                        <span>Pacing: <b>{String(sc.pacing_mode)}</b></span>
                        <span>Transition: <b>{String(sc.transition)}</b></span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="py-16 text-center text-slate hint text-xs">
                Run the deconstruction engine to extract hook cadence, camera movements, and scene blueprint.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mode 2: Semantic Authoring (SVML) */}
      {mode === "author" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-base">SVML Semantic Script Editor</h3>
              <span className="text-xs hint font-mono">@[Role] · @[Segment] · @&#123;moment&#125;</span>
            </div>
            <p className="hint text-xs">
              Declare speaker roles, structured segments, and semantic moments (like <code className="text-amber-500">@&#123;reveal&#125;</code> or <code className="text-amber-500">@&#123;zoom&#125;</code>). Visual triggers are separated from dialogue so TTS audio stays clean.
            </p>
            <textarea
              rows={14}
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
              className="w-full font-mono text-xs leading-relaxed p-3 rounded-lg border border-rule bg-panel focus:outline-none focus:ring-1 focus:ring-ink"
            />
            <div className="flex items-center justify-between pt-2">
              <button
                disabled={busy}
                onClick={() => setScriptText(SAMPLE_SVML)}
                className="btn btn-quiet text-xs"
              >
                Load Sample
              </button>
              <button
                disabled={busy || !scriptText.trim()}
                onClick={handleRunAuthor}
                className="btn btn-primary"
              >
                {busy ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Compile Narrative
              </button>
            </div>
          </div>

          <div className="card p-5 space-y-4">
            <h3 className="font-bold text-base">Compiled Narrative & Timeline Tokens</h3>
            {authorResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="p-2 rounded bg-sunken border border-rule">
                    <span className="text-mute block">Segments</span>
                    <span className="font-bold">{((authorResult.segments as unknown[]) || []).length}</span>
                  </div>
                  <div className="p-2 rounded bg-sunken border border-rule">
                    <span className="text-mute block">Moments</span>
                    <span className="font-bold">{((authorResult.moments as unknown[]) || []).length}</span>
                  </div>
                  <div className="p-2 rounded bg-sunken border border-rule">
                    <span className="text-mute block">Est. Runtime</span>
                    <span className="font-bold">{String(authorResult.estimated_duration_sec)}s</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="label">Spoken Audio Dialogue (TTS Cleaned)</label>
                  <div className="p-3 rounded-lg border border-rule bg-sunken text-xs text-slate italic max-h-[140px] overflow-y-auto">
                    "{String(authorResult.spoken_dialogue)}"
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="label">Segments & Token Alignment</label>
                  <div className="max-h-[200px] overflow-y-auto space-y-2 pr-1">
                    {((authorResult.segments as Array<Record<string, unknown>>) || []).map((seg, i) => (
                      <div key={i} className="p-2.5 rounded border border-rule bg-panel text-xs space-y-1">
                        <div className="flex items-center justify-between font-semibold">
                          <span>{String(seg.title)} [{String(seg.role)}]</span>
                          <span className="timecode">{Number(seg.start_sec).toFixed(1)}s - {Number(seg.end_sec).toFixed(1)}s</span>
                        </div>
                        <p className="text-slate text-[11px] truncate">{String(seg.spoken_text)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-20 text-center text-slate hint text-xs">
                Compile semantic script to inspect token alignment, speaker roles, and clean dialogue extraction.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mode 3: Variant Engine */}
      {mode === "variants" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <div className="card p-5 space-y-4">
            <h3 className="font-bold text-base flex items-center gap-2">
              <Layers className="w-4 h-4 text-amber-500" /> Multi-Variant Generator
            </h3>
            <p className="hint text-xs">
              Generate localized language variants, vertical 9:16 short cuts, or alternative speaker performances. Unaffected visual renders and background audio tracks are reused automatically without wasteful re-rendering.
            </p>
            <div className="space-y-3 pt-2">
              <div>
                <label className="label">Variant Type</label>
                <select
                  value={variantType}
                  onChange={(e) => setVariantType(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-sm rounded-lg border border-rule bg-panel"
                >
                  <option value="voice_swap">Voice / Persona Swap (e.g. Male to Female Anchor)</option>
                  <option value="aspect_ratio">Aspect Ratio Conversion (16:9 to 9:16 Shorts/Reels)</option>
                  <option value="language_swap">Language Localization (Auto-translate & Voice)</option>
                </select>
              </div>

              {variantType === "voice_swap" && (
                <div>
                  <label className="label">Target Neural Voice</label>
                  <select
                    value={variantVoice}
                    onChange={(e) => setVariantVoice(e.target.value)}
                    className="w-full mt-1 px-3 py-2 text-sm rounded-lg border border-rule bg-panel"
                  >
                    <option value="narrator_warm">Female Anchor (AriaNeural)</option>
                    <option value="narrator_deep">Male Anchor (ChristopherNeural)</option>
                    <option value="character_2">Female Expressive (JennyNeural)</option>
                    <option value="character_1">Male Expressive (GuyNeural)</option>
                  </select>
                </div>
              )}

              {variantType === "aspect_ratio" && (
                <div>
                  <label className="label">Target Shape</label>
                  <select
                    value={variantAspect}
                    onChange={(e) => setVariantAspect(e.target.value)}
                    className="w-full mt-1 px-3 py-2 text-sm rounded-lg border border-rule bg-panel"
                  >
                    <option value="9:16">Vertical 9:16 (Shorts, Reels, TikTok - 1080x1920)</option>
                    <option value="1:1">Square 1:1 (Feed posts - 1080x1080)</option>
                    <option value="16:9">Widescreen 16:9 (YouTube - 1920x1080)</option>
                  </select>
                </div>
              )}

              {variantType === "language_swap" && (
                <div>
                  <label className="label">Target Language</label>
                  <select
                    value={variantLang}
                    onChange={(e) => setVariantLang(e.target.value)}
                    className="w-full mt-1 px-3 py-2 text-sm rounded-lg border border-rule bg-panel"
                  >
                    <option value="es">Spanish (es-ES)</option>
                    <option value="hi">Hindi (hi-IN)</option>
                    <option value="fr">French (fr-FR)</option>
                    <option value="de">German (de-DE)</option>
                  </select>
                </div>
              )}

              <div className="pt-3">
                <button
                  disabled={busy}
                  onClick={handleRunVariants}
                  className="btn btn-primary"
                >
                  {busy ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />} Generate Zero-Waste Variant
                </button>
              </div>
            </div>
          </div>

          <div className="card p-5 space-y-4">
            <h3 className="font-bold text-base">Variant Architecture & Reused Assets</h3>
            {variantResult ? (
              <div className="space-y-4">
                {((variantResult.variants as Array<Record<string, unknown>>) || []).map((v, i) => (
                  <div key={i} className="p-3.5 rounded-lg border border-rule bg-panel text-xs space-y-2">
                    <div className="flex items-center justify-between font-bold text-sm">
                      <span>{String(v.variant_name)}</span>
                      <span className="chip chip-done">
                        {String(v.estimated_compute_savings_pct)}% Compute Saved
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-mute text-[11px] pt-1">
                      <div>Reused Scenes: <b className="text-ink">{String(v.reused_scenes_count)}</b></div>
                      <div>Re-rendered Scenes: <b className="text-ink">{String(v.regenerated_scenes_count)}</b></div>
                    </div>
                    <div className="space-y-1 pt-2">
                      <span className="label block text-[10px]">Scene Execution Status:</span>
                      <div className="max-h-[160px] overflow-y-auto space-y-1">
                        {((v.scenes as Array<Record<string, unknown>>) || []).map((sc, j) => (
                          <div key={j} className="flex items-center justify-between p-1.5 rounded bg-sunken text-[11px]">
                            <span className="truncate">{String(sc.title)}</span>
                            <span className={`chip ${sc.status === "reused_from_base" ? "chip-done" : "chip-hold"}`}>
                              {String(sc.status)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-20 text-center text-slate hint text-xs">
                Select a variant type to spawn persona, language, or aspect ratio adaptations with zero redundant render time.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
