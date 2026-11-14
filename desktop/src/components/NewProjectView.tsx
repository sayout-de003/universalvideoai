import { useState } from "react";
import { Sparkles } from "lucide-react";

interface Props {
  onCreate: (payload: Record<string, unknown>, runImmediately: boolean) => Promise<void>;
}

export function NewProjectView({ onCreate }: Props) {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<"automatic" | "professional">("automatic");
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [resolution, setResolution] = useState("1920x1080");
  const [durationSec, setDurationSec] = useState("");
  const [language, setLanguage] = useState("en");
  const [subLangs, setSubLangs] = useState("en");
  const [uploadedScript, setUploadedScript] = useState("");
  const [refUrl, setRefUrl] = useState("");
  const [preferredEngine, setPreferredEngine] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (runNow: boolean) => {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      await onCreate({
        prompt: prompt.trim(), mode, aspect_ratio: aspectRatio, resolution,
        target_duration_sec: durationSec ? Number(durationSec) : null,
        language, subtitle_languages: subLangs.split(",").map((s) => s.trim()).filter(Boolean),
        uploaded_script: uploadedScript.trim() || null,
        reference_video_url: refUrl.trim() || null,
        preferred_render_engine: preferredEngine || null,
      }, runNow);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">New Video Production</h1>
        <p className="text-xs text-zinc-400 mt-1">Describe any video in natural language—from a 15-second animated Short to a multi-chapter documentary or 3D scene.</p>
      </div>
      <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-4">
        <div>
          <label className="block text-xs font-medium text-zinc-300 mb-1.5">Describe Your Video</label>
          <textarea rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="e.g. Create a 25-minute cinematic documentary about the history of the Roman Empire with dramatic narration, orchestral music, chapters, and subtitles." className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2.5 text-sm text-zinc-100 focus:outline-none focus:border-amber-500" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Production Mode</label>
            <select value={mode} onChange={(e) => setMode(e.target.value as "automatic" | "professional")} className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200">
              <option value="automatic">Automatic AI Team</option>
              <option value="professional">Professional Control</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Aspect Ratio</label>
            <select value={aspectRatio} onChange={(e) => { const ar = e.target.value; setAspectRatio(ar); setResolution(ar === "9:16" ? "1080x1920" : ar === "1:1" ? "1080x1080" : "1920x1080"); }} className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200">
              <option value="16:9">16:9 Widescreen</option>
              <option value="9:16">9:16 Vertical</option>
              <option value="1:1">1:1 Square</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Duration Override (sec)</label>
            <input type="number" value={durationSec} onChange={(e) => setDurationSec(e.target.value)} placeholder="Auto from prompt" className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200" />
          </div>
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Render Engine</label>
            <select value={preferredEngine} onChange={(e) => setPreferredEngine(e.target.value)} className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200">
              <option value="">Auto-Select Best</option>
              <option value="ffmpeg">FFmpeg Procedural/Master</option>
              <option value="hyperframes">HyperFrames 2D/Character</option>
              <option value="threejs">Three.js 3D Engine</option>
              <option value="remotion">Remotion React</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Narration Language & Subtitles (comma-sep)</label>
            <div className="flex gap-2">
              <input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="en" className="w-20 rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200" />
              <input value={subLangs} onChange={(e) => setSubLangs(e.target.value)} placeholder="en,hi" className="flex-1 rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200" />
            </div>
          </div>
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Reference Video URL (Optional)</label>
            <input value={refUrl} onChange={(e) => setRefUrl(e.target.value)} placeholder="https://..." className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200" />
          </div>
        </div>
        <div>
          <label className="block text-[11px] text-zinc-400 mb-1">Optional Script (one scene per line)</label>
          <textarea rows={3} value={uploadedScript} onChange={(e) => setUploadedScript(e.target.value)} placeholder="Paste an existing script if you already have one..." className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-xs text-zinc-200" />
        </div>
        <div className="flex items-center gap-3 pt-2">
          <button disabled={loading || !prompt.trim()} onClick={() => submit(true)} className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-zinc-950 text-xs font-semibold transition">
            <Sparkles className="w-4 h-4" />{loading ? "Starting Production..." : "Create & Produce Video"}
          </button>
          <button disabled={loading || !prompt.trim()} onClick={() => submit(false)} className="px-4 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-200 text-xs font-medium transition">
            Create Plan & Storyboard Only
          </button>
        </div>
      </div>
    </div>
  );
}
