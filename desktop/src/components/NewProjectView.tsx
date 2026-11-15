import { useRef, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Play, Sparkles, Upload } from "lucide-react";
import { studioClient, type ExtractedFileResult } from "../api/client";

interface Props {
  onCreate: (payload: Record<string, unknown>, runImmediately: boolean) => Promise<void>;
}

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
  { id: "remotion", label: "Kinetic Motion Graphics & Data HUD (Remotion)" },
  { id: "threejs", label: "3D WebGL Scenes (Three.js)" },
  { id: "blender", label: "3D Rigged Character Animation (Blender)" },
  { id: "ffmpeg", label: "Cinematic Slideshow & Footage (FFmpeg)" },
];

export function NewProjectView({ onCreate }: Props) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [videoFormat, setVideoFormat] = useState("");
  const [voiceMode, setVoiceMode] = useState("auto");
  const [shape, setShape] = useState(SHAPES[0]);
  const [lengthSec, setLengthSec] = useState("");
  const [more, setMore] = useState(true);
  const [mode, setMode] = useState<"automatic" | "professional">("automatic");
  const [language, setLanguage] = useState("en");
  const [subLangs, setSubLangs] = useState("en");
  const [uploadedScript, setUploadedScript] = useState("");
  const [refUrl, setRefUrl] = useState("");
  const [engine, setEngine] = useState("");
  const [loading, setLoading] = useState<"plan" | "run" | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [fileInfo, setFileInfo] = useState<ExtractedFileResult | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
      await onCreate({
        title: title.trim() || null,
        prompt: effectivePrompt,
        mode,
        video_format: videoFormat || null,
        voice_mode: voiceMode || "auto",
        aspect_ratio: shape.id,
        resolution: shape.res,
        target_duration_sec: lengthSec ? Number(lengthSec) : null,
        language,
        subtitle_languages: subLangs.split(",").map((s) => s.trim()).filter(Boolean),
        uploaded_script: uploadedScript.trim() || null,
        reference_video_url: refUrl.trim() || null,
        preferred_render_engine: engine || null,
      }, runNow);
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

        <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-rule">
          <button disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())} onClick={() => submit(false)} className="btn btn-primary mt-5">
            <FileText className="w-4 h-4" /> {loading === "plan" ? "Researching & writing script…" : "Write the script first"}
          </button>
          <button disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())} onClick={() => submit(true)} className="btn btn-quiet mt-5">
            <Play className="w-4 h-4" /> {loading === "run" ? "Starting…" : "Skip review and make the video"}
          </button>
        </div>
      </div>
    </div>
  );
}
