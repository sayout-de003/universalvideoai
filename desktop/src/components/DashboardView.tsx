import { useState } from "react";
import { ChevronDown, ChevronRight, Cpu, Download, FileVideo, FolderOpen, HardDrive, Plus, Trash2 } from "lucide-react";
import { API_BASE, studioClient } from "../api/client";
import { humanDuration, progressOfSummary } from "../lib/progress";
import type { HealthResponse, ProjectSummary } from "../types/studio";

interface Props {
  health: HealthResponse | null;
  engines: Record<string, unknown> | null;
  projects: ProjectSummary[];
  storageUsedMb: number;
  onOpenProject: (id: string) => void;
  onNewProject: () => void;
  onRefreshProjects: () => Promise<void>;
  onError: (message: string) => void;
}

type Folders = Record<string, Array<{ name: string; subpath: string; size_bytes: number; is_video: boolean }>>;
const chipClass = { idle: "chip", live: "chip chip-live", done: "chip chip-done", hold: "chip chip-hold" } as const;
const barClass = { idle: "bg-mute", live: "bg-live", done: "bg-done", hold: "bg-hold" } as const;

function fileSize(bytes: number) {
  return bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function cleanTitle(raw: string): string {
  return (raw || "")
    .replace(/^[#*\s]+/, "")
    .replace(/^(?:SCREENPLAY|SCRIPT|PROJECT)\s*:\s*/i, "")
    .replace(/\*?Format\s*:.*$/i, "")
    .trim() || "Untitled Production";
}

export function DashboardView({ health, engines, projects, storageUsedMb, onOpenProject, onNewProject, onRefreshProjects, onError }: Props) {
  const [filesOpen, setFilesOpen] = useState<string | null>(null);
  const [folders, setFolders] = useState<Record<string, Folders>>({});
  const [showSystem, setShowSystem] = useState(false);

  const renderEngines = (engines?.rendering_engines as Array<{ id: string; name: string; available: boolean }>) || [];
  const attempt = async (fn: () => Promise<unknown>) => {
    try { await fn(); } catch (err) { onError(err instanceof Error ? err.message : String(err)); }
  };

  const loadFiles = async (pid: string) => {
    const res = await studioClient.listProjectFiles(pid);
    setFolders((prev) => ({ ...prev, [pid]: res.folders }));
  };
  const toggleFiles = (pid: string) => attempt(async () => {
    if (filesOpen === pid) { setFilesOpen(null); return; }
    setFilesOpen(pid);
    await loadFiles(pid);
  });
  const deleteProject = (p: ProjectSummary) => attempt(async () => {
    if (!window.confirm(`Delete "${p.title}" and all of its videos? This can't be undone.`)) return;
    await studioClient.deleteProject(p.id);
    if (filesOpen === p.id) setFilesOpen(null);
    await onRefreshProjects();
  });
  const deleteFile = (pid: string, subpath: string, name: string) => attempt(async () => {
    if (!window.confirm(`Delete "${name}"?`)) return;
    await studioClient.deleteProjectFile(pid, subpath);
    await loadFiles(pid);
    await onRefreshProjects();
  });

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">My videos</h1>
          <p className="text-slate mt-1">Describe a video, review the script, then watch it get made.</p>
        </div>
        <button onClick={onNewProject} className="btn btn-primary"><Plus className="w-4 h-4" /> New video</button>
      </div>

      {projects.length === 0 ? (
        <div className="card p-10 text-center">
          <div className="text-lg font-bold">Nothing here yet</div>
          <p className="text-slate mt-1 mb-5">Write one paragraph about the video you want. The studio drafts the script for your approval first.</p>
          <button onClick={onNewProject} className="btn btn-primary"><Plus className="w-4 h-4" /> Start your first video</button>
        </div>
      ) : (
        <ul className="space-y-3">
          {projects.map((p) => {
            const pr = progressOfSummary(p);
            const open = filesOpen === p.id;
            const files = folders[p.id] || {};
            return (
              <li key={p.id} className="card overflow-hidden">
                <div className="p-4 flex items-center gap-4">
                  <button onClick={() => onOpenProject(p.id)} className="flex-1 min-w-0 text-left">
                    <div className="flex items-center gap-2.5">
                      <span className="font-bold text-[15px] truncate">{cleanTitle(p.title)}</span>
                      <span className={chipClass[pr.tone]}>{pr.tone === "live" && <span className="w-1.5 h-1.5 rounded-full bg-live tally" />}{pr.label}</span>
                    </div>
                    <div className="hint mt-0.5 truncate">
                      {humanDuration(p.target_duration_sec)} · {p.aspect_ratio} · {p.category.replace(/_/g, " ")}
                      {pr.scenesTotal > 0 && ` · ${pr.scenesDone} of ${pr.scenesTotal} scenes made`}
                    </div>
                    <div className="flex items-center gap-3 mt-3">
                      <div className="flex-1 h-1.5 rounded-full bg-rule overflow-hidden" role="progressbar" aria-valuenow={pr.percent} aria-valuemin={0} aria-valuemax={100} aria-label={`${p.title} progress`}>
                        <div className={`h-full rounded-full transition-all duration-700 ${barClass[pr.tone]}`} style={{ width: `${pr.percent}%` }} />
                      </div>
                      <span className="timecode text-xs text-slate w-10 text-right">{pr.percent}%</span>
                    </div>
                    <div className="hint mt-1">{pr.headline}</div>
                  </button>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => onOpenProject(p.id)} className="btn btn-quiet">Open</button>
                    <button onClick={() => toggleFiles(p.id)} className="btn btn-ghost" aria-expanded={open} title="Show files"><FolderOpen className="w-4 h-4" /> Files {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}</button>
                    <button onClick={() => deleteProject(p)} className="btn btn-ghost btn-danger" aria-label={`Delete ${p.title}`} title="Delete video"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </div>
                {open && (
                  <div className="border-t border-rule bg-sunken px-4 py-3 space-y-3">
                    {Object.keys(files).length === 0 && <div className="hint">No files yet.</div>}
                    {Object.entries(files).filter(([, list]) => list.length > 0).map(([folder, list]) => (
                      <div key={folder}>
                        <div className="text-xs font-semibold text-slate mb-1">{folder}</div>
                        <ul className="divide-y divide-rule card-sunken bg-panel">
                          {list.map((f) => (
                            <li key={f.subpath} className="px-3 py-1.5 flex items-center justify-between gap-3 text-[13px]">
                              <span className="flex items-center gap-2 min-w-0">
                                {f.is_video && <FileVideo className="w-3.5 h-3.5 text-done shrink-0" />}
                                <span className="truncate">{f.name}</span>
                                <span className="hint shrink-0">{fileSize(f.size_bytes)}</span>
                              </span>
                              <span className="flex items-center gap-1 shrink-0">
                                <a href={`${API_BASE}/api/projects/${p.id}/media/${f.subpath}?download=true`} download={f.name} className="btn btn-ghost" aria-label={`Download ${f.name}`}><Download className="w-3.5 h-3.5" /></a>
                                <button onClick={() => deleteFile(p.id, f.subpath, f.name)} className="btn btn-ghost btn-danger" aria-label={`Delete ${f.name}`}><Trash2 className="w-3.5 h-3.5" /></button>
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <section>
        <button onClick={() => setShowSystem((v) => !v)} className="btn btn-ghost -ml-2" aria-expanded={showSystem}>
          {showSystem ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />} Studio details
        </button>
        {showSystem && (
          <div className="card p-5 mt-2 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-[13px]">
              <div><div className="label flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5" /> This computer</div>{health ? `${health.hardware.cpu_cores} cores · ${health.hardware.ram_gb} GB memory · ${health.hardware.gpu_backend}` : "Checking…"}</div>
              <div><div className="label flex items-center gap-1.5"><HardDrive className="w-3.5 h-3.5" /> Storage</div>{storageUsedMb.toFixed(1)} MB used by videos{health ? ` · ${health.hardware.disk_free_gb} GB free` : ""}</div>
              <div><div className="label">Voice dictation</div>{health?.openwhispr.bridge_online ? "OpenWhispr connected" : "OpenWhispr not running — typing still works"}</div>
            </div>
            <div>
              <div className="label">Video & Animation Engines</div>
              <div className="flex flex-wrap gap-2">
                {renderEngines.map((e) => (
                  <span key={e.id} className={`chip ${e.available ? "chip-done" : ""}`}>
                    {e.name || e.id}
                    {e.available ? "" : " (not installed)"}
                  </span>
                ))}
                {renderEngines.length === 0 && <span className="hint">Waiting for the studio engine…</span>}
              </div>
            </div>
            <div>
              <div className="label">Voice & Speech Synthesis Providers</div>
              <div className="flex flex-wrap gap-2">
                {((engines?.tts_providers as Array<{ id: string; provider: string; model?: string; available: boolean }>) || []).map((t) => (
                  <span key={t.id} className={`chip ${t.available ? "chip-done" : ""}`}>
                    {t.provider} {t.model ? `(${t.model.split("/").pop()})` : ""}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
