import { useState } from "react";
import { ChevronDown, ChevronRight, FileText, Play } from "lucide-react";

interface Props {
  onCreate: (payload: Record<string, unknown>, runImmediately: boolean) => Promise<void>;
}

const LENGTHS: Array<{ label: string; sec: string }> = [
  { label: "Let the studio decide", sec: "" },
  { label: "1 min", sec: "60" },
  { label: "5 min", sec: "300" },
  { label: "10 min", sec: "600" },
  { label: "20 min", sec: "1200" },
];
const SHAPES = [
  { id: "16:9", label: "Widescreen", note: "YouTube, 16:9", res: "1920x1080" },
  { id: "9:16", label: "Vertical", note: "Shorts, Reels, 9:16", res: "1080x1920" },
  { id: "1:1", label: "Square", note: "Feed posts, 1:1", res: "1080x1080" },
];
const ENGINES = [
  { id: "", label: "Choose automatically" },
  { id: "ffmpeg", label: "Slideshow and footage (FFmpeg)" },
  { id: "hyperframes", label: "2D animation (HyperFrames)" },
  { id: "threejs", label: "3D scenes (Three.js)" },
  { id: "remotion", label: "Motion graphics (Remotion)" },
];

export function NewProjectView({ onCreate }: Props) {
  const [prompt, setPrompt] = useState("");
  const [shape, setShape] = useState(SHAPES[0]);
  const [lengthSec, setLengthSec] = useState("");
  const [more, setMore] = useState(false);
  const [mode, setMode] = useState<"automatic" | "professional">("automatic");
  const [language, setLanguage] = useState("en");
  const [subLangs, setSubLangs] = useState("en");
  const [uploadedScript, setUploadedScript] = useState("");
  const [refUrl, setRefUrl] = useState("");
  const [engine, setEngine] = useState("");
  const [loading, setLoading] = useState<"plan" | "run" | null>(null);

  const submit = async (runNow: boolean) => {
    if (!prompt.trim()) return;
    setLoading(runNow ? "run" : "plan");
    try {
      await onCreate({
        prompt: prompt.trim(), mode, aspect_ratio: shape.id, resolution: shape.res,
        target_duration_sec: lengthSec ? Number(lengthSec) : null,
        language, subtitle_languages: subLangs.split(",").map((s) => s.trim()).filter(Boolean),
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
        <p className="text-slate mt-1">Say what the video is about. You'll review the script before anything is rendered.</p>
      </div>

      <div className="card p-6 space-y-6">
        <div>
          <label htmlFor="prompt" className="label">What should the video be about?</label>
          <textarea id="prompt" rows={5} value={prompt} onChange={(e) => setPrompt(e.target.value)} className="field text-[15px]"
            placeholder="A 20-minute documentary on the rise and fall of the Roman Empire, with calm narration, orchestral music, chapters and English subtitles." />
        </div>

        <fieldset>
          <legend className="label">Length</legend>
          <div className="flex flex-wrap gap-2">
            {LENGTHS.map((l) => (
              <button key={l.label} type="button" onClick={() => setLengthSec(l.sec)} aria-pressed={lengthSec === l.sec}
                className={`btn ${lengthSec === l.sec ? "btn-primary" : "btn-quiet"}`}>{l.label}</button>
            ))}
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
            {more ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />} More options
          </button>
          {more && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
              <div>
                <label htmlFor="mode" className="label">Who drives?</label>
                <select id="mode" className="field" value={mode} onChange={(e) => setMode(e.target.value as "automatic" | "professional")}>
                  <option value="automatic">The AI team decides</option>
                  <option value="professional">I want control at each step</option>
                </select>
              </div>
              <div>
                <label htmlFor="engine" className="label">Visual style</label>
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
                <label htmlFor="script" className="label">Already have a script?</label>
                <textarea id="script" rows={4} className="field" value={uploadedScript} onChange={(e) => setUploadedScript(e.target.value)} placeholder="Paste it here, one scene per line. Leave empty to have one written." />
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-rule">
          <button disabled={loading !== null || !prompt.trim()} onClick={() => submit(false)} className="btn btn-primary mt-5">
            <FileText className="w-4 h-4" /> {loading === "plan" ? "Writing the script…" : "Write the script first"}
          </button>
          <button disabled={loading !== null || !prompt.trim()} onClick={() => submit(true)} className="btn btn-quiet mt-5">
            <Play className="w-4 h-4" /> {loading === "run" ? "Starting…" : "Skip review and make the video"}
          </button>
        </div>
      </div>
    </div>
  );
}
