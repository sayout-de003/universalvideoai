import { useRef, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Link2, Play, Plus, ShieldCheck, Sparkles, Trash2, Upload } from "lucide-react";
import { studioClient, type ExtractedFileResult } from "../api/client";

export interface PendingRefUpload {
  file: File;
  role: string;
  userNotes: string;
}

interface Props {
  onCreate: (payload: Record<string, unknown>, runImmediately: boolean, refFiles?: PendingRefUpload[]) => Promise<void>;
}

const VISUAL_STYLES = [
  { id: "", label: "Let AI decide", note: "Matches visual style from your prompt & references" },
  { id: "pixel_art", label: "Pixel Art", note: "Crisp 16-bit sprites, stepped palette, LibreSprite / Canvas" },
  { id: "2d_illustrated", label: "2D Illustrated", note: "Vector & cel-shaded character animation, HyperFrames / Remotion" },
  { id: "3d_stylized", label: "3D Stylized", note: "Rigged 3D characters, PBR lighting, Headless Blender / Three.js" },
  { id: "hand_drawn_storybook", label: "Hand-Drawn Storybook", note: "Watercolor parchment, sketchy ink contours, OpenToonz / Canvas" },
];

const REFERENCE_ROLES = [
  { id: "visual_style", label: "Visual Style" },
  { id: "character_reference", label: "Character Design" },
  { id: "environment_reference", label: "Environment / World" },
  { id: "camera_reference", label: "Camera & Framing" },
  { id: "animation_reference", label: "Animation & Motion" },
  { id: "story_reference", label: "Story & Pacing" },
  { id: "factual_source", label: "Factual Source / Research" },
  { id: "voice_reference", label: "Voice Reference" },
  { id: "music_reference", label: "Music Reference" },
  { id: "sound_reference", label: "Sound Design" },
  { id: "brand_reference", label: "Brand / Logo" },
];

const LENGTHS: Array<{ label: string; sec: string }> = [
  { label: "Let AI decide", sec: "" },
  { label: "30 sec", sec: "30" },
  { label: "1 min", sec: "60" },
  { label: "5 min", sec: "300" },
  { label: "10 min", sec: "600" },
  { label: "20 min", sec: "1200" },
];
const SHAPES = [
  { id: "16:9", label: "Widescreen", note: "YouTube / Cinema, 16:9", res: "1920x1080" },
  { id: "9:16", label: "Vertical", note: "Shorts / Reels, 9:16", res: "1080x1920" },
  { id: "1:1", label: "Square", note: "Feed posts, 1:1", res: "1080x1080" },
];
const FORMATS = [
  { id: "", label: "Let AI decide (Auto-detect best format & narrative arc)" },
  { id: "documentaries", label: "Documentary (Hollywood Evidence-Led)" },
  { id: "educational_videos", label: "Educational / Animated Explainer" },
  { id: "fiction_short_films", label: "Animated / Fiction Short Film (Pixar 2D/3D)" },
  { id: "youtube_shorts", label: "YouTube Shorts / Reels / TikTok (High-Retention)" },
  { id: "youtube_longform", label: "YouTube Long-Form Essay" },
  { id: "historical_recreations", label: "Historical Recreation & Biography" },
  { id: "brand_commercials", label: "Brand Commercial / Ad" },
  { id: "saas_product_demos", label: "SaaS / Tech Product Explainer" },
  { id: "movie_trailers", label: "Cinematic Trailer / Teaser" },
  { id: "music_videos", label: "Music Video / Beat-Mapped Visuals" },
];
const VOICES = [
  { id: "auto", label: "Let AI decide (Dual Human Male + Female Neural Voices)" },
  { id: "dual", label: "Dual Male & Female Conversational Voices" },
  { id: "male", label: "Male Human Voice Only (ChristopherNeural / GuyNeural)" },
  { id: "female", label: "Female Human Voice Only (AriaNeural / JennyNeural)" },
];
const ENGINES = [
  { id: "", label: "Let AI decide (Pixar 2D/3D + Remotion Motion Graphics + xfade)" },
  { id: "hyperframes", label: "Pixar 2D/3D Character & Parallax Animation (HyperFrames)" },
  { id: "libresprite", label: "Pixel Art Sprite & Tilemap Pipeline (LibreSprite / Canvas)" },
  { id: "opentoonz", label: "Hand-Drawn Storybook & Watercolor Pipeline (OpenToonz / Canvas)" },
  { id: "remotion", label: "Kinetic Motion Graphics & Data HUD (Remotion)" },
  { id: "threejs", label: "3D WebGL Scenes (Three.js)" },
  { id: "blender", label: "3D Rigged Character Animation (Blender)" },
  { id: "ffmpeg", label: "Cinematic Slideshow & Footage (FFmpeg)" },
];

