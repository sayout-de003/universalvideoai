import { useState } from "react";
import { ChevronDown, ChevronRight, Cpu, Download, FileVideo, Folder, HardDrive, Layers, List, Mic, Play, Trash2 } from "lucide-react";
import { API_BASE, studioClient } from "../api/client";
import type { HealthResponse, ProjectSummary } from "../types/studio";

interface Props {
  health: HealthResponse | null;
  engines: Record<string, unknown> | null;
  projects: ProjectSummary[];
  storageUsedMb: number;
  onOpenProject: (id: string) => void;
  onNewProject: () => void;
  onRefreshProjects: () => Promise<void>;
}

type ProjectFolders = Record<string, Array<{ name: string; subpath: string; size_bytes: number; is_video: boolean }>>;

export function DashboardView({ health, engines, projects, storageUsedMb, onOpenProject, onNewProject, onRefreshProjects }: Props) {
  const [viewMode, setViewMode] = useState<"list" | "folders">("list");
  const [expandedProject, setExpandedProject] = useState<string | null>(null);
  const [foldersByProject, setFoldersByProject] = useState<Record<string, ProjectFolders>>({});
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});

  const activeCount = projects.filter((p) => p.status === "running" || p.status === "paused").length;
  const completedCount = projects.filter((p) => p.status === "completed").length;
  const failedCount = projects.filter((p) => p.status === "qa_failed" || p.status === "failed").length;
  const renderEngines = (engines?.rendering_engines as Array<{ id: string; name: string; available: boolean }>) || [];
  const omToolsCount = (engines?.openmontage_tools_count as number) || 0;
  const omPipelines = (engines?.openmontage_pipelines as Array<{ name: string }>) || [];

  const loadFiles = async (pid: string) => {
    const res = await studioClient.listProjectFiles(pid);
    setFoldersByProject((prev) => ({ ...prev, [pid]: res.folders }));
  };

  const handleToggleProjectFolder = async (pid: string) => {
    if (expandedProject === pid) {
      setExpandedProject(null);
      return;
    }
    setExpandedProject(pid);
    await loadFiles(pid);
  };

  const handleDeleteProject = async (pid: string, title: string) => {
    if (!window.confirm(`Delete project "${title}" and all its folders/videos?`)) return;
    await studioClient.deleteProject(pid);
    if (expandedProject === pid) setExpandedProject(null);
    await onRefreshProjects();
  };

  const handleDeleteFile = async (pid: string, subpath: string, name: string) => {
    if (!window.confirm(`Delete file "${name}"?`)) return;
    await studioClient.deleteProjectFile(pid, subpath);
    await loadFiles(pid);
    await onRefreshProjects();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Studio Dashboard</h1>
          <p className="text-xs text-zinc-400 mt-1">Real-time host telemetry, OpenMontage engine registry, OpenWhispr voice status, and productions.</p>
        </div>
        <button onClick={onNewProject} className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 text-xs font-semibold transition">+ New Production</button>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800">
          <div className="text-xs text-zinc-400">Projects</div>
          <div className="text-2xl font-semibold mt-1">{projects.length}</div>
          <div className="text-[11px] text-zinc-500 mt-1">{activeCount} active · {completedCount} completed · {failedCount} failed</div>
        </div>
        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800">
          <div className="text-xs text-zinc-400 flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5 text-amber-400" /> Host Hardware</div>
          <div className="text-lg font-semibold mt-1">{health ? `${health.hardware.ram_gb} GB RAM` : "Probing..."}</div>
          <div className="text-[11px] text-zinc-500 mt-1">{health ? `${health.hardware.arch} · ${health.hardware.gpu_backend}` : ""}</div>
        </div>
        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800">
          <div className="text-xs text-zinc-400 flex items-center gap-1.5"><HardDrive className="w-3.5 h-3.5 text-sky-400" /> Storage</div>
          <div className="text-lg font-semibold mt-1">{storageUsedMb.toFixed(1)} MB used</div>
          <div className="text-[11px] text-zinc-500 mt-1">{health ? `${health.hardware.disk_free_gb} GB free on disk` : ""}</div>
        </div>
        <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800">
          <div className="text-xs text-zinc-400 flex items-center gap-1.5"><Mic className="w-3.5 h-3.5 text-emerald-400" /> OpenWhispr & OpenMontage</div>
          <div className="text-lg font-semibold mt-1">{omToolsCount} Tools · {omPipelines.length} Pipelines</div>
          <div className="text-[11px] text-zinc-500 mt-1">OpenWhispr Bridge: {health?.openwhispr.bridge_online ? "Online" : "Standby (Local Fallback Ready)"}</div>
        </div>
      </div>
      <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
        <div className="text-xs font-semibold text-zinc-200 flex items-center gap-2 mb-3"><Layers className="w-4 h-4 text-amber-400" /> Available Rendering & Generation Engines</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
          {renderEngines.map((eng) => (
            <div key={eng.id} className="p-3 rounded-lg bg-zinc-950/70 border border-zinc-800 flex items-center justify-between">
              <div><div className="text-xs font-medium text-zinc-200">{eng.name}</div><div className="text-[11px] text-zinc-500">{eng.id}</div></div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${eng.available ? "bg-emerald-500/15 text-emerald-300" : "bg-zinc-800 text-zinc-500"}`}>{eng.available ? "Ready" : "Unavailable"}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-semibold text-zinc-200">Productions & Project Files ({projects.length})</div>
          <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-800 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("list")}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium ${viewMode === "list" ? "bg-amber-500 text-zinc-950" : "text-zinc-400 hover:text-zinc-200"}`}
            >
              <List className="w-3.5 h-3.5" /> List View
            </button>
            <button
              onClick={() => setViewMode("folders")}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium ${viewMode === "folders" ? "bg-amber-500 text-zinc-950" : "text-zinc-400 hover:text-zinc-200"}`}
            >
              <Folder className="w-3.5 h-3.5" /> Folder Structure
            </button>
          </div>
        </div>
        {projects.length === 0 ? (
          <div className="text-xs text-zinc-500 py-8 text-center">No productions yet. Click <span className="text-amber-400">+ New Production</span> to create any video from natural language.</div>
        ) : (
          <div className="space-y-2">
            {projects.map((p) => {
              const isExpanded = viewMode === "folders" && expandedProject === p.id;
              const folders = foldersByProject[p.id] || {};
              return (
                <div key={p.id} className="rounded-lg bg-zinc-950/80 border border-zinc-800 overflow-hidden">
                  <div className="p-3 flex items-center justify-between gap-3 hover:bg-zinc-900/40 transition">
                    <div
                      onClick={() => (viewMode === "folders" ? handleToggleProjectFolder(p.id) : onOpenProject(p.id))}
                      className="flex items-center gap-2.5 flex-1 cursor-pointer min-w-0"
                    >
                      {viewMode === "folders" && (
                        isExpanded ? <ChevronDown className="w-4 h-4 text-amber-400 shrink-0" /> : <ChevronRight className="w-4 h-4 text-zinc-500 shrink-0" />
                      )}
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-zinc-100 truncate">{p.title} <span className="text-[11px] text-zinc-500 font-mono">({p.id})</span></div>
                        <div className="text-[11px] text-zinc-500 mt-0.5">{p.category} · {p.pipeline_name} · {p.render_engine} · {p.resolution} · {Math.round(p.target_duration_sec)}s</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[11px] px-2.5 py-1 rounded-full bg-zinc-800 text-zinc-300 capitalize">{p.status} ({p.current_stage})</span>
                      <button onClick={() => onOpenProject(p.id)} title="Open Project" className="p-1.5 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-amber-400">
                        <Play className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDeleteProject(p.id, p.title)} title="Delete Project & Videos" className="p-1.5 rounded-md bg-zinc-900 hover:bg-red-950/60 border border-zinc-800 hover:border-red-500/40 text-zinc-400 hover:text-red-400">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="border-t border-zinc-800/80 bg-zinc-950 px-4 py-3 space-y-2">
                      {Object.entries(folders).map(([folderName, files]) => {
                        const fKey = `${p.id}:${folderName}`;
                        const fOpen = expandedFolders[fKey] ?? (folderName === "exports" || folderName === "deliverables" || folderName === "renders");
                        return (
                          <div key={folderName} className="rounded-md border border-zinc-800/70 bg-zinc-900/30">
                            <button
                              onClick={() => setExpandedFolders((prev) => ({ ...prev, [fKey]: !fOpen }))}
                              className="w-full px-3 py-1.5 flex items-center justify-between text-xs text-zinc-300 hover:bg-zinc-900/60"
                            >
                              <span className="flex items-center gap-2 font-mono">
                                {fOpen ? <ChevronDown className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />}
                                <Folder className="w-3.5 h-3.5 text-amber-400" /> {folderName}/
                              </span>
                              <span className="text-[11px] text-zinc-500">{files.length} file(s)</span>
                            </button>
                            {fOpen && files.length > 0 && (
                              <div className="border-t border-zinc-800/60 divide-y divide-zinc-800/40">
                                {files.map((f) => (
                                  <div key={f.subpath} className="px-4 py-1.5 flex items-center justify-between text-xs">
                                    <span className="flex items-center gap-2 text-zinc-300 font-mono truncate">
                                      {f.is_video && <FileVideo className="w-3.5 h-3.5 text-sky-400 shrink-0" />}
                                      <span className="truncate">{f.name}</span>
                                      <span className="text-[10px] text-zinc-500">({(f.size_bytes / 1024).toFixed(1)} KB)</span>
                                    </span>
                                    <div className="flex items-center gap-1.5 shrink-0">
                                      <a
                                        href={`${API_BASE}/api/projects/${p.id}/media/${f.subpath}?download=true`}
                                        download={f.name}
                                        className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100"
                                        title="Download File"
                                      >
                                        <Download className="w-3.5 h-3.5" />
                                      </a>
                                      <button
                                        onClick={() => handleDeleteFile(p.id, f.subpath, f.name)}
                                        className="p-1 rounded hover:bg-red-950/60 text-zinc-400 hover:text-red-400"
                                        title="Delete File / Video"
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
