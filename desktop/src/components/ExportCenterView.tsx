import { useState } from "react";
import { Download } from "lucide-react";
import { API_BASE } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onExport: (body: Record<string, unknown>) => Promise<Record<string, unknown>>;
}

export function ExportCenterView({ project, onExport }: Props) {
  const [format, setFormat] = useState("mp4");
  const [codec, setCodec] = useState("h264");
  const [resolution, setResolution] = useState(project.project.resolution || "1920x1080");
  const [fps, setFps] = useState(project.project.fps || 30);
  const [bitrate, setBitrate] = useState("8M");
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleExport = async () => {
    setExporting(true);
    setResult(null);
    try {
      const res = await onExport({ format, codec, resolution, aspect_ratio: project.project.aspect_ratio, fps, bitrate, include_subtitles: true, include_chapters: true });
      setResult(`Exported successfully: ${String(res.output_path)}`);
    } catch (err) {
      setResult(`Export failed: ${String(err)}`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Export Center</h1>
        <p className="text-xs text-zinc-400 mt-1">Export master video, audio stems, chapter metadata, and SRT/VTT subtitles.</p>
      </div>
      <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Format</label>
            <select value={format} onChange={(e) => setFormat(e.target.value)} className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-xs text-zinc-200">
              <option value="mp4">MP4</option><option value="mov">MOV</option><option value="webm">WebM</option><option value="wav">WAV (Audio Only)</option><option value="mp3">MP3 (Audio Only)</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Codec</label>
            <select value={codec} onChange={(e) => setCodec(e.target.value)} className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-xs text-zinc-200">
              <option value="h264">H.264</option><option value="h265">H.265 (HEVC)</option><option value="prores">ProRes (MOV)</option><option value="vp9">VP9 (WebM)</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Resolution</label>
            <select value={resolution} onChange={(e) => setResolution(e.target.value)} className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-xs text-zinc-200">
              <option value="1920x1080">1080p (1920x1080)</option><option value="3840x2160">4K UHD (3840x2160)</option><option value="1080x1920">1080p Vertical (1080x1920)</option><option value="1280x720">720p (1280x720)</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-zinc-400 mb-1">Frame Rate & Bitrate</label>
            <div className="flex gap-2">
              <input type="number" value={fps} onChange={(e) => setFps(Number(e.target.value))} className="w-20 rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200" />
              <input value={bitrate} onChange={(e) => setBitrate(e.target.value)} className="flex-1 rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-2 text-xs text-zinc-200" />
            </div>
          </div>
        </div>
        <button disabled={exporting} onClick={handleExport} className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-zinc-950 text-xs font-semibold">
          <Download className="w-4 h-4" />{exporting ? "Encoding Export..." : "Export Production"}
        </button>
        {result && <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-emerald-300">{result}</div>}
        <div className="pt-3 border-t border-zinc-800 text-xs text-zinc-400 space-y-2.5">
          <div className="font-medium text-zinc-300">Download & Share Deliverables</div>
          <div className="flex flex-wrap gap-2">
            <a
              href={`${API_BASE}/api/projects/${project.project.id}/media/exports/final_production.mp4?download=true`}
              download="final_production.mp4"
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-100 font-medium transition"
            >
              Download Master MP4
            </a>
            <a
              href={`${API_BASE}/api/projects/${project.project.id}/share-bundle`}
              download={`${project.project.id}_share_bundle.zip`}
              className="px-3 py-1.5 rounded-lg bg-sky-600/20 hover:bg-sky-600/30 border border-sky-500/40 text-sky-300 font-medium transition"
            >
              Download Shareable ZIP (Video + Subtitles + Stems)
            </a>
            <button
              onClick={() => {
                navigator.clipboard?.writeText(`${project.project.workspace_dir}/exports/final_production.mp4`);
                setResult("Copied local MP4 path to clipboard for sharing.");
              }}
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition"
            >
              Copy Shareable Path
            </button>
          </div>
          <a href={`${API_BASE}/api/projects/${project.project.id}/media/deliverables/production_report.json`} target="_blank" rel="noreferrer" className="text-amber-400 hover:underline block">View Machine-Readable Production Report (JSON)</a>
        </div>
      </div>
    </div>
  );
}