export function NewProjectView({ onCreate }: Props) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [videoFormat, setVideoFormat] = useState("");
  const [visualStyle, setVisualStyle] = useState("");
  const [productionMode, setProductionMode] = useState<"free_open_source" | "hybrid" | "professional">("free_open_source");
  const [voiceMode, setVoiceMode] = useState("auto");
  const [shape, setShape] = useState(SHAPES[0]);
  const [lengthSec, setLengthSec] = useState("");
  const [more, setMore] = useState(true);
  const [mode, setMode] = useState<"automatic" | "professional">("automatic");
  const [language, setLanguage] = useState("en");
  const [subLangs, setSubLangs] = useState("en");
  const [uploadedScript, setUploadedScript] = useState("");
  const [refUrl, setRefUrl] = useState("");
  const [refRole, setRefRole] = useState("visual_style");
  const [refNotes, setRefNotes] = useState("");
  const [refLinks, setRefLinks] = useState<Array<{ url: string; role: string; user_notes: string }>>([]);
  const [refFiles, setRefFiles] = useState<PendingRefUpload[]>([]);
  const [refFileRole, setRefFileRole] = useState("visual_style");
  const [refFileNotes, setRefFileNotes] = useState("");
  const [engine, setEngine] = useState("");
  const [loading, setLoading] = useState<"plan" | "run" | "interpret" | null>(null);
  const [briefPreview, setBriefPreview] = useState<Record<string, unknown> | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [fileInfo, setFileInfo] = useState<ExtractedFileResult | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const refMediaInputRef = useRef<HTMLInputElement | null>(null);

  const addRefLink = () => {
    const trimmed = refUrl.trim();
    if (!trimmed) return;
    setRefLinks((prev) => [...prev, { url: trimmed, role: refRole, user_notes: refNotes.trim() }]);
    setRefUrl("");
    setRefNotes("");
  };

  const addRefFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const next: PendingRefUpload[] = [];
    Array.from(files).forEach((f) => {
      next.push({ file: f, role: refFileRole, userNotes: refFileNotes.trim() });
    });
    setRefFiles((prev) => [...prev, ...next]);
    setRefFileNotes("");
  };

  const handleInterpret = async () => {
    const effectivePrompt = prompt.trim() || uploadedScript.trim();
    if (!effectivePrompt) return;
    setLoading("interpret");
    try {
      const allRefs = [
        ...refLinks.map((r) => ({ url: r.url, roles: [r.role], user_notes: r.user_notes })),
        ...(refUrl.trim() ? [{ url: refUrl.trim(), roles: [refRole], user_notes: refNotes.trim() }] : []),
      ];
      const res = await studioClient.interpretPrompt({
        prompt: effectivePrompt,
        production_mode: productionMode,
        preferences: {
          video_format: videoFormat || undefined,
          visual_style: visualStyle || undefined,
          target_duration_sec: lengthSec ? Number(lengthSec) : undefined,
        },
        references: allRefs,
        uploads: refFiles.map((f) => ({ filename: f.file.name, roles: [f.role], user_notes: f.userNotes })),
      });
      setBriefPreview(res);
    } catch (err) {
      setFileError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  };

  const handleFileUpload = async (file: File) => {
    setFileBusy(true);
    setFileError(null);
    try {
      const res = await studioClient.extractFile(file);
      setFileInfo(res);
      if (res.parsed_title && !title.trim()) {
        setTitle(res.parsed_title);
      }
      if (res.parsed_duration_sec && !lengthSec) {
        setLengthSec(String(Math.round(res.parsed_duration_sec)));
      }
      if (res.extracted_text) {
        setUploadedScript(res.extracted_text);
        if (!prompt.trim()) {
          setPrompt(
            res.parsed_title
              ? `${res.parsed_title} — ${res.parsed_subject || "Cinematic production from uploaded file"}`
              : res.extracted_text.slice(0, 600)
          );
        }
      }
    } catch (err) {
      // Fallback: read directly in browser as UTF-8 text if possible
      try {
        const rawText = await file.text();
        setUploadedScript(rawText);
        if (!prompt.trim()) setPrompt(rawText.slice(0, 600));
        setFileInfo({
          ok: true,
          filename: file.name,
          extension: file.name.split(".").pop() || "",
          size_bytes: file.size,
          kind: "text_fallback",
          extracted_text: rawText,
        });
      } catch {
        setFileError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setFileBusy(false);
    }
  };

  const submit = async (runNow: boolean) => {
    const effectivePrompt = prompt.trim() || uploadedScript.trim();
    if (!effectivePrompt) return;
    setLoading(runNow ? "run" : "plan");
    try {
      const allRefs = [
        ...refLinks.map((r) => ({ url: r.url, roles: [r.role], user_notes: r.user_notes })),
        ...(refUrl.trim() ? [{ url: refUrl.trim(), roles: [refRole], user_notes: refNotes.trim() }] : []),
      ];
      await onCreate({
        title: title.trim() || null,
        prompt: effectivePrompt,
        mode,
        production_mode: productionMode,
        video_format: videoFormat || null,
        visual_style: visualStyle || null,
        voice_mode: voiceMode || "auto",
        aspect_ratio: shape.id,
        resolution: shape.res,
        target_duration_sec: lengthSec ? Number(lengthSec) : null,
        language,
        subtitle_languages: subLangs.split(",").map((s) => s.trim()).filter(Boolean),
        uploaded_script: uploadedScript.trim() || null,
        reference_video_url: refUrl.trim() || null,
        references: allRefs,
        preferred_render_engine: engine || null,
      }, runNow, refFiles);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="max-w-3xl space-y-7">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">New video</h1>
        <p className="text-slate mt-1">
          Describe your idea, paste a screenplay, or upload any file (.pdf, .docx, .md, .txt, .srt, .json, .csv, audio/video). Choose exact settings or let the AI Director decide and stream its reasoning live.
        </p>
      </div>

      <div className="card p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
          <div>
            <label htmlFor="title" className="label">Project title (optional — auto-extracted if left blank)</label>
            <input
              id="title"
              className="field"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Napoleon Bonaparte — Rise and Legacy"
            />
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="*/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileUpload(f);
              }}
            />
            <button
              type="button"
              disabled={fileBusy}
              onClick={() => fileInputRef.current?.click()}
              className="btn btn-quiet w-full"
            >
              <Upload className="w-4 h-4" /> {fileBusy ? "Reading file…" : "Upload any file (Script / PDF / DOCX / SRT / Media)"}
            </button>
          </div>
        </div>

        {fileInfo && (
          <div className="rounded-lg border border-done/40 bg-done-soft px-3.5 py-2.5 text-[13px] flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="font-semibold text-done">Loaded file: {fileInfo.filename}</span>
              <span className="text-slate ml-2">
                ({fileInfo.kind}{fileInfo.scene_count ? ` · ${fileInfo.scene_count} scenes parsed` : ""}{fileInfo.parsed_duration_sec ? ` · ${fileInfo.parsed_duration_sec}s` : ""})
              </span>
            </div>
            <button
              type="button"
              onClick={() => { setFileInfo(null); setUploadedScript(""); }}
              className="text-xs underline text-slate hover:text-ink"
            >
              Clear file
            </button>
          </div>
        )}
        {fileError && (
          <div className="rounded-lg border border-live/40 bg-live-soft px-3.5 py-2 text-[13px] text-live">
            Could not read file: {fileError}
          </div>
        )}

        <div>
          <label htmlFor="prompt" className="label">What should the video be about? (Or paste your full screenplay here)</label>
          <textarea id="prompt" rows={5} value={prompt} onChange={(e) => setPrompt(e.target.value)} className="field text-[15px]"
            placeholder="A documentary on Napoleon Bonaparte with dual human male & female narration, Pixar-style 2D/3D animated scenes, motion graphics, and smooth xfade transitions..." />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="format" className="label">Video format</label>
            <select id="format" className="field" value={videoFormat} onChange={(e) => setVideoFormat(e.target.value)}>
              {FORMATS.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="voice" className="label">Human voice casting</label>
            <select id="voice" className="field" value={voiceMode} onChange={(e) => setVoiceMode(e.target.value)}>
              {VOICES.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
            </select>
          </div>
        </div>

        <fieldset>
          <legend className="label">Visual style & animation profile</legend>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {VISUAL_STYLES.map((st) => (
              <button
                key={st.id || "auto"}
                type="button"
                onClick={() => setVisualStyle(st.id)}
                aria-pressed={visualStyle === st.id}
                className={`text-left rounded-lg border px-3 py-2.5 ${visualStyle === st.id ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}
              >
                <div className="font-semibold text-[13px]">{st.label}</div>
                <div className={`text-xs mt-0.5 ${visualStyle === st.id ? "text-[#b9c2cb]" : "text-mute"}`}>{st.note}</div>
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="label">Production mode & cost policy</legend>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setProductionMode("free_open_source")}
              aria-pressed={productionMode === "free_open_source"}
              className={`text-left rounded-lg border px-3 py-2.5 ${productionMode === "free_open_source" ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}
            >
              <div className="font-semibold text-[13px] flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" /> Free & Open-Source
              </div>
              <div className={`text-xs mt-0.5 ${productionMode === "free_open_source" ? "text-[#b9c2cb]" : "text-mute"}`}>
                100% local & free engines (Blender, LibreSprite, OpenToonz, HyperFrames, Remotion, Edge-TTS, FFmpeg). Blocks all paid APIs.
              </div>
            </button>
            <button
              type="button"
              onClick={() => setProductionMode("hybrid")}
              aria-pressed={productionMode === "hybrid"}
              className={`text-left rounded-lg border px-3 py-2.5 ${productionMode === "hybrid" ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}
            >
              <div className="font-semibold text-[13px]">Hybrid / Automatic</div>
              <div className={`text-xs mt-0.5 ${productionMode === "hybrid" ? "text-[#b9c2cb]" : "text-mute"}`}>
                Combines local open-source engines with configured cloud providers when helpful.
              </div>
            </button>
            <button
              type="button"
              onClick={() => { setProductionMode("professional"); setMode("professional"); }}
              aria-pressed={productionMode === "professional"}
              className={`text-left rounded-lg border px-3 py-2.5 ${productionMode === "professional" ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}
            >
              <div className="font-semibold text-[13px]">Professional Studio</div>
              <div className={`text-xs mt-0.5 ${productionMode === "professional" ? "text-[#b9c2cb]" : "text-mute"}`}>
                Full manual approval gates, multi-engine routing, and frame-accurate control.
              </div>
            </button>
          </div>
        </fieldset>

        {/* Reference Links & Uploaded Reference Media */}
        <div className="rounded-lg border border-rule p-4 space-y-3 bg-sunken/50">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold text-[13.5px] flex items-center gap-1.5">
                <Link2 className="w-4 h-4" /> Reference Links & Media Attachments
              </div>
              <p className="hint">Attach YouTube videos/channels, Instagram public posts/Reels/profiles, websites, or upload images, videos, audio, and PDFs with explicit roles.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_180px_1fr_auto] gap-2 items-center">
            <input
              className="field text-[13px]"
              value={refUrl}
              onChange={(e) => setRefUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRefLink())}
              placeholder="Paste YouTube, Instagram, or Web URL…"
            />
            <select className="field text-[13px]" value={refRole} onChange={(e) => setRefRole(e.target.value)}>
              {REFERENCE_ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
            <input
              className="field text-[13px]"
              value={refNotes}
              onChange={(e) => setRefNotes(e.target.value)}
              placeholder="Notes (e.g. 'use this color palette & pacing')"
            />
            <button type="button" onClick={addRefLink} className="btn btn-quiet text-xs py-2 px-3">
              <Plus className="w-3.5 h-3.5" /> Add URL
            </button>
          </div>

          {refLinks.length > 0 && (
            <ul className="space-y-1.5">
              {refLinks.map((item, idx) => (
                <li key={idx} className="rounded border border-rule bg-panel px-3 py-1.5 text-xs flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate">
                    <span className="chip mr-2">{item.role}</span>
                    <span className="font-mono text-ink">{item.url}</span>
                    {item.user_notes && <span className="text-slate ml-2">— “{item.user_notes}”</span>}
                  </div>
                  <button type="button" onClick={() => setRefLinks((prev) => prev.filter((_, i) => i !== idx))} className="text-slate hover:text-live">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="grid grid-cols-1 md:grid-cols-[180px_1fr_auto] gap-2 items-center pt-2 border-t border-rule">
            <select className="field text-[13px]" value={refFileRole} onChange={(e) => setRefFileRole(e.target.value)}>
              {REFERENCE_ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
            <input
              className="field text-[13px]"
              value={refFileNotes}
              onChange={(e) => setRefFileNotes(e.target.value)}
              placeholder="Notes for uploaded reference files (optional)…"
            />
            <div>
              <input
                ref={refMediaInputRef}
                type="file"
                multiple
                accept="image/*,video/*,audio/*,.pdf,.docx,.txt,.md"
                className="hidden"
                onChange={(e) => addRefFiles(e.target.files)}
              />
              <button type="button" onClick={() => refMediaInputRef.current?.click()} className="btn btn-quiet text-xs py-2 px-3">
                <Upload className="w-3.5 h-3.5" /> Attach Images / Videos / Docs
              </button>
            </div>
          </div>

          {refFiles.length > 0 && (
            <ul className="space-y-1.5">
              {refFiles.map((rf, idx) => (
                <li key={idx} className="rounded border border-rule bg-panel px-3 py-1.5 text-xs flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate">
                    <span className="chip mr-2">{rf.role}</span>
                    <span className="font-semibold">{rf.file.name}</span>
                    <span className="text-mute ml-1.5">({Math.round(rf.file.size / 1024)} KB)</span>
                    {rf.userNotes && <span className="text-slate ml-2">— “{rf.userNotes}”</span>}
                  </div>
                  <button type="button" onClick={() => setRefFiles((prev) => prev.filter((_, i) => i !== idx))} className="text-slate hover:text-live">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <fieldset>
          <legend className="label">Length</legend>
          <div className="flex flex-wrap items-center gap-2">
            {LENGTHS.map((l) => (
              <button key={l.label} type="button" onClick={() => setLengthSec(l.sec)} aria-pressed={lengthSec === l.sec}
                className={`btn ${lengthSec === l.sec ? "btn-primary" : "btn-quiet"}`}>{l.label}</button>
            ))}
            <input
              type="number"
              min={5}
              max={14400}
              value={lengthSec}
              onChange={(e) => setLengthSec(e.target.value)}
              placeholder="Custom sec (e.g. 45)"
              className="field w-44 py-1.5 text-[13px]"
            />
          </div>
        </fieldset>

        <fieldset>
          <legend className="label">Shape</legend>
          <div className="grid grid-cols-3 gap-2">
            {SHAPES.map((s) => (
              <button key={s.id} type="button" onClick={() => setShape(s)} aria-pressed={shape.id === s.id}
                className={`text-left rounded-lg border px-3 py-2.5 ${shape.id === s.id ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}>
                <div className="font-semibold text-[13px]">{s.label}</div>
                <div className={`text-xs ${shape.id === s.id ? "text-[#b9c2cb]" : "text-mute"}`}>{s.note}</div>
              </button>
            ))}
          </div>
        </fieldset>

        <div>
          <button type="button" onClick={() => setMore((v) => !v)} className="btn btn-ghost -ml-2" aria-expanded={more}>
            {more ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />} Animation engine, script & language options
          </button>
          {more && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
              <div>
                <label htmlFor="mode" className="label">Who drives?</label>
                <select id="mode" className="field" value={mode} onChange={(e) => setMode(e.target.value as "automatic" | "professional")}>
                  <option value="automatic">The AI team decides (logs reasoning live)</option>
                  <option value="professional">I want manual control at each step</option>
                </select>
              </div>
              <div>
                <label htmlFor="engine" className="label">Animation & visual engine</label>
                <select id="engine" className="field" value={engine} onChange={(e) => setEngine(e.target.value)}>
                  {ENGINES.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="lang" className="label">Narration language</label>
                <input id="lang" className="field" value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="en" />
              </div>
              <div>
                <label htmlFor="subs" className="label">Subtitle languages</label>
                <input id="subs" className="field" value={subLangs} onChange={(e) => setSubLangs(e.target.value)} placeholder="en, hi" />
                <div className="hint mt-1">Separate with commas.</div>
              </div>
              <div className="md:col-span-2">
                <label htmlFor="ref" className="label">Reference video link</label>
                <input id="ref" className="field" value={refUrl} onChange={(e) => setRefUrl(e.target.value)} placeholder="https://… (optional, for style)" />
              </div>
              <div className="md:col-span-2">
                <label htmlFor="script" className="label">Uploaded or pasted script / file content</label>
                <textarea id="script" rows={5} className="field font-mono text-[12.5px]" value={uploadedScript} onChange={(e) => setUploadedScript(e.target.value)} placeholder="Paste a structured # SCREENPLAY: ... or upload any file above (.pdf, .docx, .md, .txt, .srt, .json, .csv). Leave empty to have the Hollywood Screenplay Architect write one." />
              </div>
            </div>
          )}
        </div>

        <div className="rounded-lg bg-sunken px-3.5 py-2.5 text-[12.5px] text-slate flex items-start gap-2">
          <Sparkles className="w-4 h-4 text-ink shrink-0 mt-0.5" />
          <span>
            Any setting left on <strong>Let AI decide</strong> is automatically selected by the AI Director based on your topic and trending formats, with full decision reasoning streamed in the <strong>Produce</strong> live log.
          </span>
        </div>

        {briefPreview && (
          <div className="rounded-lg border border-ink/30 bg-panel p-4 space-y-2 text-[13px]">
            <div className="font-bold flex items-center justify-between">
              <span>AI Production Summary Preview</span>
              <span className="chip text-xs">{String((briefPreview.production_summary as Record<string, unknown>)?.visual_direction || visualStyle || "Auto")}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">Format</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.format || "Auto")}</div>
              </div>
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">Duration</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.duration || "Auto")}</div>
              </div>
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">Visual Direction</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.visual_direction || "Auto")}</div>
              </div>
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">References</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.reference_material || "0")}</div>
              </div>
            </div>
            {Array.isArray(briefPreview.questions) && briefPreview.questions.length > 0 && (
              <div className="text-xs text-slate pt-1">
                <span className="font-semibold text-ink">Suggested clarifications: </span>
                {(briefPreview.questions as Array<Record<string, unknown>>).map((q) => String(q.question)).join(" • ")}
              </div>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-rule">
          <button disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())} onClick={() => submit(false)} className="btn btn-primary mt-5">
            <FileText className="w-4 h-4" /> {loading === "plan" ? "Researching & writing script…" : "Write the script first"}
          </button>
          <button disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())} onClick={() => submit(true)} className="btn btn-quiet mt-5">
            <Play className="w-4 h-4" /> {loading === "run" ? "Starting…" : "Skip review and make the video"}
          </button>
          <button type="button" disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())} onClick={handleInterpret} className="btn btn-ghost mt-5">
            <Sparkles className="w-4 h-4" /> {loading === "interpret" ? "Analyzing brief…" : "Preview AI interpretation"}
          </button>
        </div>
      </div>
    </div>
  );
}
