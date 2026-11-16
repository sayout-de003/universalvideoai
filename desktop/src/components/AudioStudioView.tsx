import { useState } from "react";
import { Mic, Play, Sparkles, Volume2 } from "lucide-react";
import { API_BASE, studioClient } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props { project: ProjectDetail; }

const STEMS = [
  { id: "master_mix", label: "Final mix", note: "Everything together, as heard in the video" },
  { id: "narration", label: "Narration", note: "Voice only" },
  { id: "music", label: "Music", note: "Background score" },
  { id: "sfx", label: "Sound effects", note: "Transitions and accents" },
];

const QUICK_VOICES = [
  { id: "en-US-ChristopherNeural", label: "Christopher (Male Authority - Edge Neural)", type: "edge" },
  { id: "en-US-AriaNeural", label: "Aria (Female Expressive - Edge Neural)", type: "edge" },
  { id: "sarah", label: "Sarah (Female Professional CTO - Edge)", type: "edge" },
  { id: "mark", label: "Mark (Male Lead Engineer - Edge)", type: "edge" },
  { id: "en-US-JennyNeural", label: "Jenny (Female Warm - Edge Neural)", type: "edge" },
  { id: "en-US-GuyNeural", label: "Guy (Male Casual - Edge Neural)", type: "edge" },
  { id: "en-GB-SoniaNeural", label: "Sonia (British Female - Edge Neural)", type: "edge" },
  { id: "en-GB-RyanNeural", label: "Ryan (British Male - Edge Neural)", type: "edge" },
  { id: "hi-IN-MadhurNeural", label: "Madhur (Hindi/English Male - Edge Neural)", type: "edge" },
  { id: "hi-IN-SwaraNeural", label: "Swara (Hindi/English Female - Edge Neural)", type: "edge" },
  { id: "Zyphra/ZONOS3-Mini", label: "Hugging Face · Zonos-v0.3-Mini (100M MoE Zero-Shot Voice)", type: "hf" },
  { id: "k2-fsa/OmniVoice", label: "Hugging Face · OmniVoice (600+ Languages at RTF 0.025)", type: "hf" },
  { id: "fishaudio/drama-3", label: "Hugging Face · Drama-3 (Fish Audio 35B Dramatic Acting)", type: "hf" },
];

export function AudioStudioView({ project }: Props) {
  const [testText, setTestText] = useState("Welcome to the studio. Our neural voice pipeline delivers studio-grade narration.");
  const [selectedVoice, setSelectedVoice] = useState(QUICK_VOICES[0].id);
  const [synthBusy, setSynthBusy] = useState(false);
  const [testAudioUrl, setTestAudioUrl] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const audioAssets = project.assets.filter((a) => a.asset_type === "audio");
  const pid = project.project.id;
  const made = project.project.status === "completed" || project.project.status === "qa_failed";

  const handleTestVoice = async () => {
    if (!testText.trim()) return;
    setSynthBusy(true);
    setTestError(null);
    try {
      const choice = QUICK_VOICES.find((v) => v.id === selectedVoice);
      if (choice?.type === "hf") {
        const res = await studioClient.generateHuggingFaceVoice({
          model_key: selectedVoice,
          text: testText.trim(),
        });
        if (res.output_wav) {
          // Use filename for playback
          const filename = String(res.output_wav).split("/").pop();
          setTestAudioUrl(`${API_BASE}/api/projects/hf_voice_generations/media/${filename}`);
        }
      } else {
        // Generate via HF voice endpoint which routes all voice keys
        const res = await studioClient.generateHuggingFaceVoice({
          model_key: "Zyphra/ZONOS3-Mini",
          voice_id: selectedVoice,
          text: testText.trim(),
        });
        if (res.output_wav) {
          const filename = String(res.output_wav).split("/").pop();
          setTestAudioUrl(`${API_BASE}/api/projects/hf_voice_generations/media/${filename}`);
        }
      }
    } catch (err) {
      setTestError(err instanceof Error ? err.message : String(err));
    } finally {
      setSynthBusy(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Voice Casting in Project */}
      <section>
        <h2 className="font-bold mb-3 flex items-center gap-2"><Mic className="w-4 h-4" /> Cast Voices in this Production</h2>
        {project.speakers.length === 0 ? <div className="card p-5 hint">Voices are assigned when the script is written.</div> : (
          <ul className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {project.speakers.map((sp) => (
              <li key={sp.id} className="card p-4 text-[13px]">
                <div className="font-bold">{sp.name}</div>
                <div className="text-slate mt-0.5">{sp.role}</div>
                <div className="hint mt-1.5">{sp.voice_id} · {sp.voice_provider} · {sp.language}</div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Voice Sandbox */}
      <section className="card p-5 space-y-4 bg-sunken/40">
        <div>
          <h2 className="font-bold flex items-center gap-2 text-ink">
            <Sparkles className="w-4 h-4 text-live" /> Live Voice Testing Sandbox
          </h2>
          <p className="hint mt-0.5">Test real-time synthesis across Edge Neural human actors and Hugging Face open-source zero-shot voice models.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-3 items-end">
          <div>
            <label className="label">Select Voice Actor / Model</label>
            <select
              className="field text-xs"
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
            >
              {QUICK_VOICES.map((v) => (
                <option key={v.id} value={v.id}>{v.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Dialogue Line to Speak</label>
            <input
              className="field text-xs"
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder="Type dialogue to preview voice..."
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled={synthBusy || !testText.trim()}
            onClick={handleTestVoice}
            className="btn btn-primary text-xs py-1.5 px-3"
          >
            <Play className={`w-3.5 h-3.5 ${synthBusy ? "animate-spin" : ""}`} />
            {synthBusy ? "Synthesizing audio…" : "Synthesize Preview"}
          </button>
          {testAudioUrl && (
            <audio controls autoPlay className="h-8 max-w-md flex-1" src={testAudioUrl} />
          )}
        </div>
        {testError && <p className="text-xs text-live">{testError}</p>}
      </section>

      {/* Production Audio Stems */}
      <section>
        <h2 className="font-bold mb-3 flex items-center gap-2"><Volume2 className="w-4 h-4" /> Final Mix & Stems</h2>
        {!made ? <div className="card p-5 hint">Audio tracks are mixed near the end of production. They'll be playable here once the video is finished.</div> : (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {STEMS.map((s) => (
              <li key={s.id} className="card p-4">
                <div className="font-semibold text-[13px]">{s.label}</div>
                <div className="hint mb-2">{s.note}</div>
                <audio controls preload="none" className="w-full h-9" src={`${API_BASE}/api/projects/${pid}/media/stems/${s.id}.wav`} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Recorded Segments */}
      <section>
        <h2 className="font-bold mb-3">Recorded Scene Segments ({audioAssets.length})</h2>
        {audioAssets.length === 0 ? <div className="card p-5 hint">Nothing recorded yet.</div> : (
          <ul className="card divide-y divide-rule">
            {audioAssets.map((a) => (
              <li key={a.id} className="px-4 py-2.5 flex items-center justify-between gap-3 text-[13px]">
                <span className="truncate">{a.file_path.split("/").pop()}</span>
                <span className="hint shrink-0">{a.duration_sec?.toFixed(1)}s · {a.provider}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
