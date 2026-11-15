import { useState } from "react";
import { Copy, Download, Package } from "lucide-react";
import { API_BASE } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onExport: (body: Record<string, unknown>) => Promise<Record<string, unknown>>;
}

const PRESETS = [
  { id: "1080", label: "Full HD", note: "1920×1080 · best for most uploads", resolution: "1920x1080", codec: "h264", format: "mp4", bitrate: "8M" },
  { id: "4k", label: "4K", note: "3840×2160 · large file", resolution: "3840x2160", codec: "h265", format: "mp4", bitrate: "25M" },
  { id: "720", label: "Small file", note: "1280×720 · quick to share", resolution: "1280x720", codec: "h264", format: "mp4", bitrate: "4M" },
  { id: "audio", label: "Audio only", note: "MP3 of the final mix", resolution: "1920x1080", codec: "h264", format: "mp3", bitrate: "192k" },
];

export function ExportCenterView({ project, onExport }: Props) {
  const p = project.project;
  const [preset, setPreset] = useState(PRESETS[0]);
  const [advanced, setAdvanced] = useState(false);
  const [format, setFormat] = useState("mp4");
  const [codec, setCodec] = useState("h264");
  const [resolution, setResolution] = useState(p.resolution || "1920x1080");
  const [fps, setFps] = useState(p.fps || 30);
  const [bitrate, setBitrate] = useState("8M");
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [exportedFile, setExportedFile] = useState<{ url: string; filename: string } | null>(null);
  const finished = p.status === "completed" || p.status === "qa_failed";
  const base = `${API_BASE}/api/projects/${p.id}`;

  const pick = (pr: typeof PRESETS[number]) => {
    setPreset(pr); setFormat(pr.format); setCodec(pr.codec); setResolution(pr.resolution); setBitrate(pr.bitrate);
  };

  const run = async () => {
    setExporting(true);
    setResult(null);
    setExportedFile(null);
    try {
      const res = await onExport({ format, codec, resolution, aspect_ratio: p.aspect_ratio, fps, bitrate, include_subtitles: true, include_chapters: true });
      const downloadUrl = typeof res.download_url === "string" ? `${API_BASE}${res.download_url}` : `${base}/media/exports/${String(res.filename || `export_${resolution}_${codec}.${format}`)}?download=true`;
      setExportedFile({ url: downloadUrl, filename: String(res.filename || `export_${resolution}_${codec}.${format}`) });
      setResult({ ok: true, text: `Export ready: ${String(res.output_path || res.filename || "Saved")}` });
    } catch (err) {
      setResult({ ok: false, text: `Export failed: ${err instanceof Error ? err.message : String(err)}` });
    } finally {
      setExporting(false);
    }
  };

  if (!finished) {
    return <div className="card p-10 text-center"><div className="font-bold text-lg">Finish the video first</div><p className="text-slate mt-1">Exporting opens up once production is done. Check progress on the Produce tab.</p></div>;
  }
  return (
    <div className="max-w-3xl space-y-8">
      <section className="space-y-4">
        <h2 className="font-bold">Export a copy</h2>
        <div className="grid grid-cols-2 gap-2">
          {PRESETS.map((pr) => (
            <button key={pr.id} onClick={() => pick(pr)} aria-pressed={preset.id === pr.id}
              className={`text-left rounded-lg border px-4 py-3 ${preset.id === pr.id ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}>
              <div className="font-semibold text-[13px]">{pr.label}</div>
              <div className={`text-xs ${preset.id === pr.id ? "text-[#b9c2cb]" : "text-mute"}`}>{pr.note}</div>
            </button>
          ))}
        </div>
        <button onClick={() => setAdvanced((v) => !v)} className="btn btn-ghost -ml-2" aria-expanded={advanced}>{advanced ? "Hide" : "Show"} advanced settings</button>
        {advanced && (
          <div className="card p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            <div><label htmlFor="fmt" className="label">Format</label>
              <select id="fmt" className="field" value={format} onChange={(e) => setFormat(e.target.value)}><option value="mp4">MP4</option><option value="mov">MOV</option><option value="webm">WebM</option><option value="wav">WAV (audio)</option><option value="mp3">MP3 (audio)</option></select></div>
            <div><label htmlFor="codec" className="label">Codec</label>
              <select id="codec" className="field" value={codec} onChange={(e) => setCodec(e.target.value)}><option value="h264">H.264</option><option value="h265">H.265</option><option value="prores">ProRes</option><option value="vp9">VP9</option></select></div>
            <div><label htmlFor="res" className="label">Resolution</label>
              <select id="res" className="field" value={resolution} onChange={(e) => setResolution(e.target.value)}><option value="1920x1080">1920×1080</option><option value="3840x2160">3840×2160</option><option value="1080x1920">1080×1920</option><option value="1280x720">1280×720</option></select></div>
            <div><label htmlFor="fps" className="label">Frames and bitrate</label>
              <div className="flex gap-2"><input id="fps" type="number" className="field w-20" value={fps} onChange={(e) => setFps(Number(e.target.value))} /><input aria-label="Bitrate" className="field" value={bitrate} onChange={(e) => setBitrate(e.target.value)} /></div></div>
          </div>
        )}
        <button disabled={exporting} onClick={run} className="btn btn-primary"><Download className="w-4 h-4" /> {exporting ? "Exporting…" : `Export ${preset.label}`}</button>
        {result && (
          <div role={result.ok ? "status" : "alert"} className={`px-3 py-2.5 rounded-lg text-[13px] border break-all space-y-2 ${result.ok ? "bg-done-soft border-done/30 text-done" : "bg-live-soft border-live/40 text-live"}`}>
            <div>{result.text}</div>
            {result.ok && exportedFile && (
              <div className="pt-1">
                <a href={exportedFile.url} download={exportedFile.filename} className="btn btn-primary btn-sm inline-flex items-center gap-1.5 py-1 px-3 text-xs">
                  <Download className="w-3.5 h-3.5" /> Download {exportedFile.filename}
                </a>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-bold">Download what's already made</h2>
        <div className="flex flex-wrap gap-2">
          <a href={`${base}/media/exports/final_production.mp4?download=true`} download="final_production.mp4" className="btn btn-primary"><Download className="w-4 h-4" /> Final video (MP4)</a>
          <a href={`${base}/share-bundle`} download={`${p.id}_share_bundle.zip`} className="btn btn-quiet"><Package className="w-4 h-4" /> Video, subtitles and audio (ZIP)</a>
          <button className="btn btn-quiet" onClick={() => { navigator.clipboard?.writeText(`${p.workspace_dir}/exports/final_production.mp4`); setResult({ ok: true, text: "File location copied." }); }}><Copy className="w-4 h-4" /> Copy file location</button>
        </div>
        <a href={`${base}/media/deliverables/production_report.json`} target="_blank" rel="noreferrer" className="text-[13px] underline text-slate hover:text-ink">Open the production report</a>
      </section>
    </div>
  );
}
